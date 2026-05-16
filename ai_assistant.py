import json
from typing import Any

import httpx

from app.core.config import settings

GIGIMON_CONTEXT = """
Sen Gigimon treyder platformasining AI assistentisan. Quyida platforma imkoniyatlari keltirilgan:

## Sahifalar va imkoniyatlar:
- **Dashboard** - Umumiy ko'rinish: balance, equity, ochiq pozitsiyalar, oxirgi tradelar
- **Trade Qo'shish** - Yangi trade qo'shish (symbol, side, qty, price, exit_price, fee, notes)
- **Trade Tarixi** - Barcha tradelar ro'yxati, Active/Archived tab, bekor qilish
- **Tahlil** - Batafsil metrikalar: Sharpe Ratio, Drawdown, Win Rate, Pattern tahlili, AI tahlil
- **Bildirishnomalar** - Risk ogohlantirishlari va trade bildirishnomalari
- **Sozlamalar** - AI kaliti, provayder (OpenAI/Gemini), rang, currency, initial balance

## Foydalanuvchi qo'llanmasi:
1. Login: /auth/login orqali email+password
2. Trade qo'shish: /add-trade.html da symbol, side, qty, price kiriting
3. Trade tarixi: /history.html da barcha tradelar, cancel qilish mumkin
4. Analytics: /analytics.html da batafsil tahlil, AI analysis
5. AI sozlash: Settings > AI Integration > API key + provider tanlash

## Qoidalar:
- Foydalanuvchining savoliga qisqa, aniq javob ber
- Trading bo'yicha maslahat kerak bo'lsa, risk boshqaruvini eslat
- Agar savol platformaga oid bo'lsa, sahifa yo'nalishini ko'rsat
- Agar foydalanuvchi trade tahlil so'rasa, ma'lumot yetarli bo'lmasa, "Trading statistikangizni Analytics sahifasida ko'rishingiz mumkin" deb ayt
"""


async def _call_ai(system_prompt: str, user_message: str, api_key: str, provider: str) -> str:
    if not api_key:
        return "AI sozlanmagan. Iltimos, Sozlamalar > AI Integration bo'limida API kalitingizni o'rnating."

    if provider == "gemini":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url,
                json={
                    "system_instruction": {"parts": [{"text": system_prompt}]},
                    "contents": [{"parts": [{"text": user_message}]}],
                    "generationConfig": {"temperature": 0.3},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
    else:
        async with httpx.AsyncClient(base_url=settings.ai_base_url, timeout=30.0) as client:
            resp = await client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": settings.ai_model,
                    "temperature": 0.3,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]


async def chat(
    message: str,
    *,
    api_key: str,
    provider: str,
    trades_summary: str = "",
    current_page: str = "",
) -> str:
    system = GIGIMON_CONTEXT
    if trades_summary:
        system += f"\n\nFoydalanuvchining so'nggi tradelari:\n{trades_summary}"
    if current_page:
        system += f"\n\nFoydalanuvchi hozir {current_page} sahifasida."

    return await _call_ai(system, message, api_key, provider)


async def quick_analyze(
    *,
    api_key: str,
    provider: str,
    trade_count: int,
    win_rate: float,
    total_pnl: float,
    recent_streak: str,
) -> str:
    system = "Sen treyder assistentisan. Quyidagi metrikalarga qarab qisqa (2-3 jumla) maslahat ber. O'zbek tilida."
    data = f"Tradelar: {trade_count}, Win rate: {win_rate}%, PnL: ${total_pnl}, So'nggi streak: {recent_streak}"
    return await _call_ai(system, data, api_key, provider)
