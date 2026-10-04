"""Aprendizado v1 — log local JSONL + recuperação de casos parecidos (few-shot).

Sem dependências novas, só stdlib. CPU-friendly, sem GPU.

- Cada troca bot<->cliente é anexada a `conversas.jsonl` (ver `DATA_DIR`).
- `POST /feedback` classifica uma resposta como "boa"/"ma".
- Respostas "ma" nunca voltam como exemplo; "boa" tem prioridade.
- Exemplos parecidos entram no prompt como few-shot (factos e tom).
- O ficheiro nunca deve ir para git (contém números de clientes): ver `.gitignore`.
"""

import json
import os
import re
import threading
import unicodedata
import uuid
from datetime import datetime, timezone

_STOPWORDS = {
    "a", "o", "e", "de", "do", "da", "dos", "das", "em", "um", "uma",
    "para", "com", "que", "quanto", "quantos", "qual", "quais", "como",
    "quando", "onde", "os", "as", "uns", "umas", "no", "na", "nos",
    "nas", "ao", "aos", "por", "mais", "muito", "isto", "isso", "este",
    "esta", "esse", "essa", "meu", "minha", "seu", "sua", "voce", "você",
    "tem", "têm", "e", "se", "qto", "qt", "q", "la", "lá", "ai", "aí",
    "entao", "então", "pois", "mas", "ou", "tambem", "também",
}


def _tokens(texto: str) -> set:
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    palavras = re.findall(r"[a-z0-9]+", sem_acento.lower())
    return {p for p in palavras if len(p) > 2 and p not in _STOPWORDS}


class LearningStore:
    """Guarda trocas em JSONL e recupera casos parecidos."""

    def __init__(
        self,
        data_dir: str | None = None,
        arquivo: str = "conversas.jsonl",
        max_linhas: int = 2000,
        top_k: int = 2,
        min_score: float = 0.15,
    ):
        self.data_dir = data_dir or os.getenv("DATA_DIR", "./data")
        self.arquivo = arquivo
        self.max_linhas = int(os.getenv("LEARNING_MAX_LINHAS", str(max_linhas)))
        self.top_k = int(os.getenv("LEARNING_TOP_K", str(top_k)))
        self.min_score = float(os.getenv("LEARNING_MIN_SCORE", str(min_score)))
        self._lock = threading.Lock()
        try:
            os.makedirs(self.data_dir, exist_ok=True)
        except Exception as exc:
            print(f"[learning] não consegui criar {self.data_dir}: {exc}")

    def _caminho(self) -> str:
        return os.path.join(self.data_dir, self.arquivo)

    def _ler_tudo(self) -> list:
        registos = []
        try:
            with open(self._caminho(), "r", encoding="utf-8") as fh:
                for linha in fh:
                    linha = linha.strip()
                    if not linha:
                        continue
                    try:
                        registos.append(json.loads(linha))
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            pass
        except Exception as exc:
            print(f"[learning] erro a ler: {exc}")
        return registos

    def log_exchange(self, cliente: str, pergunta: str, resposta: str,
                     provedor: str = "", modelo: str = "",
                     mensagem_id: str | None = None) -> str:
        mensagem_id = mensagem_id or uuid.uuid4().hex[:12]
        registo = {
            "id": mensagem_id,
            "ts": datetime.now(timezone.utc).isoformat(),
            "cliente": cliente or "unknown",
            "pergunta": (pergunta or "")[:1000],
            "resposta": (resposta or "")[:1000],
            "provedor": provedor,
            "modelo": modelo,
            "avaliacao": None,
        }
        try:
            with self._lock:
                with open(self._caminho(), "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(registo, ensure_ascii=False) + "\n")
                self._podar()
        except Exception as exc:
            print(f"[learning] erro a registar: {exc}")
        return mensagem_id

    def _podar(self) -> None:
        try:
            with open(self._caminho(), "r", encoding="utf-8") as fh:
                linhas = fh.readlines()
            if len(linhas) > self.max_linhas + 500:
                with open(self._caminho(), "w", encoding="utf-8") as fh:
                    fh.writelines(linhas[-self.max_linhas:])
        except FileNotFoundError:
            pass
        except Exception as exc:
            print(f"[learning] erro a podar: {exc}")

    def rate(self, mensagem_id: str, nota: str, observacao: str = "") -> bool:
        if nota not in ("boa", "ma"):
            return False
        try:
            with self._lock:
                registos = self._ler_tudo()
                achou = False
                for reg in registos:
                    if reg.get("id") == mensagem_id:
                        reg["avaliacao"] = nota
                        if observacao:
                            reg["observacao"] = observacao[:500]
                        achou = True
                        break
                if not achou:
                    return False
                with open(self._caminho(), "w", encoding="utf-8") as fh:
                    for reg in registos:
                        fh.write(json.dumps(reg, ensure_ascii=False) + "\n")
                return True
        except Exception as exc:
            print(f"[learning] erro a avaliar: {exc}")
            return False

    def find_similar(self, pergunta: str, k: int | None = None) -> list:
        base = _tokens(pergunta)
        if not base:
            return []
        candidatos = []
        try:
            for reg in self._ler_tudo():
                if reg.get("avaliacao") == "ma":
                    continue
                pontos = _tokens(reg.get("pergunta", ""))
                if not pontos:
                    continue
                uniao = base | pontos
                score = len(base & pontos) / len(uniao) if uniao else 0.0
                if reg.get("avaliacao") == "boa":
                    score = min(1.0, score + 0.25)
                if score >= self.min_score:
                    candidatos.append((score, reg))
        except Exception as exc:
            print(f"[learning] erro a procurar: {exc}")
            return []
        candidatos.sort(key=lambda item: item[0], reverse=True)
        return [reg for _, reg in candidatos[: (k or self.top_k)]]

    def format_examples(self, pergunta: str) -> str:
        exemplos = self.find_similar(pergunta)
        if not exemplos:
            return ""
        blocos = ["EXEMPLOS DE ATENDIMENTOS ANTERIORES (segue o mesmo padrão de factos e tom):"]
        total = len(blocos[0])
        for i, reg in enumerate(exemplos, 1):
            perg = (reg.get("pergunta", "") or "")[:200]
            resp = (reg.get("resposta", "") or "")[:300]
            bloco = f"{i}) Cliente: {perg}\n   Plenitude: {resp}"
            if total + len(bloco) > 900:
                break
            blocos.append(bloco)
            total += len(bloco)
        if len(blocos) < 2:
            return ""
        return "\n".join(blocos)

    def count(self) -> int:
        return len(self._ler_tudo())
