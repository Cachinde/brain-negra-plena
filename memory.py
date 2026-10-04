from collections import defaultdict, deque
from typing import Deque, Dict, List


class MemoryManager:
    """Histórico curto por cliente, em memória (adequado a CPU-basic no HF Space)."""

    def __init__(self, max_history: int = 8):
        self.max_history = max_history
        self._store: Dict[str, Deque[dict]] = defaultdict(lambda: deque(maxlen=max_history))

    def get_context(self, client_id: str) -> str:
        history = self._store.get(client_id)
        if not history:
            return ""

        lines: List[str] = ["Histórico recente desta conversa:"]
        for item in history:
            role = "Cliente" if item["role"] == "user" else "Plenitude"
            lines.append(f"{role}: {item['content']}")
        return "\n".join(lines)

    def add_message(self, client_id: str, role: str, content: str) -> None:
        if not client_id or not content:
            return
        self._store[client_id].append({"role": role, "content": content.strip()})
