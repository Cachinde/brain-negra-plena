from typing import Optional
from pydantic import BaseModel, Field

class EscutarPayload(BaseModel):
    numero: str = ""
    numero_crm: str = ""
    nome: str = "Cliente"
    texto: str = ""
    tipo_conversa: str = "pv"
    grupo_id: Optional[str] = None
    mensagem_id: Optional[str] = None
    audio_base64: Optional[str] = None

class EscutarResponse(BaseModel):
    texto: str = Field(..., description="Resposta a enviar no WhatsApp")
