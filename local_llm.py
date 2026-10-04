import os
import torch
import spaces
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from config import Config

class LocalLlamaEngine:
    _instance = None

    def __init__(self):
        self.model_id = Config.LOCAL_MODEL_ID
        self.lora_path = Config.LORA_ADAPTER_PATH
        
        print(f"🔄 A iniciar Llama local ({self.model_id}) na RAM (ZeroGPU movera para GPU na inferencia)...")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_id)
        
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            torch_dtype=torch.bfloat16,
            low_cpu_mem_usage=True
        )
        
        if self.lora_path and os.path.exists(self.lora_path):
            print(f"🧠 A aplicar pesos de aprendizagem LoRA de: {self.lora_path}...")
            self.model = PeftModel.from_pretrained(self.model, self.lora_path)
            
        print("✅ Llama local preparado e pronto a usar!")

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @spaces.GPU
    def generate(self, messages: list) -> str:
        # Movemos o modelo para a GPU no exacto momento do atendimento
        self.model.to("cuda")
        
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tokenizer(prompt, return_tensors="pt").to("cuda")
        
        outputs = self.model.generate(
            **inputs, 
            max_new_tokens=450, 
            temperature=0.4, 
            top_p=0.9,
            do_sample=True,
            pad_token_id=self.tokenizer.eos_token_id
        )
        
        response = self.tokenizer.decode(outputs[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True)
        return response.strip()
