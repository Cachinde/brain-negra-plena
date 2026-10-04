import time
from typing import List, Tuple
import requests
from config import Config

class CatalogService:
    def __init__(self):
        self._cache_text = ""
        self._cache_at = 0.0

    def get_context(self) -> str:
        now = time.time()
        if self._cache_text and (now - self._cache_at) < Config.CATALOG_CACHE_SECONDS:
            return self._cache_text

        sources: List[Tuple[str, str]] = [
            ("Catalogo / sabores", Config.CATALOG_API_URL),
            ("Precos", Config.PRICES_API_URL),
            ("Horarios e entrega", Config.HOURS_API_URL),
        ]

        blocks: List[str] = []
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
                    blocks.append(f"### {title}\n{body}")
            except Exception as exc:
                blocks.append(f"### {title}\n(temporariamente indisponivel: {exc})")

        self._cache_text = "\n\n".join(blocks)
        self._cache_at = now
        return self._cache_text
