"""Weekly brief generation via Groq (llama-3.1-8b-instant).

Replaces the original Claude API plan with a free-tier alternative:
  - Groq free tier: 14,400 req/day, 30 req/min — sufficient for household use
  - Model: llama-3.1-8b-instant (~1-2 s latency)
  - Falls back to a structured template when GROQ_API_KEY is not configured

The weekly carbon data (~500 tokens) fits in a single prompt — no RAG / vector
search needed for this use case.
"""
import hashlib
import json
import logging

from cachetools import TTLCache

from app.config import settings

log = logging.getLogger(__name__)

# Cache successful briefs so repeated /api/weekly hits don't re-spend Groq quota.
# Keyed by a digest of (city, days payload); upstream carbon data is itself
# cached ~30 min, so identical inputs recur. 30-min TTL keeps it fresh.
_brief_cache: TTLCache = TTLCache(maxsize=256, ttl=1800)


def _cache_key(city: str, days: list) -> str:
    blob = json.dumps([city, days], sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def _template_brief(city: str, days: list) -> str:
    scored = [d for d in days if d.get("avg_carbon_score", 0) > 0]
    if not scored:
        return f"Weekly carbon forecast for {city} is available above."

    best = max(scored, key=lambda d: d["avg_carbon_score"])
    worst = min(scored, key=lambda d: d["avg_carbon_score"])

    parts = [
        f"{best['day_label']} is the best day for energy-intensive tasks "
        f"(average carbon score {best['avg_carbon_score']:.0f}/100)."
    ]
    if best["day_label"] != worst["day_label"]:
        parts.append(
            f"Avoid high-consumption tasks on {worst['day_label']} "
            f"when the grid is more carbon-intensive (score {worst['avg_carbon_score']:.0f}/100)."
        )
    parts.append(
        "Set the GROQ_API_KEY environment variable to enable AI-generated personalised insights."
    )
    return " ".join(parts)


async def generate_brief(city: str, days: list, carbon_label: str) -> str:
    """Generate a natural-language weekly brief.

    Args:
        city: Display name, e.g. "London".
        days: List of dicts with keys day_label, avg_carbon_score, tasks.
        carbon_label: Short description of the data source.

    Returns:
        A 100-150 word brief in British English prose.
    """
    api_key = settings.groq_api_key
    if not api_key:
        return _template_brief(city, days)

    key = _cache_key(city, days)
    cached = _brief_cache.get(key)
    if cached is not None:
        return cached

    try:
        from groq import AsyncGroq

        lines = [f"{city} — 7-day carbon & scheduling outlook", f"Data: {carbon_label}", ""]
        for d in days:
            task_parts = []
            for t in d.get("tasks", []):
                if t.get("best_start"):
                    task_parts.append(f'{t["task_label"]}: score {t["score"]:.0f}/100')
                else:
                    task_parts.append(f'{t["task_label"]}: no window')
            tasks_str = " | ".join(task_parts) if task_parts else "no tasks"
            lines.append(
                f"- {d['day_label']} (avg carbon score {d['avg_carbon_score']:.0f}/100): {tasks_str}"
            )

        data_block = "\n".join(lines)
        prompt = (
            f"You are an energy advisor for a smart home planner app.\n\n"
            f"Based on this 7-day forecast data:\n\n{data_block}\n\n"
            f"Write a concise weekly brief (100–150 words) for a household in {city}. "
            f"Highlight the best day(s) to run high-energy appliances, note any particularly "
            f"clean or carbon-intensive periods, and give one practical tip. "
            f"Write in British English, flowing prose, no bullet points or headers."
        )

        groq_client = AsyncGroq(api_key=api_key)
        chat = await groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.6,
        )
        brief = chat.choices[0].message.content.strip()
        _brief_cache[key] = brief
        return brief

    except Exception as exc:
        log.warning("Groq brief generation failed: %s", exc)
        return _template_brief(city, days)
