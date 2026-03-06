import asyncio
import json
import logging
from openai import AsyncOpenAI
from google import genai
from google.genai import types

from app.core.config import settings

logger = logging.getLogger(__name__)

# Sémaphore global : max 3 appels Gemini simultanés (évite le rate limit free tier)
_GEMINI_SEMAPHORE = asyncio.Semaphore(3)

_MAX_RETRIES = 4


def _is_gemini(model: str) -> bool:
    return model.lower().startswith("gemini")


# ─── Implémentations internes ─────────────────────────────────────────────────

async def _gemini(
    model: str,
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.3,
) -> str:
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    config = types.GenerateContentConfig(
        temperature=temperature,
        system_instruction=system_prompt if system_prompt else None,
    )
    async with _GEMINI_SEMAPHORE:
        for attempt in range(_MAX_RETRIES):
            try:
                response = await client.aio.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
                return response.text or ""
            except Exception as e:
                err_str = str(e)
                is_rate_limit = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str
                if is_rate_limit and attempt < _MAX_RETRIES - 1:
                    wait = 20 * (attempt + 1)
                    logger.warning(
                        f"[GEMINI] 429 rate limit — tentative {attempt + 1}/{_MAX_RETRIES}, "
                        f"retry dans {wait}s..."
                    )
                    await asyncio.sleep(wait)
                else:
                    raise
    return ""


async def _gemini_with_search(
    model: str,
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.3,
) -> str:
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    config = types.GenerateContentConfig(
        temperature=temperature,
        system_instruction=system_prompt if system_prompt else None,
        tools=[types.Tool(google_search=types.GoogleSearch())],
    )
    async with _GEMINI_SEMAPHORE:
        for attempt in range(_MAX_RETRIES):
            try:
                response = await client.aio.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
                return response.text or ""
            except Exception as e:
                err_str = str(e)
                is_rate_limit = "429" in err_str or "RESOURCE_EXHAUSTED" in err_str
                if is_rate_limit and attempt < _MAX_RETRIES - 1:
                    wait = 20 * (attempt + 1)
                    logger.warning(
                        f"[GEMINI SEARCH] 429 rate limit — tentative {attempt + 1}/{_MAX_RETRIES}, "
                        f"retry dans {wait}s..."
                    )
                    await asyncio.sleep(wait)
                else:
                    raise
    return ""


async def _openai(
    model: str,
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.3,
) -> str:
    client = AsyncOpenAI(api_key=settings.CHATGPT_API)
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content or ""


async def _openai_with_search(
    model: str,
    prompt: str,
    system_prompt: str = "",
) -> str:
    client = AsyncOpenAI(api_key=settings.CHATGPT_API)
    kwargs: dict = {
        "model": model,
        "tools": [{"type": "web_search"}],
        "input": prompt,
    }
    if system_prompt:
        kwargs["instructions"] = system_prompt
    response = await client.responses.create(**kwargs)
    return response.output_text or ""


async def _firecrawl_agent(
    prompt: str,
    firecrawl_model: str = "spark-1-mini",
    urls: list[str] | None = None,
) -> str:
    import os
    from agents import Agent, Runner
    from agents.mcp import MCPServerStreamableHttp

    os.environ.setdefault("OPENAI_API_KEY", settings.CHATGPT_API)

    mcp = MCPServerStreamableHttp(
        params={"url": f"https://mcp.firecrawl.dev/{settings.FIRECRAWL_API_KEY}/v2/mcp"},
        client_session_timeout_seconds=300,  # 5 min pour les ops de scraping
    )

    instructions = (
        "Tu es un agent d'enrichissement de données B2B. "
        "Utilise les outils Firecrawl pour trouver les contacts d'une entreprise. "
        "Privilégie l'outil /search pour découvrir les pages pertinentes (page contact, équipe, LinkedIn, etc.), "
        "puis scrape les pages trouvées. "
        "N'utilise JAMAIS /crawl — strictement interdit. "
        "Pour tout appel scrape ou search, utilise TOUJOURS formats=['markdown'] uniquement. "
        "N'utilise JAMAIS les formats json, html, rawHtml, screenshot, ni le paramètre extract. "
        "Réponds UNIQUEMENT avec un objet JSON valide au format : "
        '{"resultats": [{"type": "generique" ou "specialise", "nom": "...", "prenom": "...", "role": "...", "mail": "...", "genre": "Monsieur" ou "Madame" ou null}]} '
        "Sans texte supplémentaire, sans markdown, sans bloc de code."
    )

    full_prompt = prompt
    if urls:
        full_prompt = f"URLs à scraper en priorité : {', '.join(urls)}\n\n{prompt}"

    agent = Agent(
        name="enrichissement-agent",
        instructions=instructions,
        mcp_servers=[mcp],
    )

    logger.info("[FIRECRAWL BROWSER] Agent démarré...")
    try:
        async with mcp:
            result = await Runner.run(agent, full_prompt)
        result_text = result.final_output or ""
        logger.info(f"[FIRECRAWL BROWSER] Résultat reçu ({len(result_text)} chars)")
        return result_text if result_text else '{"resultats": []}'
    except Exception as e:
        logger.error(f"[FIRECRAWL BROWSER] Exception : {e.__class__.__name__}: {e}")
        return '{"resultats": []}'


async def _ovh_vision(
    model: str,
    images_b64: list[str],
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.1,
) -> str:
    client = AsyncOpenAI(
        api_key=settings.OVH_AI_ENDPOINTS_ACCESS_TOKEN,
        base_url=settings.OVH_AI_BASE_URL,
    )
    content: list[dict] = [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}}
        for img in images_b64
    ]
    content.append({"type": "text", "text": prompt})
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": content})
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content or ""


# ─── Dispatchers publics ───────────────────────────────────────────────────────

async def call_ai(
    model: str,
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.3,
) -> str:
    """Dispatcher texte — route vers Gemini ou OpenAI selon le modèle."""
    if _is_gemini(model):
        return await _gemini(model, prompt, system_prompt, temperature)
    return await _openai(model, prompt, system_prompt, temperature)


async def call_ai_with_search(
    model: str,
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.3,
    urls: list[str] | None = None,
) -> str:
    """Dispatcher avec web search — route vers Firecrawl Agent, Gemini Search ou OpenAI web_search."""
    if model.startswith("spark"):
        return await _firecrawl_agent(prompt, model, urls)
    if _is_gemini(model):
        return await _gemini_with_search(model, prompt, system_prompt, temperature)
    return await _openai_with_search(model, prompt, system_prompt)


async def call_ai_vision(
    model: str,
    images_b64: list[str],
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.1,
) -> str:
    """Vision multimodale (OVH/Qwen)."""
    return await _ovh_vision(model, images_b64, prompt, system_prompt, temperature)
