"""Perfis persistentes de cliente — a Plenitude conhece quem fala.

- Guarda por cliente: nome, primeiro/último contacto, nº de trocas, último assunto.
- `linha_contexto()` diz ao prompt se o cliente é recorrente (para NÃO
  repetir saudações) e qual era o assunto anterior (continuidade).
- Classificação de assunto por palavras-chave (sem dependências).
- Ficheiro `perfis.json` em `DATA_DIR`; nunca vai para git (tem PII).
"""

import json
import os
import re
import threading
import unicodedata
from datetime import datetime, timezone

_ARQUIVO = "perfis.json"

_ASSUNTOS = [
    ("precos", {
        "preco", "precos", "custa", "custam", "custo", "valor", "valores",
        "tabela", "quanto", "pagar", "pagamento", "preçario",
    }),
    ("encomenda", {
        "encomenda", "encomendar", "pedido", "pedir", "peco", "reserva",
        "reservar", "marcar", "marcacao", "quero", "queria", "gostaria",
    }),
    ("horario", {
        "horario", "horarios", "hora", "horas", "aberto", "aberta",
        "fechado", "fechada", "abre", "fecha", "entrega", "entregam",
        "quando", "onde", "localizacao", "local", "endereco",
    }),
    ("saudacao", {
        "ola", "oi", "bom", "dia", "tarde", "noite", "bemvindo", "boas",
    }),
]


def _toks(texto: str) -> set:
    base = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return set(re.findall(r"[a-z]+", base.lower()))


def classificar_assunto(texto: str) -> str:
    toks = _toks(texto)
    for assunto, chaves in _ASSUNTOS:
        if toks & chaves:
            return assunto
    return "outro"


class ProfileStore:
    def __init__(self, data_dir: str | None = None, arquivo: str = _ARQUIVO):
        self.data_dir = data_dir or os.getenv("DATA_DIR", "./data")
        self.arquivo = arquivo
        self._lock = threading.Lock()
        try:
            os.makedirs(self.data_dir, exist_ok=True)
        except Exception as exc:
            print(f"[profiles] não consegui criar {self.data_dir}: {exc}")

    def _caminho(self) -> str:
        return os.path.join(self.data_dir, self.arquivo)

    def _carregar(self) -> dict:
        try:
            with open(self._caminho(), "r", encoding="utf-8") as fh:
                dados = json.load(fh)
                return dados if isinstance(dados, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
        except Exception as exc:
            print(f"[profiles] erro a ler: {exc}")
            return {}

    def _guardar(self, dados: dict) -> None:
        tmp = self._caminho() + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(dados, fh, ensure_ascii=False)
            os.replace(tmp, self._caminho())
        except Exception as exc:
            print(f"[profiles] erro a guardar: {exc}")

    def obter(self, cliente: str) -> dict:
        with self._lock:
            return self._carregar().get(cliente or "unknown", {})

    def linha_contexto(self, cliente: str, nome: str = "") -> str:
        """Devolve "" para estreantes; para recorrentes, manda não saudar."""
        perfil = self.obter(cliente)
        n = int(perfil.get("n_trocas", 0) or 0)
        if n <= 0:
            return ""
        quem = perfil.get("nome") or (nome or "").strip() or "cliente sem nome registado"
        assunto = perfil.get("ultimo_assunto") or "outro"
        return (
            f"Conheces este cliente ({quem}): já trocaram {n} mensagem(ns) antes; "
            f"último assunto: {assunto}. NÃO cumprimentes de novo — "
            f"vai direto ao assunto com continuidade."
        )

    def registar(self, cliente: str, nome: str = "", pergunta: str = "") -> dict:
        chave = cliente or "unknown"
        agora = datetime.now(timezone.utc).isoformat()
        with self._lock:
            dados = self._carregar()
            perfil = dados.get(chave, {})
            nome_limpo = (nome or "").strip()
            if nome_limpo and nome_limpo.lower() not in ("cliente", "visitante"):
                perfil["nome"] = nome_limpo
            perfil["primeiro_contacto"] = perfil.get("primeiro_contacto", agora)
            perfil["ultimo_contacto"] = agora
            perfil["n_trocas"] = int(perfil.get("n_trocas", 0) or 0) + 1
            if pergunta:
                perfil["ultimo_assunto"] = classificar_assunto(pergunta)
            dados[chave] = perfil
            self._guardar(dados)
            return dict(perfil)
