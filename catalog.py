import time
from typing import List, Tuple

import requests

from config import Config


class CatalogService:
    """
    Preços oficiais ficam sempre no contexto.
    APIs externas (se configuradas) acrescentam dados sem substituir os preços.
    """

    def __init__(self):
        self._cache_text = ""
        self._cache_at = 0.0

    def get_context(self) -> str:
        blocks: List[str] = [Config.OFFICIAL_PRICES]

        now = time.time()
        if self._cache_text and (now - self._cache_at) < Config.CATALOG_CACHE_SECONDS:
            if self._cache_text:
                blocks.append(self._cache_text)
            return "\n\n".join(blocks)

        sources: List[Tuple[str, str]] = [
            ("Catálogo extra / sabores", Config.CATALOG_API_URL),
            ("Preços API (só se não contradisser os oficiais)", Config.PRICES_API_URL),
            ("Horários e entrega", Config.HOURS_API_URL),
        ]

        api_blocks: List[str] = []
        headers = {}
        if Config.BUSINESS_API_TOKEN:
            headers["Authorization"] = f"Bearer {Config.BUSINESS_API_TOKEN}"

        for title, url in sources:
            if not url:
                continue
            try:
                response = requests.get(url, headers=headers, timeout=8)
                response.raise_for_status()
                body = response.text.strip()[:4000]
                if body:
                    api_blocks.append(f"### {title}\n{body}")
            except Exception as exc:
                api_blocks.append(f"### {title}\n(temporariamente indisponível: {exc})")

        self._cache_text = "\n\n".join(api_blocks)
        self._cache_at = now
        if self._cache_text:
            blocks.append(self._cache_text)
        return "\n\n".join(blocks)
