import json
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings


class AIResult(dict):
    pass


async def _call_openai(*, key: str, system: str, user_content: str) -> dict:
    async with httpx.AsyncClient(base_url=settings.ai_base_url, timeout=30.0) as client:
        resp = await client.post(
            "/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": settings.ai_model,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)


async def _call_gemini(*, key: str, system: str, user_content: str) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            url,
            json={
                "system_instruction": {"parts": [{"text": system}]},
                "contents": [{"parts": [{"text": user_content}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "responseMimeType": "application/json",
                },
            },
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.7, min=0.7, max=4))
async def generate_insight(*, report_payload: dict[str, Any], api_key: str = "", provider: str = "") -> AIResult:
    """
    Cloud AI call (OpenAI or Gemini). Returns:
      - advice_markdown
      - scores (dict)
      - actions (list)
      
    api_key overrides settings.ai_api_key if provided.
    provider overrides settings.ai_provider if provided.
    """
    key = api_key or settings.ai_api_key
    if not key:
        return AIResult(
            advice_markdown="AI API kaliti sozlanmagan. Sozlamalar > AI Integration bo'limida kalitingizni o'rnating.",
            scores={"intizom": 0, "risk_boshqaruvi": 0, "barqarorlik": 0, "pattern_aniqlash": 0, "sizing": 0},
            actions=["AI API kalitini sozlamalar sahifasida o'rnating", "Kalit o'rnatilgach, bu sahifani qayta yuklang"],
            model=settings.ai_model,
        )

    system = (
        "You are an elite trading coach. Analyze the trader's performance data below. "
        "Return a STRICT JSON object with these exact keys:\n"
        "  - advice_markdown (string): Detailed analysis in markdown format (Uzbek language). Cover strengths, weaknesses, patterns, and specific recommendations.\n"
        "  - scores (object): Scores out of 100 for: discipline, risk_management, consistency, pattern_recognition, sizing.\n"
        "  - actions (array of strings): 3-5 specific actionable steps the trader should take next.\n"
    )
    user_content = json.dumps(report_payload, ensure_ascii=False, default=str)

    prov = provider or settings.ai_provider
    if prov == "gemini":
        parsed = await _call_gemini(key=key, system=system, user_content=user_content)
    else:
        parsed = await _call_openai(key=key, system=system, user_content=user_content)

    return AIResult(
        advice_markdown=parsed.get("advice_markdown", ""),
        scores=parsed.get("scores", {}),
        actions=parsed.get("actions", []),
        model=settings.ai_model,
    )

