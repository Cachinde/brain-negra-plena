from typing import Literal, Optional

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
    mensagem_id: Optional[str] = Field(
        default=None, description="Id para avaliar depois em POST /feedback"
    )


class FeedbackPayload(BaseModel):
    mensagem_id: str = Field(..., description="Id devolvido em EscutarResponse")
    nota: Literal["boa", "ma"] = Field(..., description="'boa' ou 'ma'")
    comentario: Optional[str] = Field(default=None, description="Nota opcional da equipa")


class FeedbackResponse(BaseModel):
    ok: bool = Field(..., description="True se a avaliação foi registada")
    detalhe: str = Field(..., description="Explicação curta")
