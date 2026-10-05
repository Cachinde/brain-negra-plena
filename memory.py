"""Histórico curto por cliente — RAM com espelho em disco.

A RAM sozinha amnésia quando o Space dorme/reinicia; o disco
(`historico.json` em `DATA_DIR`) faz a conversa sobreviver.
Nunca vai para git (tem PII de clientes).
"""

import json
import os
import threading
from collections import deque
from typing import Deque, Dict, List

_ARQUIVO = "historico.json"
_MAX_CLIENTES = 500


class MemoryManager:
    def __init__(self, max_history: int = 8, data_dir: str | None = None,
                 arquivo: str = _ARQUIVO):
        self.max_history = max_history
        self.data_dir = data_dir or os.getenv("DATA_DIR", "./data")
        self.arquivo = arquivo
        self._lock = threading.Lock()
        self._store: Dict[str, Deque[dict]] = {}
        self._carregar()

    def _caminho(self) -> str:
        return os.path.join(self.data_dir, self.arquivo)

    def _carregar(self) -> None:
        try:
            with open(self._caminho(), "r", encoding="utf-8") as fh:
                dados = json.load(fh)
            if not isinstance(dados, dict):
                return
            for cliente, itens in list(dados.items())[:_MAX_CLIENTES]:
                for item in (itens or [])[-self.max_history:]:
                    if isinstance(item, dict) and item.get("role") in ("user", "model"):
                        self._fila(cliente).append({
                            "role": item["role"],
                            "content": str(item.get("content", ""))[:2000],
                        })
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        except Exception as exc:
            print(f"[memory] erro a carregar: {exc}")

    def _guardar(self) -> None:
        tmp = self._caminho() + ".tmp"
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            dados = {k: list(v) for k, v in self._store.items()}
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(dados, fh, ensure_ascii=False)
            os.replace(tmp, self._caminho())
        except Exception as exc:
            print(f"[memory] erro a guardar: {exc}")

    def _fila(self, client_id: str) -> Deque[dict]:
        fila = self._store.get(client_id)
        if fila is None:
            fila = deque(maxlen=self.max_history)
            self._store[client_id] = fila
        return fila

    def get_context(self, client_id: str) -> str:
        history = self._store.get(client_id)
        if not history:
            return ""

        lines: List[str] = ["Histórico recente desta conversa:"]
        for item in history:
            role = "Cliente" if item["role"] == "user" else "Plenitude"
            lines.append(f"{role}: {item['content']}")
        return "\n".join(lines)

    def get_turns(self, client_id: str) -> List[dict]:
        """Turnos no formato do chat (user/assistant) para o LLM."""
        history = self._store.get(client_id)
        if not history:
            return []
        return [
            {
                "role": "user" if item["role"] == "user" else "assistant",
                "content": item["content"],
            }
            for item in history
        ]

    def add_message(self, client_id: str, role: str, content: str) -> None:
        if not client_id or not content:
            return
        if role not in ("user", "model"):
            return
        with self._lock:
            fila = self._fila(client_id)
            fila.append({"role": role, "content": content.strip()[:2000]})
            while len(self._store) > _MAX_CLIENTES:
                mais_antigo = next(iter(self._store))
                if mais_antigo == client_id:
                    break
                del self._store[mais_antigo]
            self._guardar()
