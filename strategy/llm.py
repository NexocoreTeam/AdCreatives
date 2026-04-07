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
    kwargs: dict = {"model": "claude-sonnet-4-20250514", "max_tokens": max_tokens, "messages": messages}
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
