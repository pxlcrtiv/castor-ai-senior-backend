"""Streaming adapter — bridges agent orchestration with SSE streaming.

Uses the configured LLM provider for streaming responses.
Supports OpenAI, Gemini, OpenCode Zen, and Vercel AI Gateway.
"""

from __future__ import annotations

import json
from typing import AsyncIterator

from src.config.llm_provider import LLMConfig, LLMProvider, create_llm_client
from src.security.rbac import rbac, audit_trail
from src.security.prompt_validator import prompt_validator


class StreamAdapter:
    """Stream LLM responses token-by-token via async generator.

    Flow: validate → RBAC check → LLM streaming → audit log
    """

    def __init__(self, config: LLMConfig | None = None):
        self._config = config
        self._client = None

    def _get_client(self):
        """Lazy-init the LLM client."""
        if self._client is None:
            if self._config is None:
                self._config = LLMConfig.from_env()
            self._client = create_llm_client(self._config)
        return self._client

    async def stream(
        self,
        query: str,
        role: str = "analyst",
        session_id: str = "default",
    ) -> AsyncIterator[str]:
        """Stream response tokens for a query.

        Args:
            query: User's natural language query.
            role: User's RBAC role.
            session_id: Session ID for audit trail.

        Yields:
            Response tokens as strings.
        """
        # 1. Security validation
        validation = prompt_validator.validate(query, role)
        if not validation.is_safe:
            audit_trail.log(
                role=role,
                tool="stream_validation",
                query=query[:200],
                allowed=False,
                session_id=session_id,
                denial_reason=validation.reason,
            )
            yield f"⛔ Consulta bloqueada: {validation.reason}"
            return

        # 2. Log stream start
        audit_trail.log(
            role=role,
            tool="stream_response",
            query=query[:200],
            allowed=True,
            session_id=session_id,
        )

        # 3. Stream from configured provider
        try:
            config = self._config or LLMConfig.from_env()

            if config.provider == LLMProvider.GEMINI:
                async for token in self._stream_gemini(query, config):
                    yield token
            else:
                # OpenAI, OpenCode Zen, Vercel AI — all use OpenAI SDK
                async for token in self._stream_openai(query, config):
                    yield token

        except Exception as e:
            yield f"\n\n⚠️ Error: {e}"

    async def _stream_openai(
        self, query: str, config: LLMConfig
    ) -> AsyncIterator[str]:
        """Stream using OpenAI-compatible API (openai, zen, vercel)."""
        from openai import OpenAI

        kwargs = {"api_key": config.api_key}
        if config.base_url:
            kwargs["base_url"] = config.base_url

        client = OpenAI(**kwargs)

        # Use a system prompt for the reconciliation context
        messages = [
            {
                "role": "system",
                "content": (
                    "Eres el agente de conciliación fiscal de la empresa A. "
                    "Responde en español de forma concisa. "
                    "Si consultas datos, usa las herramientas disponibles."
                ),
            },
            {"role": "user", "content": query},
        ]

        # Streaming call
        stream = client.chat.completions.create(
            model=config.model,
            messages=messages,
            temperature=config.temperature,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def _stream_gemini(
        self, query: str, config: LLMConfig
    ) -> AsyncIterator[str]:
        """Stream using Google Gemini API."""
        try:
            import google.generativeai as genai

            genai.configure(api_key=config.api_key)
            model = genai.GenerativeModel(config.model)

            response = model.generate_content(
                query,
                generation_config=genai.types.GenerationConfig(
                    temperature=config.temperature,
                ),
                stream=True,
            )

            for chunk in response:
                if chunk.text:
                    yield chunk.text

        except ImportError:
            yield "⚠️ Gemini SDK not installed. Run: pip install google-generativeai"


def sse_format(token: str) -> str:
    """Format a token as Server-Sent Event data."""
    return f"data: {json.dumps({'token': token})}\n\n"


def sse_done() -> str:
    """SSE stream termination signal."""
    return "data: [DONE]\n\n"
