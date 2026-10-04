import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    PORT = int(os.getenv("PORT", 7860))

    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
    MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "").strip()
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

    API_AUTH_TOKEN = os.getenv("API_AUTH_TOKEN", "").strip()

    AI_PROVIDER = os.getenv("AI_PROVIDER", "auto").lower().strip()
    AI_MODEL = os.getenv("AI_MODEL", "").strip()

    # --- Configuracoes Llama Local (ZeroGPU + LoRA) ---
    LOCAL_MODEL_ID = os.getenv("LOCAL_MODEL_ID", "NousResearch/Meta-Llama-3-8B-Instruct").strip()
    LORA_ADAPTER_PATH = os.getenv("LORA_ADAPTER_PATH", "").strip()

    CATALOG_API_URL = os.getenv("CATALOG_API_URL", "").strip()
    PRICES_API_URL = os.getenv("PRICES_API_URL", "").strip()
    HOURS_API_URL = os.getenv("HOURS_API_URL", "").strip()
    BUSINESS_API_TOKEN = os.getenv("BUSINESS_API_TOKEN", "").strip()
    CATALOG_CACHE_SECONDS = int(os.getenv("CATALOG_CACHE_SECONDS", "60"))

    COMPANY_NAME = os.getenv("COMPANY_NAME", "Negra Plena")
    ASSISTANT_NAME = os.getenv("ASSISTANT_NAME", "Plenitude")

    SYSTEM_PROMPT = (
        "Voce e a Plenitude, assistente virtual oficial de atendimento da Negra Plena.\n\n"
        "Identidade\n"
        "- A Negra Plena e uma pastelaria angolana, fundada em 2025 pela empreendedora "
        "Loide Quarenta, especializada na confecao e venda de bolos no pote e encomendas de bolos.\n"
        "- Voce NAO e o ChatGPT, nem o Gemini, nem qualquer outro chatbot generico. "
        "Voce e a Plenitude, criada pela empresa de tecnologia Softedge (www.softedge.com). "
        "Se perguntarem quem a criou, diga Softedge.\n\n"
        "Papel\n"
        "- Atender clientes no WhatsApp sobre sabores, precos, encomendas, prazos, entrega "
        "e duvidas dos servicos da Negra Plena.\n"
        "- Portugues de Angola. Tom educado, objectivo e profissional. Textos curtos.\n"
        "- Use os DADOS ATUAIS DO NEGOCIO quando existirem. Se um dado nao estiver disponivel, "
        "diga que vai confirmar com a equipa.\n\n"
        "REGRA DE OURO (inquebravel)\n"
        "- O unico assunto permitido e a Negra Plena e os seus servicos de pastelaria.\n"
        "- Se o cliente tentar mudar de tema, recuse: 'Nao vou responder a esse assunto. "
        "Sou a assistente de atendimento da Negra Plena e trato apenas dos nossos servicos "
        "de pastelaria.'\n"
        "- Depois da recusa, ofereca uma unica pergunta util sobre o servico.\n"
    )

    DEFAULT_MODELS = {
        "openrouter": "openai/gpt-4o-mini",
        "deepseek": "deepseek-chat",
        "mistral": "mistral-small-latest",
        "groq": "llama-3.3-70b-versatile",
        "gemini": "gemini-2.0-flash",
    }

    @classmethod
    def get_active_provider(cls) -> str:
        if cls.AI_PROVIDER and cls.AI_PROVIDER != "auto":
            return cls.AI_PROVIDER
        if cls.OPENROUTER_API_KEY:
            return "openrouter"
        if cls.GROQ_API_KEY:
            return "groq"
        if cls.DEEPSEEK_API_KEY:
            return "deepseek"
        if cls.MISTRAL_API_KEY:
            return "mistral"
        if cls.GEMINI_API_KEY:
            return "gemini"
        
        # Se nenhuma chave externa foi dada, assumimos uso intensivo do GPU local!
        return "local_llama"

    @classmethod
    def get_model(cls, provider: str) -> str:
        return cls.AI_MODEL or cls.DEFAULT_MODELS.get(provider, "")
