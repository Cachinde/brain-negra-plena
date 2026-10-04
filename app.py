import gradio as gr
import spaces
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from config import Config
from ai_engine import AIEngine
from models import EscutarPayload, EscutarResponse

engine = AIEngine()

# ---------- FastAPI (WhatsApp Bot envia pedidos aqui) ----------
api = FastAPI(title="Plenitude API")
api.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def require_token(authorization: str = Header(default="")):
    if not Config.API_AUTH_TOKEN:
        return
    if authorization != f"Bearer {Config.API_AUTH_TOKEN}":
        raise HTTPException(status_code=401, detail="Token invalido")

@api.get("/health")
@api.get("/api/health")
def health():
    return {"status": "ok"}

@api.post("/escutar", response_model=EscutarResponse)
@api.post("/api/escutar", response_model=EscutarResponse)
def escutar(payload: EscutarPayload, _=Depends(require_token)):
    cliente = payload.numero_crm or payload.numero or "unknown"
    texto = payload.texto.strip()
    if not texto and not payload.audio_base64:
        return EscutarResponse(texto="Nao consegui ler a sua mensagem. Pode escrever de novo?")
    if not texto:
        texto = "(audio recebido)"
    resposta = engine.generate_reply(cliente, texto, payload.nome or "Cliente")
    return EscutarResponse(texto=resposta)

# ---------- Gradio (Interface visual + ZeroGPU) ----------
@spaces.GPU
def plenitude_chat(message, history):
    if not message or not message.strip():
        return "Por favor, escreva a sua mensagem."
    return engine.generate_reply("web_user", message, "Visitante")

_demo = gr.ChatInterface(
    fn=plenitude_chat,
    title="Plenitude - Negra Plena",
    description="Assistente virtual da pastelaria Negra Plena. Desenvolvida pela Softedge.",
)

# Monta o Gradio por cima do FastAPI (ambos na mesma porta 7860)
app = gr.mount_gradio_app(api, _demo, path="/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
