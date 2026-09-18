"""Tests for multi-provider LLM configuration.

Seams under test:
1. LLMConfig.from_env() → config for the selected provider
2. Provider switching (openai, gemini, opencode-zen, vercel-ai)
3. Fallback behavior when API key is missing
4. AutoGen config generation
"""

import os
import pytest
from unittest.mock import patch

from src.config.llm_provider import LLMProvider, LLMConfig, create_llm_client, get_autogen_llm_config


# Clean env before each test to prevent leaks
@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Remove all LLM env vars between tests and block .env reload."""
    keys = [
        "LLM_PROVIDER", "OPENAI_API_KEY", "OPENAI_MODEL",
        "GEMINI_API_KEY", "GEMINI_MODEL",
        "ZEN_API_KEY", "ZEN_BASE_URL", "ZEN_MODEL",
        "VERCEL_AI_API_KEY", "VERCEL_AI_BASE_URL", "VERCEL_AI_MODEL",
        "LLM_TEMPERATURE",
    ]
    for k in keys:
        monkeypatch.delenv(k, raising=False)
    # Block load_dotenv from re-reading .env during tests
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **kw: None)


# ---------------------------------------------------------------------------
# Provider enum
# ---------------------------------------------------------------------------

class TestLLMProvider:

    def test_all_providers(self):
        providers = [p.value for p in LLMProvider]
        assert "openai" in providers
        assert "gemini" in providers
        assert "opencode-zen" in providers
        assert "vercel-ai" in providers


# ---------------------------------------------------------------------------
# LLM config
# ---------------------------------------------------------------------------

class TestLLMConfig:

    def test_openai_config(self):
        os.environ["LLM_PROVIDER"] = "openai"
        os.environ["OPENAI_API_KEY"] = "sk-test"
        os.environ["OPENAI_MODEL"] = "gpt-4o"
        config = LLMConfig.from_env()
        assert config.provider == LLMProvider.OPENAI
        assert config.api_key == "sk-test"
        assert config.model == "gpt-4o"
        assert config.base_url is None

    def test_gemini_config(self):
        os.environ["LLM_PROVIDER"] = "gemini"
        os.environ["GEMINI_API_KEY"] = "AIza-test"
        os.environ["GEMINI_MODEL"] = "gemini-2.0-flash"
        config = LLMConfig.from_env()
        assert config.provider == LLMProvider.GEMINI
        assert config.api_key == "AIza-test"
        assert config.model == "gemini-2.0-flash"

    def test_opencode_zen_config(self):
        os.environ["LLM_PROVIDER"] = "opencode-zen"
        os.environ["ZEN_API_KEY"] = "zen-test"
        os.environ["ZEN_BASE_URL"] = "https://api.zen.example.com/v1"
        os.environ["ZEN_MODEL"] = "zen-pro"
        config = LLMConfig.from_env()
        assert config.provider == LLMProvider.OPENCODE_ZEN
        assert config.api_key == "zen-test"
        assert config.base_url == "https://api.zen.example.com/v1"
        assert config.model == "zen-pro"

    def test_vercel_ai_config(self):
        os.environ["LLM_PROVIDER"] = "vercel-ai"
        os.environ["VERCEL_AI_API_KEY"] = "vercel-test"
        os.environ["VERCEL_AI_BASE_URL"] = "https://ai-gateway.vercel.com/v1"
        os.environ["VERCEL_AI_MODEL"] = "anthropic/claude-3.5-sonnet"
        config = LLMConfig.from_env()
        assert config.provider == LLMProvider.VERCEL_AI
        assert config.api_key == "vercel-test"
        assert config.base_url == "https://ai-gateway.vercel.com/v1"
        assert config.model == "anthropic/claude-3.5-sonnet"

    def test_vercel_ai_defaults(self):
        os.environ["LLM_PROVIDER"] = "vercel-ai"
        os.environ["VERCEL_AI_API_KEY"] = "vercel-test"
        config = LLMConfig.from_env()
        assert config.base_url == "https://ai-gateway.vercel.com/v1"
        assert config.model == "gpt-4o"

    def test_defaults_to_openai(self):
        os.environ["OPENAI_API_KEY"] = "sk-test"
        config = LLMConfig.from_env()
        assert config.provider == LLMProvider.OPENAI

    def test_unknown_provider_raises(self):
        os.environ["LLM_PROVIDER"] = "anthropic"
        with pytest.raises(ValueError, match="Unknown provider"):
            LLMConfig.from_env()

    def test_missing_api_key_raises(self):
        os.environ["LLM_PROVIDER"] = "gemini"
        # No GEMINI_API_KEY set
        with pytest.raises(ValueError, match="required"):
            LLMConfig.from_env()


# ---------------------------------------------------------------------------
# AutoGen config generation
# ---------------------------------------------------------------------------

class TestAutogenConfig:

    def test_openai_autogen_config(self):
        os.environ["LLM_PROVIDER"] = "openai"
        os.environ["OPENAI_API_KEY"] = "sk-test"
        os.environ["OPENAI_MODEL"] = "gpt-4o"
        config = LLMConfig.from_env()
        ac = get_autogen_llm_config(config)
        assert "config_list" in ac
        assert ac["config_list"][0]["model"] == "gpt-4o"
        assert ac["config_list"][0]["api_key"] == "sk-test"

    def test_vercel_ai_autogen_config_includes_base_url(self):
        os.environ["LLM_PROVIDER"] = "vercel-ai"
        os.environ["VERCEL_AI_API_KEY"] = "vercel-test"
        os.environ["VERCEL_AI_BASE_URL"] = "https://ai-gateway.vercel.com/v1"
        config = LLMConfig.from_env()
        ac = get_autogen_llm_config(config)
        assert ac["config_list"][0]["base_url"] == "https://ai-gateway.vercel.com/v1"

    def test_openai_no_base_url_in_config(self):
        os.environ["LLM_PROVIDER"] = "openai"
        os.environ["OPENAI_API_KEY"] = "sk-test"
        config = LLMConfig.from_env()
        ac = get_autogen_llm_config(config)
        assert "base_url" not in ac["config_list"][0]


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------

class TestCreateClient:

    def test_openai_client(self):
        os.environ["LLM_PROVIDER"] = "openai"
        os.environ["OPENAI_API_KEY"] = "sk-test"
        config = LLMConfig.from_env()
        client = create_llm_client(config)
        assert client is not None

    def test_vercel_ai_uses_openai_sdk(self):
        os.environ["LLM_PROVIDER"] = "vercel-ai"
        os.environ["VERCEL_AI_API_KEY"] = "vercel-test"
        os.environ["VERCEL_AI_BASE_URL"] = "https://ai-gateway.vercel.com/v1"
        config = LLMConfig.from_env()
        client = create_llm_client(config)
        assert client is not None

    def test_opencode_zen_uses_openai_sdk(self):
        os.environ["LLM_PROVIDER"] = "opencode-zen"
        os.environ["ZEN_API_KEY"] = "zen-test"
        os.environ["ZEN_BASE_URL"] = "https://api.zen.example.com/v1"
        config = LLMConfig.from_env()
        client = create_llm_client(config)
        assert client is not None
