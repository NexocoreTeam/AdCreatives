"""Shared LLM client utilities for the strategy layer."""

from __future__ import annotations

import json
import os
import time

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


# Transient-error types that warrant a retry. Anthropic-specific errors plus
# generic httpx connection issues. APIStatusError covers 429/500/502/503/504;
# we let the SDK's `.status_code` attribute decide whether it's worth retrying.
_RETRYABLE_STATUSES = {408, 425, 429, 500, 502, 503, 504, 529}


def _is_retryable(exc: Exception) -> bool:
    """Decide whether an Anthropic SDK error is worth retrying.

    Returns True for rate-limit, server-error, and overload responses, plus
    network-layer hiccups. Returns False for auth errors, content-policy
    rejections, and other 4xx that won't change on retry."""
    status = getattr(exc, "status_code", None)
    if status is None:
        # Network / timeout errors don't have a status code — these are
        # almost always transient.
        msg = str(exc).lower()
        return any(s in msg for s in (
            "timeout", "connection", "temporarily", "overloaded", "503", "504"
        ))
    return status in _RETRYABLE_STATUSES


def claude_complete(
    prompt: str,
    system: str = "",
    max_tokens: int = 4096,
    *,
    max_retries: int = 5,
) -> str:
    """Simple Claude completion wrapper with automatic retry on transient
    errors.

    Retries up to `max_retries` times with exponential backoff (1, 2, 4,
    8, 16 seconds = 31s total at default max_retries=5) on rate-limit (429),
    server-error (5xx), overloaded (529), and network hiccups. Auth /
    content-policy errors raise immediately — those won't change on retry.

    Default was bumped from 3 to 5 on 2026-05-22 after Anthropic 529
    "Overloaded" errors began surfacing in remix_continue runs. 529s often
    last a couple of minutes when Anthropic's capacity is constrained;
    1+2+4=7s of backoff was sometimes not enough to ride them out.
    31s of total backoff catches the typical short overload window
    without making the operator wait absurdly long if it really is broken.

    When retries exhaust on a 529, raises with a user-friendly message
    pointing at https://status.anthropic.com and explaining how to
    resume manually."""
    client = get_anthropic_client()
    messages = [{"role": "user", "content": prompt}]
    kwargs: dict = {"model": "claude-sonnet-4-6", "max_tokens": max_tokens, "messages": messages}
    if system:
        kwargs["system"] = system

    # SDK requires streaming for requests that might exceed the 10-minute
    # non-streaming timeout. The threshold lands around ~30K output tokens for
    # Sonnet, so we switch to streaming above 20K to leave margin. Streaming is
    # transparent here — we just collect the text and return the final string.
    use_streaming = max_tokens > 20000

    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            if use_streaming:
                with client.messages.stream(**kwargs) as stream:
                    for _ in stream.text_stream:
                        pass  # consume the stream; the final message is what we return
                    final = stream.get_final_message()
                    return final.content[0].text
            response = client.messages.create(**kwargs)
            return response.content[0].text
        except Exception as e:
            last_exc = e
            if attempt == max_retries or not _is_retryable(e):
                # Friendlier error on terminal 529 (Anthropic overload) —
                # tells the operator this is an Anthropic capacity issue,
                # not a code bug, and how to recover.
                status = getattr(e, "status_code", None)
                msg = str(e).lower()
                is_overload = (status == 529) or ("overloaded" in msg) or ("529" in msg)
                if is_overload and attempt == max_retries:
                    raise RuntimeError(
                        f"Anthropic API is currently overloaded (HTTP 529). "
                        f"Tried {max_retries + 1} times with exponential "
                        f"backoff (31s total) and the API never recovered. "
                        f"This is a temporary Anthropic capacity issue, not "
                        f"a code bug. Check https://status.anthropic.com and "
                        f"retry the same command in a few minutes — your "
                        f"analyze-only / mapping work is on disk and will "
                        f"resume from where it stopped."
                    ) from e
                raise
            wait_s = 2 ** attempt  # 1, 2, 4, 8, 16 seconds at max_retries=5
            status = getattr(e, "status_code", "?")
            print(
                f"  [claude_complete] retryable error (status={status}, "
                f"attempt {attempt + 1}/{max_retries + 1}): {str(e)[:120]}. "
                f"Sleeping {wait_s}s.",
                flush=True,
            )
            time.sleep(wait_s)
    # Defensive — shouldn't reach here because the final attempt re-raises.
    raise last_exc if last_exc else RuntimeError("claude_complete: no attempts made")


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


def openai_structured_json(
    prompt: str,
    *,
    system: str = "",
    schema: dict,
    schema_name: str = "structured_output",
    max_tokens: int = 3000,
    model: str | None = None,
) -> dict:
    """Return JSON from an OpenAI model, using JSON schema when available.

    The default model can be overridden with OPENAI_PROMPT_WRITER_MODEL. A
    JSON-object fallback keeps older SDK/model combos usable if strict schema
    mode is rejected by the API.
    """
    client = get_openai_client()
    chosen_model = model or os.environ.get("OPENAI_PROMPT_WRITER_MODEL") or "gpt-4o"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs = {
        "model": chosen_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "schema": schema,
                "strict": True,
            },
        },
    }
    try:
        response = client.chat.completions.create(**kwargs)
    except Exception:
        kwargs["response_format"] = {"type": "json_object"}
        response = client.chat.completions.create(**kwargs)

    text = response.choices[0].message.content or "{}"
    return json.loads(text)


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


def sniff_image_mime(data: bytes) -> str | None:
    """Detect an image's MIME type from its magic bytes.

    Extensions lie: Foreplay serves PNG assets behind .jpg-looking URLs, and
    Anthropic 400s when the declared media type doesn't match the bytes
    (live failure: Vessi ad 544513423796604, 2026-07-08). Returns None for
    anything that isn't a recognized image format.
    """
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:4] in (b"GIF8",):
        return "image/gif"
    return None


def vision_complete(
    prompt: str,
    image: str,
    *,
    system: str = "",
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 2048,
) -> str:
    """Vision completion for a local image file OR URL, routed by model name.

    Routing: `claude-*` → Anthropic, `gpt-*` → OpenAI, anything with a `/`
    (e.g. `google/gemini-2.5-pro`) → OpenRouter. Local files are inlined as
    base64 so callers don't need a public URL. Built for the ad-analyzer
    model bake-off, where the same call must run against several vendors.
    """
    import base64
    from pathlib import Path

    is_url = image.startswith(("http://", "https://"))
    if not is_url:
        path = Path(image)
        data = path.read_bytes()
        suffix = path.suffix.lower().lstrip(".")
        # Trust the bytes over the extension — mismatches get rejected by
        # the vision APIs.
        mime = sniff_image_mime(data) or f"image/{'jpeg' if suffix in ('jpg', 'jpeg') else suffix}"
        b64 = base64.standard_b64encode(data).decode()

    if model.startswith("claude"):
        client = get_anthropic_client()
        if is_url:
            source: dict = {"type": "url", "url": image}
        else:
            source = {"type": "base64", "media_type": mime, "data": b64}
        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": source},
                {"type": "text", "text": prompt},
            ]}],
        }
        if system:
            kwargs["system"] = system
        return client.messages.create(**kwargs).content[0].text

    # OpenAI-compatible path (OpenAI direct, or any vendor via OpenRouter).
    if "/" in model:
        client = get_openrouter_client()
        if client is None:
            raise EnvironmentError(
                f"Model '{model}' needs OPENROUTER_API_KEY (not set). See .env.example")
    else:
        client = get_openai_client()
    url = image if is_url else f"data:{mime};base64,{b64}"
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": url}},
    ]})
    response = client.chat.completions.create(
        model=model, messages=messages, max_tokens=max_tokens)
    return response.choices[0].message.content or ""


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
