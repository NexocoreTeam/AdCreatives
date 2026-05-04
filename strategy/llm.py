"""Shared LLM client utilities for the strategy layer."""

from __future__ import annotations

import os

import anthropic
import openai


def get_anthropic_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set. See .env.example")
    return anthropic.Anthropic(api_key=api_key)


def get_openai_client() -> openai.OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY not set. See .env.example")
    return openai.OpenAI(api_key=api_key)


def claude_complete(prompt: str, system: str = "", max_tokens: int = 4096) -> str:
    """Simple Claude completion wrapper."""
    client = get_anthropic_client()
    messages = [{"role": "user", "content": prompt}]
    kwargs: dict = {"model": "claude-sonnet-4-6", "max_tokens": max_tokens, "messages": messages}
    if system:
        kwargs["system"] = system
    response = client.messages.create(**kwargs)
    return response.content[0].text


def gpt4o_complete(prompt: str, system: str = "", max_tokens: int = 4096) -> str:
    """Simple GPT-4o completion wrapper."""
    client = get_openai_client()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


def gpt4o_vision(prompt: str, image_url: str, system: str = "") -> str:
    """GPT-4o with vision — analyze an image."""
    client = get_openai_client()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_url}},
        ],
    })
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=4096,
    )
    return response.choices[0].message.content or ""


def claude_vision(prompt: str, image_url: str, system: str = "", max_tokens: int = 1024) -> str:
    """Claude with vision — analyze an image via URL.

    Same API key as the rest of the strategy layer (no separate OpenAI key
    needed). Uses Sonnet 4.6.
    """
    client = get_anthropic_client()
    content = [
        {"type": "image", "source": {"type": "url", "url": image_url}},
        {"type": "text", "text": prompt},
    ]
    kwargs: dict = {
        "model": "claude-sonnet-4-6",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": content}],
    }
    if system:
        kwargs["system"] = system
    response = client.messages.create(**kwargs)
    return response.content[0].text


def get_openrouter_client() -> openai.OpenAI | None:
    """Return an OpenAI-compatible client pointed at OpenRouter.

    Returns None if OPENROUTER_API_KEY is unset, so callers can fall back
    to claude_vision or gpt4o_vision.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None
    return openai.OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )


def gemini_vision(
    prompt: str,
    image_urls: list[str],
    system: str = "",
    max_tokens: int = 2048,
    model: str = "google/gemini-2.5-pro",
) -> str:
    """Gemini vision via OpenRouter. Accepts MULTIPLE image URLs in one call —
    much better than single-image vision for visual-identity capture across
    logo + product shots + hero images.

    Falls back to claude_vision (single image) if OPENROUTER_API_KEY is unset.
    """
    client = get_openrouter_client()
    if client is None:
        # Fallback: use Claude on the first image only
        first = image_urls[0] if image_urls else ""
        if not first:
            raise ValueError("No image URLs provided")
        fallback_prompt = (
            prompt
            + f"\n\n(Note: only 1 of {len(image_urls)} images shown; OPENROUTER_API_KEY not set)"
        )
        return claude_vision(fallback_prompt, first, system=system, max_tokens=max_tokens)

    content = [{"type": "text", "text": prompt}]
    for url in image_urls:
        content.append({"type": "image_url", "image_url": {"url": url}})

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": content})

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        extra_headers={
            "HTTP-Referer": "https://github.com/NexocoreTeam/AdCreatives",
            "X-Title": "AdCreatives",
        },
    )
    return response.choices[0].message.content or ""
