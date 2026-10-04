import os
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import spaces

from ai_engine import AIEngine
from config import Config
from models import EscutarPayload, EscutarResponse

app = FastAPI(
    title="Plenitude — Cerebro Negra Plena",
    description="API de atendimento da pastelaria Negra Plena com suporte a GPU.",
    version="1.0.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = AIEngine()


def require_token(authorization: str = Header(default="")) -> None:
    if not Config.API_AUTH_TOKEN:
        return
    expected = f"Bearer {Config.API_AUTH_TOKEN}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Token invalido")


# A Hugging Face exige que haja uma funcao com @spaces.GPU se o Space tiver GPU!
@spaces.GPU
def run_ml_task(texto: str):
    return f"GPU Processed: {texto}"


@app.get("/")
def root():
    return {
        "assistente": Config.ASSISTANT_NAME,
        "empresa": Config.COMPANY_NAME,
        "status": "ok",
        "provedor": Config.get_active_provider(),
        "gpu_enabled": True
    }


@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/escutar", response_model=EscutarResponse)
@app.post("/api/escutar", response_model=EscutarResponse)
def escutar(payload: EscutarPayload, _: None = Depends(require_token)):
    cliente = payload.numero_crm or payload.numero or "unknown"
    texto = payload.texto.strip()
    
    if not texto and not payload.audio_base64:
        return EscutarResponse(
            texto="Nao consegui ler a sua mensagem. Pode escrever de novo, por favor?"
        )

    if not texto and payload.audio_base64:
        texto = "(o cliente enviou um audio; transcricao na GPU ainda em preparacao)"

    resposta = engine.generate_reply(cliente, texto, payload.nome or "Cliente")
    return EscutarResponse(texto=resposta)
