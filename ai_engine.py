import requests
import re
import uuid
from config import Config
from memory import MemoryManager
from catalog import CatalogService
from learning import LearningStore
from profiles import ProfileStore


_SAUDACAO_INICIAL = re.compile(
    r"^\s*(ol[aá]|oi|bom dia|boa tarde|boa noite)\b[^,;:.!?…\n]*[,;:.!?…]?\s*",
    re.IGNORECASE,
)


def tirar_saudacao(resposta: str, nome: str = "") -> str:
    """Corta saudação inicial repetida ('Olá Isaac! ...', 'Isaac! ...').

    O nome próprio só é cortado quando é o cliente conhecido.
    Nunca devolve vazio.
    """
    texto = _SAUDACAO_INICIAL.sub("", resposta or "", count=1).lstrip()
    nome_limpo = (nome or "").strip()
    if nome_limpo:
        variantes = {nome_limpo, nome_limpo.split()[0]}
        for variante in sorted(variantes, key=len, reverse=True):
            if len(variante) >= 3:
                texto = re.sub(
                    r"^\s*" + re.escape(variante) + r"\s*[!,]\s*",
                    "", texto, count=1, flags=re.IGNORECASE,
                ).lstrip()
    return texto if texto else (resposta or "").strip()


# Corrupções observadas no Llama-8B -> forma correcta.
# Lista fechada (só o que já apareceu nos logs); ordem importa.
_CORRECOES = [
    (r"\bNeg(?:re|rela|rega|reira|ral)\s+Plena\b"
     r"|\bNegra\s+(?:Pena|Piena)\b"
     r"|\bNegral\s+(?:Piena|Pi[ñn]a)\b", "Negra Plena"),
    (r"\bPlentude\b|\bPlenuidade\b", "Plenitude"),
    (r"\bservicios\b", "serviços"),
    (r"\bpasteleira\b|\bpasteleria\b", "pastelaria"),
    (r"\bmás\b", "mais"),
    (r"\batenci[oó]n\b", "atenção"),
    (r"\bsimplicit[eé]\b", "simplicidade"),
    (r"\bangolanenses\b", "angolanos"),
    (r"\bangolanense\b", "angolana"),
    (r"\bEnroladinh[oó]s\b", "enroladinhos"),
    (r"\bchourisos\b", "chouriços"),
    (r"\bchouriso\b", "chouriço"),
    (r"\bBolhas\s+de\s+Berl(?:im|in)\b", "Bolas de Berlim"),
    (r"\bRiss[oó]i\b", "rissóis"),
    (r"\bsaudos\b", "salgados"),
    (r"\bBerlin\b", "Berlim"),
]
_CORRECOES_RX = [(re.compile(pat, re.IGNORECASE), rep) for pat, rep in _CORRECOES]


def sanitizar(resposta: str) -> str:
    """Corrige corrupções conhecidas do 8B (nomes, idioma, produtos)."""
    texto = resposta or ""
    for rx, rep in _CORRECOES_RX:
        texto = rx.sub(rep, texto)
    return texto.strip() or (resposta or "").strip()


class AIEngine:
    def __init__(self):
        self.memory = MemoryManager(max_history=8)
        self.catalog = CatalogService()
        self.learning = LearningStore()
        self.profiles = ProfileStore()
    def generate_reply(self, numero_crm: str, texto_cliente: str, nome_cliente: str) -> str:
        resposta, _ = self._responder(numero_crm, texto_cliente, nome_cliente, registar=False)
        return resposta

    def responder(self, numero_crm: str, texto_cliente: str, nome_cliente: str,
                  fora_expediente: bool = False) -> tuple:
        """Igual a generate_reply mas regista a troca no aprendizado e devolve o id."""
        return self._responder(numero_crm, texto_cliente, nome_cliente,
                               registar=True, fora_expediente=fora_expediente)

    def _responder(self, numero_crm: str, texto_cliente: str, nome_cliente: str,
                   registar: bool, fora_expediente: bool = False) -> tuple:
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

        perfil_txt = self.profiles.linha_contexto(numero_crm, nome_cliente)
        if perfil_txt:
            system += f"\n\n{perfil_txt}"

        if fora_expediente:
            system += (
                "\n\nHORARIO: Agora está FORA do horário comercial "
                "(humanos: dias úteis 9h–18h Luanda). Atende na mesma com clareza; "
                "se pedirem atendimento humano, diz que a equipa responde a partir "
                "das 9h e que deixas o pedido registado. Nunca prometas contacto "
                "humano imediato fora de horas."
            )

        user_text = texto_cliente.strip() or "(o cliente enviou uma mensagem sem texto)"
        atual = f"O cliente {nome_cliente} ({numero_crm}) diz: {user_text}"
        # Turnos reais (melhor coerência que histórico colado num turno só).
        mensagens = [{"role": "system", "content": system}]
        mensagens += self.memory.get_turns(numero_crm)
        mensagens.append({"role": "user", "content": atual})
        # Versão corrida só para o caminho Gemini (1 turno de utilizador).
        texto_corrido = f"{historico}\n\n{atual}" if historico else atual

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
                    resposta = self._call_gemini(system, texto_corrido)
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

        era_conhecido = int(self.profiles.obter(numero_crm).get("n_trocas", 0) or 0) > 0
        if era_conhecido:
            resposta = tirar_saudacao(resposta, nome_cliente)
        resposta = sanitizar(resposta)

        self.memory.add_message(numero_crm, "user", user_text)
        self.memory.add_message(numero_crm, "model", resposta)
        self.profiles.registar(numero_crm, nome_cliente, user_text)
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
