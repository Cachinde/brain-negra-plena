"""Llama local no ZeroGPU — inferência com pesos abertos + LoRA opcional.

Regras ZeroGPU respeitadas:
- `import spaces` ANTES de qualquer import que toque CUDA (regra nº1).
- Modelo carregado UMA vez no processo principal com `.to("cuda")`
  (o hijack do spaces trata disto); NUNCA dentro do `@spaces.GPU`.
- `@spaces.GPU` só em função de módulo (o `self` com o modelo não
  atravessa o fork; ver "Process isolation and pickle").
- Falha de download (ex. repo gated sem licença) NÃO deita o Space
  abaixo: regista o motivo uma vez e a hierarquia cai para as APIs externas.
"""

import spaces  # tem de ser o primeiro import com CUDA por perto

import os
import threading

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

try:
    from peft import PeftModel
except ImportError:
    PeftModel = None

from config import Config

_MODEL = None
_TOKENIZER = None
_LOAD_FAILED = ""
_LOAD_LOCK = threading.Lock()


def _ensure_loaded() -> bool:
    global _MODEL, _TOKENIZER, _LOAD_FAILED
    if _MODEL is not None:
        return True
    if _LOAD_FAILED:
        return False
    with _LOAD_LOCK:
        if _MODEL is not None:
            return True
        if _LOAD_FAILED:
            return False
        return _load_once()


def _load_once() -> bool:
    global _MODEL, _TOKENIZER, _LOAD_FAILED
    model_id = Config.LOCAL_MODEL_ID
    try:
        print(f"[llama] a carregar {model_id} ...", flush=True)
        tok = AutoTokenizer.from_pretrained(model_id)
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token
        mdl = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=torch.bfloat16,
            low_cpu_mem_usage=True,
        )
        # Uma vez no processo principal; o hijack do spaces gere o resto.
        mdl.to("cuda")
        lora = Config.LORA_ADAPTER_PATH
        if lora:
            if not os.path.exists(lora):
                print(f"[llama] LORA_ADAPTER_PATH inexistente ({lora}); a ignorar.", flush=True)
            elif PeftModel is None:
                raise RuntimeError("peft não instalado; não consigo aplicar o adaptador LoRA")
            else:
                print(f"[llama] a aplicar LoRA de: {lora} ...", flush=True)
                mdl = PeftModel.from_pretrained(mdl, lora)
        mdl.eval()
        _MODEL, _TOKENIZER = mdl, tok
        print("[llama] modelo pronto.", flush=True)
        return True
    except Exception as exc:
        _LOAD_FAILED = f"{type(exc).__name__}: {exc}"
        print(f"[llama] indisponível ({_LOAD_FAILED}); fallback para APIs externas.", flush=True)
        return False


@spaces.GPU(duration=180)
def generate_local(messages: list) -> str:
    """Gera resposta com o Llama local. Falha rápido se o modelo não carregou."""
    if not _ensure_loaded():
        raise RuntimeError(f"Llama local indisponível: {_LOAD_FAILED}")
    prompt = _TOKENIZER.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = _TOKENIZER(prompt, return_tensors="pt").to("cuda")
    gen = _MODEL.generate(
        **inputs,
        max_new_tokens=450,
        temperature=0.4,
        top_p=0.9,
        do_sample=True,
        pad_token_id=_TOKENIZER.eos_token_id,
    )
    texto = _TOKENIZER.decode(
        gen[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True
    )
    return texto.strip()
