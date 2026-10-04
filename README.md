---
title: Plenitude Negra Plena
emoji: 🧁
colorFrom: purple
colorTo: pink
sdk: gradio
sdk_version: 6.29.1
python_version: '3.12'
app_file: app.py
pinned: false
---

# Plenitude — cerebro da Negra Plena

API FastAPI da assistente **Plenitude**, atendimento da pastelaria **Negra Plena**.  
Criada pela **Softedge**. O conector WhatsApp (Node, Railway) envia `POST /api/escutar` e recebe `{ "texto": "..." }`.

`app.py` serve a API (`main.py`) com uvicorn na porta 7860 e mostra uma interface Gradio de teste em `/`.

## GPU ativada
A anotacao @spaces.GPU esta configurada para suportar inferencia rapida.

## Hierarquia de provedores (fallback)

1. Llama local (ZeroGPU) → 2. OpenRouter → 3. Groq → 4. DeepSeek → 5. Mistral → 6. Gemini.
Cada nível que falha cai para o seguinte; `AI_PROVIDER` força um específico primeiro.
O Llama local (`local_llm.py`, `NousResearch/Meta-Llama-3-8B-Instruct` por defeito,
LoRA opcional via `LORA_ADAPTER_PATH`) é carregado uma vez e corre no `@spaces.GPU`;
se o download falhar (ex. repo gated sem licença + `HF_TOKEN`), cai para as APIs externas.
Vars: `LOCAL_MODEL_ID`, `LORA_ADAPTER_PATH`, `HF_TOKEN`.

## Aprendizado (v1, log local JSONL)

- Cada resposta do `/escutar` é registada em `data/conversas.jsonl` e devolve um `mensagem_id`.
- Avalie com `POST /api/feedback` (`{"mensagem_id": "...", "nota": "boa"|"ma"}`);
  casos `"ma"` nunca voltam como exemplo, `"boa"` tem prioridade.
- Perguntas parecidas com casos anteriores entram no prompt como exemplos (few-shot).
- O ficheiro contém números de clientes: nunca vai para git e perde-se em factory rebuild.
- Vars: `DATA_DIR` (`./data`), `LEARNING_MAX_LINHAS` (2000), `LEARNING_TOP_K` (2).

## Endpoints

- `GET /` — interface Gradio de teste
- `GET /health` e `GET /api/health`
- `POST /api/escutar` ou `POST /escutar`
- `POST /api/feedback` ou `POST /feedback`
- `GET /docs` — OpenAPI
