"""Multi-provider LLM configuration.

Supports:
- OpenAI (gpt-4o, gpt-4o-mini, etc.)
- Google Gemini (gemini-2.0-flash, gemini-1.5-pro, etc.)
- OpenCode Zen (OpenAI-compatible endpoint)
- Vercel AI Gateway (OpenAI-compatible, routes to any model)

Provider is selected via LLM_PROVIDER env var. Each provider reads
its own env vars for API key, model, and base URL.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any


class LLMProvider(Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    GEMINI = "gemini"
    OPENCODE_ZEN = "opencode-zen"
    VERCEL_AI = "vercel-ai"


@dataclass
class LLMConfig:
    """Resolved LLM configuration for one provider."""

    provider: LLMProvider
    api_key: str
    model: str
    base_url: str | None = None
    temperature: float = 0.1

    @classmethod
    def from_env(cls) -> LLMConfig:
        """Load config from environment variables."""
        from dotenv import load_dotenv
        load_dotenv()

        provider_str = os.environ.get("LLM_PROVIDER", "openai").lower()

        try:
            provider = LLMProvider(provider_str)
        except ValueError:
            raise ValueError(
                f"Unknown provider '{provider_str}'. "
                f"Supported: {[p.value for p in LLMProvider]}"
            )

        loaders = {
            LLMProvider.OPENAI: cls._load_openai,
            LLMProvider.GEMINI: cls._load_gemini,
            LLMProvider.OPENCODE_ZEN: cls._load_opencode_zen,
            LLMProvider.VERCEL_AI: cls._load_vercel_ai,
        }
        return loaders[provider]()

    @classmethod
    def _load_openai(cls) -> LLMConfig:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider")
        return cls(
            provider=LLMProvider.OPENAI,
            api_key=api_key,
            model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
            temperature=float(os.environ.get("LLM_TEMPERATURE", "0.1")),
        )

    @classmethod
    def _load_gemini(cls) -> LLMConfig:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required for Gemini provider")
        return cls(
            provider=LLMProvider.GEMINI,
            api_key=api_key,
            model=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
            temperature=float(os.environ.get("LLM_TEMPERATURE", "0.1")),
        )

    @classmethod
    def _load_opencode_zen(cls) -> LLMConfig:
        api_key = os.environ.get("ZEN_API_KEY", "")
        if not api_key:
            raise ValueError("ZEN_API_KEY is required for OpenCode Zen provider")
        base_url = os.environ.get("ZEN_BASE_URL", "")
        if not base_url:
            raise ValueError("ZEN_BASE_URL is required for OpenCode Zen provider")
        return cls(
            provider=LLMProvider.OPENCODE_ZEN,
            api_key=api_key,
            model=os.environ.get("ZEN_MODEL", "zen-pro"),
            base_url=base_url,
            temperature=float(os.environ.get("LLM_TEMPERATURE", "0.1")),
        )

    @classmethod
    def _load_vercel_ai(cls) -> LLMConfig:
        api_key = os.environ.get("VERCEL_AI_API_KEY", "")
        if not api_key:
            raise ValueError("VERCEL_AI_API_KEY is required for Vercel AI Gateway")
        base_url = os.environ.get(
            "VERCEL_AI_BASE_URL", "https://ai-gateway.vercel.com/v1"
        )
        return cls(
            provider=LLMProvider.VERCEL_AI,
            api_key=api_key,
            model=os.environ.get("VERCEL_AI_MODEL", "gpt-4o"),
            base_url=base_url,
            temperature=float(os.environ.get("LLM_TEMPERATURE", "0.1")),
        )


def create_llm_client(config: LLMConfig) -> Any:
    """Create the appropriate SDK client for the provider.

    OpenAI, OpenCode Zen, and Vercel AI all use the OpenAI SDK
    (they're OpenAI-compatible). Only Gemini uses its own SDK.
    """
    if config.provider in (
        LLMProvider.OPENAI,
        LLMProvider.OPENCODE_ZEN,
        LLMProvider.VERCEL_AI,
    ):
        from openai import OpenAI

        kwargs = {"api_key": config.api_key}
        if config.base_url:
            kwargs["base_url"] = config.base_url
        return OpenAI(**kwargs)

    elif config.provider == LLMProvider.GEMINI:
        try:
            import google.generativeai as genai

            genai.configure(api_key=config.api_key)
            return genai.GenerativeModel(config.model)
        except ImportError:
            raise ImportError(
                "pip install google-generativeai  # required for Gemini provider"
            )

    raise ValueError(f"No client factory for {config.provider}")


def get_autogen_llm_config(config: LLMConfig) -> dict:
    """Build AutoGen-compatible LLM config from LLMConfig.

    AutoGen expects: {"config_list": [{"model": ..., "api_key": ..., "base_url": ...}]}
    """
    entry: dict[str, Any] = {
        "model": config.model,
        "api_key": config.api_key,
    }
    if config.base_url:
        entry["base_url"] = config.base_url

    return {"config_list": [entry]}
