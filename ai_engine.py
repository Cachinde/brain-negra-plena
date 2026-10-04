import requests
import uuid
from config import Config
from memory import MemoryManager
from catalog import CatalogService
from learning import LearningStore

class AIEngine:
    def __init__(self):
        self.memory = MemoryManager(max_history=8)
        self.catalog = CatalogService()
        self.learning = LearningStore()

    def generate_reply(self, numero_crm: str, texto_cliente: str, nome_cliente: str) -> str:
        resposta, _ = self._responder(numero_crm, texto_cliente, nome_cliente, registar=False)
        return resposta

    def responder(self, numero_crm: str, texto_cliente: str, nome_cliente: str) -> tuple:
        """Igual a generate_reply mas regista a troca no aprendizado e devolve o id."""
        return self._responder(numero_crm, texto_cliente, nome_cliente, registar=True)

    def _responder(self, numero_crm: str, texto_cliente: str, nome_cliente: str,
                   registar: bool) -> tuple:
        mensagem_id = uuid.uuid4().hex[:12]
        historico = self.memory.get_context(numero_crm)
        dados_negocio = self.catalog.get_context()
        system = Config.SYSTEM_PROMPT
        if dados_negocio:
            system += f"\n\nDADOS ATUAIS DO NEGOCIO:\n{dados_negocio}"

        user_text = texto_cliente.strip() or "(o cliente enviou uma mensagem sem texto)"
        exemplos = self.learning.format_examples(user_text)
        if exemplos:
            system += f"\n\n{exemplos}"

        user_text = texto_cliente.strip() or "(o cliente enviou uma mensagem sem texto)"
        mensagens = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    f"{historico}\n\nO cliente {nome_cliente} ({numero_crm}) diz: {user_text}"
                    if historico
                    else f"O cliente {nome_cliente} ({numero_crm}) diz: {user_text}"
                ),
            },
        ]

        # Nivel de Hierarquia (Fallback)
        # 1. Llama Local (ZeroGPU) -> 2. OpenRouter -> 3. Groq -> 4. DeepSeek -> 5. Gemini
        ordem_provedores = ["local_llama", "openrouter", "groq", "deepseek", "mistral", "gemini"]
        
        forced_provider = Config.AI_PROVIDER
        if forced_provider and forced_provider != "auto":
            # Se forcares um especifico, tenta-o primeiro, depois os outros
            ordem_provedores = [forced_provider] + [p for p in ordem_provedores if p != forced_provider]

        resposta = None
        erro_final = None
        provedor_ok = ""

        for provider in ordem_provedores:
            try:
                # Saltar provedores se a respectiva chave de seguranca nao existir
                if provider == "openrouter" and not Config.OPENROUTER_API_KEY: continue
                if provider == "groq" and not Config.GROQ_API_KEY: continue
                if provider == "deepseek" and not Config.DEEPSEEK_API_KEY: continue
                if provider == "mistral" and not Config.MISTRAL_API_KEY: continue
                if provider == "gemini" and not Config.GEMINI_API_KEY: continue
                
                print(f"[hierarchy] A tentar gerar resposta usando: {provider}...", flush=True)
                
                if provider == "local_llama":
                    from local_llm import generate_local
                    resposta = generate_local(mensagens)
                elif provider == "gemini":
                    resposta = self._call_gemini(system, mensagens[1]["content"])
                else:
                    resposta = self._call_openai_compatible(provider, mensagens)
                
                if resposta:
                    print(f"[hierarchy] Sucesso com {provider}!", flush=True)
                    provedor_ok = provider
                    break

            except Exception as exc:
                print(f"[hierarchy] Falha no provedor {provider}: {exc}", flush=True)
                erro_final = exc
                continue # Se falhou, a hierarquia ignora o erro e avanca para o proximo!

        if not resposta:
            print(f"[hierarchy] TODOS os provedores falharam. Erro final: {erro_final}", flush=True)
            return (
                "Peco desculpa, estou com uma instabilidade tecnica no sistema. "
                "Pode repetir a sua mensagem daqui a instantes?",
                mensagem_id,
            )

        self.memory.add_message(numero_crm, "user", user_text)
        self.memory.add_message(numero_crm, "model", resposta)
        if registar:
            modelo = Config.LOCAL_MODEL_ID if provedor_ok == "local_llama" else Config.get_model(provedor_ok)
            self.learning.log_exchange(
                numero_crm, user_text, resposta,
                provedor=provedor_ok, modelo=modelo,
                mensagem_id=mensagem_id,
            )
        return resposta, mensagem_id

    def _call_openai_compatible(self, provider: str, messages: list) -> str:
        url, headers = self._provider_endpoint(provider)
        payload = {
            "model": Config.get_model(provider),
            "messages": messages,
            "temperature": 0.4,
            "max_tokens": 450,
        }
        response = requests.post(url, headers=headers, json=payload, timeout=25)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    def _call_gemini(self, system: str, user_content: str) -> str:
        model = Config.get_model("gemini")
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={Config.GEMINI_API_KEY}"
        )
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user_content}]}],
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 450},
        }
        response = requests.post(url, json=payload, timeout=25)
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

    def _provider_endpoint(self, provider: str):
        if provider == "openrouter":
            return "https://openrouter.ai/api/v1/chat/completions", {
                "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://negraplena.ao",
                "X-Title": "Negra Plena Plenitude",
            }
        if provider == "groq":
            return "https://api.groq.com/openai/v1/chat/completions", {
                "Authorization": f"Bearer {Config.GROQ_API_KEY}",
                "Content-Type": "application/json",
            }
        if provider == "deepseek":
            return "https://api.deepseek.com/chat/completions", {
                "Authorization": f"Bearer {Config.DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            }
        if provider == "mistral":
            return "https://api.mistral.ai/v1/chat/completions", {
                "Authorization": f"Bearer {Config.MISTRAL_API_KEY}",
                "Content-Type": "application/json",
            }
        raise ValueError(f"Provedor nao suportado: {provider}")
