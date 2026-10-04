import requests
from config import Config
from memory import MemoryManager
from catalog import CatalogService

class AIEngine:
    def __init__(self):
        self.memory = MemoryManager(max_history=8)
        self.catalog = CatalogService()

    def generate_reply(self, numero_crm: str, texto_cliente: str, nome_cliente: str) -> str:
        provider = Config.get_active_provider()
        if provider == "none":
            return (
                "Peco desculpa, o atendimento automatico ainda nao esta configurado. "
                "A equipa da Negra Plena ira responder-lhe em breve."
            )

        historico = self.memory.get_context(numero_crm)
        dados_negocio = self.catalog.get_context()
        system = Config.SYSTEM_PROMPT
        if dados_negocio:
            system += f"\n\nDADOS ATUAIS DO NEGOCIO:\n{dados_negocio}"

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

        try:
            if provider == "gemini":
                resposta = self._call_gemini(system, mensagens[1]["content"])
            else:
                resposta = self._call_openai_compatible(provider, mensagens)

            self.memory.add_message(numero_crm, "user", user_text)
            self.memory.add_message(numero_crm, "model", resposta)
            return resposta
        except Exception as exc:
            print(f"Erro no AIEngine ({provider}): {exc}")
            return (
                "Peco desculpa, estou com um problema tecnico neste momento. "
                "Pode repetir daqui a instantes, por favor?"
            )

    def _call_openai_compatible(self, provider: str, messages: list) -> str:
        url, headers = self._provider_endpoint(provider)
        payload = {
            "model": Config.get_model(provider),
            "messages": messages,
            "temperature": 0.4,
            "max_tokens": 450,
        }
        response = requests.post(url, headers=headers, json=payload, timeout=45)
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
        response = requests.post(url, json=payload, timeout=45)
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
