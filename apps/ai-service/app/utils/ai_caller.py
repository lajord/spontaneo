import asyncio
import logging
from openai import AsyncOpenAI
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Sémaphore global : max 3 appels Gemini simultanés (évite le rate limit free tier)
_GEMINI_SEMAPHORE = asyncio.Semaphore(3)


async def call_ai_gemini(
    model: str,
    prompt: str,
    system_prompt: str = "",
    api_key: str | None = None,
    temperature: float = 0.3,
    max_retries: int = 4,
) -> str:
    """Google Gemini via google-genai SDK (async) avec retry + backoff sur 429."""
    client = genai.Client(api_key=api_key)

    config = types.GenerateContentConfig(
        temperature=temperature,
        system_instruction=system_prompt if system_prompt else None,
    )

    async with _GEMINI_SEMAPHORE:
        for attempt in range(max_retries):
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
                if is_rate_limit and attempt < max_retries - 1:
                    # Backoff : 20s, 40s, 60s (aligné sur la fenêtre Gemini free tier)
                    wait = 20 * (attempt + 1)
                    logger.warning(
                        f"[GEMINI] 429 rate limit — tentative {attempt + 1}/{max_retries}, "
                        f"retry dans {wait}s..."
                    )
                    await asyncio.sleep(wait)
                else:
                    raise

    return ""


async def call_ai_with_web_search(
    model: str,
    prompt: str,
    instructions: str = "",
    api_key: str | None = None,
) -> str:
    """Responses API + web_search tool (enrichissement)."""
    client = AsyncOpenAI(api_key=api_key)

    kwargs: dict = {
        "model": model,
        "tools": [{"type": "web_search"}],
        "input": prompt,
    }
    if instructions:
        kwargs["instructions"] = instructions

    response = await client.responses.create(**kwargs)
    return response.output_text or ""


async def call_ai_responses(
    model: str,
    prompt: str,
    instructions: str = "",
    api_key: str | None = None,
) -> str:
    """Responses API sans web search (génération de texte)."""
    client = AsyncOpenAI(api_key=api_key)

    kwargs: dict = {
        "model": model,
        "input": prompt,
    }
    if instructions:
        kwargs["instructions"] = instructions

    response = await client.responses.create(**kwargs)
    return response.output_text or ""


async def call_ai_with_vision(
    model: str,
    images_b64: list[str],
    prompt: str,
    system_prompt: str = "",
    base_url: str | None = None,
    api_key: str | None = None,
    temperature: float = 0.1,
) -> str:
    """Vision via chat.completions (OVH/Qwen)."""
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

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


async def call_ai(
    model: str,
    prompt: str,
    system_prompt: str = "",
    base_url: str | None = None,
    api_key: str | None = None,
    temperature: float = 0.3,
) -> str:
    """chat.completions générique (OpenAI, modèles custom)."""
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

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
