"""Cliente LLM opcional (BYOK / Bring Your Own Key).

Si están configuradas las variables de entorno, el asistente usa un
endpoint OpenAI-compatible (OpenAI, Azure, Ollama, llama.cpp, vLLM…);
si no, las sugerencias caen a las heurísticas deterministas.

Configuración:
    AI_LLM_BASE_URL   p.ej. https://api.openai.com/v1 o http://ollama:11434/v1
    AI_LLM_API_KEY    opcional (Ollama/llama.cpp suelen ignorarla)
    AI_LLM_MODEL      p.ej. gpt-4o-mini, qwen2.5:7b
"""
from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_TIMEOUT = 20


def llm_configured() -> bool:
    return bool(
        getattr(settings, "AI_LLM_BASE_URL", "")
        and getattr(settings, "AI_LLM_MODEL", "")
    )


def chat(system: str, user: str, max_tokens: int = 800) -> str | None:
    """Una llamada chat/completions. Devuelve None ante cualquier error
    (red, 4xx/5xx, payload inesperado) — el caller usa el fallback."""
    if not llm_configured():
        return None
    base = settings.AI_LLM_BASE_URL.rstrip("/")
    headers = {"Content-Type": "application/json"}
    key = getattr(settings, "AI_LLM_API_KEY", "")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        resp = requests.post(
            f"{base}/chat/completions",
            headers=headers,
            json={
                "model": settings.AI_LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": max_tokens,
                "temperature": 0.3,
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:  # noqa: BLE001 - cualquier fallo → fallback
        logger.warning("LLM call failed, usando fallback heurístico: %s", exc)
        return None
