import logging
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


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
        "tools": [{"type": "web_search_preview"}],
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
    """chat.completions générique (Perplexity, modèles custom)."""
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
