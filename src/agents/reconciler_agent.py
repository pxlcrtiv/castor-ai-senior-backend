"""Main Reconciliation Agent using LangChain with ReAct pattern.

Implements the multi-agent orchestration with:
- ReAct reasoning loop (Reasoning + Acting)
- Tool chaining for complex queries
- Session memory management
- Guardrails for financial data safety
"""

import asyncio
from typing import AsyncIterator, Any

from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferWindowMemory
from langchain.tools import Tool

from src.tools.erp_tools import (
    get_erp_data,
    calculate_tax_discrepancy,
    list_pending_invoices,
)
from src.rag.vector_store import ERPRAGPipeline, RAGQuery
from src.security.prompt_validator import prompt_validator, ValidationResult
from src.config.settings import settings


# ---------------------------------------------------------------------------
# Tool wrappers for LangChain
# ---------------------------------------------------------------------------

def _wrap_erp_lookup(query: str) -> str:
    """Synchronous wrapper for ERP data lookup."""
    result = asyncio.get_event_loop().run_until_complete(get_erp_data(query))
    if result["success"]:
        data = result["data"]
        return (
            f"Factura #{data['order_id']}:\n"
            f"  Proveedor: {data['supplier']}\n"
            f"  Monto: ${data['amount']:,.2f} MXN\n"
            f"  Impuesto: ${data['tax']:,.2f} MXN\n"
            f"  Región: {data['region']}\n"
            f"  Estado: {data['status']}\n"
            f"  Discrepancia: ${data.get('discrepancy', 0):,.2f}\n"
            f"  Motivo: {data.get('discrepancy_reason', 'N/A')}"
        )
    return result["error"]


def _wrap_tax_calc(query: str) -> str:
    """Parse and calculate tax discrepancy."""
    # Simple parsing: "amount|region" format
    parts = query.split("|")
    if len(parts) != 2:
        return "Formato esperado: 'monto|region' (ej: '15420.50|CDMX')"
    amount = float(parts[0].strip())
    region = parts[1].strip()
    result = asyncio.get_event_loop().run_until_complete(
        calculate_tax_discrepancy(amount, region)
    )
    if result["success"]:
        return (
            f"Cálculo fiscal para {region}:\n"
            f"  Monto base: ${result['base_amount']:,.2f}\n"
            f"  Tasa IVA: {result['tax_rate'] * 100:.0f}%\n"
            f"  Impuesto esperado: ${result['expected_tax']:,.2f}\n"
            f"  Fórmula: {result['formula']}"
        )
    return "Error en el cálculo fiscal"


def _wrap_pending_invoices(_query: str) -> str:
    """List pending invoices."""
    result = asyncio.get_event_loop().run_until_complete(list_pending_invoices())
    if result["success"]:
        lines = [f"Facturas pendientes ({result['count']}):"]
        for inv in result["invoices"]:
            lines.append(
                f"  - #{inv['order_id']}: ${inv['amount']:,.2f} "
                f"({inv['status']}) - {inv['supplier']}"
            )
        return "\n".join(lines)
    return "Error al consultar facturas pendientes"


def _wrap_rag_lookup(query: str) -> str:
    """Query the RAG pipeline for regulations."""
    pipeline = ERPRAGPipeline()
    pipeline.initialize()
    results = pipeline.query(RAGQuery(query=query, year=2024))
    if not results:
        return "No se encontraron normativas relevantes."
    lines = ["Resultados de normativas:"]
    for i, r in enumerate(results, 1):
        lines.append(f"  {i}. [{r['metadata'].get('source', '?')}]")
        lines.append(f"     {r['content'][:200]}...")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

def build_tools() -> list[Tool]:
    """Build the tool set for the reconciliation agent."""
    return [
        Tool(
            name="get_erp_data",
            func=_wrap_erp_lookup,
            description=(
                "Consulta datos de una factura en el sistema ERP. "
                "Input: número de orden (ej: '4402'). "
                "Devuelve detalles del proveedor, montos, impuestos y discrepancias."
            ),
        ),
        Tool(
            name="calculate_tax_discrepancy",
            func=_wrap_tax_calc,
            description=(
                "Calcula el impuesto esperado para un monto y región. "
                "Input: 'monto|region' (ej: '15420.50|CDMX'). "
                "Compara con el impuesto registrado para detectar discrepancias."
            ),
        ),
        Tool(
            name="list_pending_invoices",
            func=_wrap_pending_invoices,
            description=(
                "Lista todas las facturas pendientes de revisión en el ERP. "
                "No requiere input. Devuelve lista de facturas con discrepancias."
            ),
        ),
        Tool(
            name="search_regulations",
            func=_wrap_rag_lookup,
            description=(
                "Busca normativas y manuales en documentos PDF indexados. "
                "Input: consulta en lenguaje natural sobre regulaciones fiscales. "
                "Útil para verificar requisitos legales o procedimientos."
            ),
        ),
    ]


def build_agent(
    session_memory: ConversationBufferWindowMemory | None = None,
) -> AgentExecutor:
    """Build the reconciliation agent with ReAct pattern.

    Args:
        session_memory: Optional pre-configured memory for the session.

    Returns:
        Configured AgentExecutor ready to process queries.
    """
    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=settings.openai_temperature,
        streaming=True,
    )

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "Eres un agente de conciliación fiscal de la empresa A. "
            "Tu función es ayudar a resolver discrepancias entre facturas de "
            "logística y el sistema ERP.\n\n"
            "REGLAS:\n"
            "1. Siempre verifica los datos en el ERP antes de dar una respuesta.\n"
            "2. Usa la calculadora de impuestos para validar discrepancias.\n"
            "3. Consulta normativas si la situación requiere sustento legal.\n"
            "4. Si detectas un error grave, notifica que se requiere revisión humana.\n"
            "5. NUNCA reveles información salarial o datos restringidos.\n"
            "6. Responde en español de forma clara y concisa.\n\n"
            "CONTEXTO DE SESIÓN:\n"
            "{session_context}"
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    tools = build_tools()
    agent = create_openai_tools_agent(llm, tools, prompt)

    memory = session_memory or ConversationBufferWindowMemory(
        memory_key="chat_history",
        return_messages=True,
        k=10,  # Keep last 10 exchanges
    )

    return AgentExecutor(
        agent=agent,
        tools=tools,
        memory=memory,
        verbose=True,
        max_iterations=5,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
    )


# ---------------------------------------------------------------------------
# High-level query handler with security layer
# ---------------------------------------------------------------------------

class ReconciliationAgent:
    """High-level wrapper combining agent, security, and RAG."""

    def __init__(self):
        self._sessions: dict[str, AgentExecutor] = {}

    def _get_or_create_session(
        self, session_id: str = "default"
    ) -> AgentExecutor:
        """Get existing session or create new one."""
        if session_id not in self._sessions:
            self._sessions[session_id] = build_agent()
        return self._sessions[session_id]

    async def query(
        self,
        user_input: str,
        session_id: str = "default",
        user_role: str = "analyst",
    ) -> dict[str, Any]:
        """Process a user query with full security and tool pipeline.

        Args:
            user_input: Natural language query from the user.
            session_id: Session identifier for conversation memory.
            user_role: User role for access control.

        Returns:
            Dict with response, metadata, and any flagged issues.
        """
        # 1. Security validation
        validation: ValidationResult = prompt_validator.validate(
            user_input, user_role
        )
        if not validation.is_safe:
            return {
                "response": (
                    "⛔ Consulta bloqueada por el sistema de seguridad. "
                    f"Razón: {validation.reason}"
                ),
                "blocked": True,
                "validation": {
                    "is_safe": False,
                    "reason": validation.reason,
                },
            }

        # 2. Get or create agent session
        agent = self._get_or_create_session(session_id)

        # 3. Execute agent with tools
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: agent.invoke({
                    "input": user_input,
                    "session_context": (
                        "Sesión activa de conciliación fiscal. "
                        "El usuario está revisando facturas de logística."
                    ),
                }),
            )

            response_text = result.get("output", "No se generó respuesta.")

            # 4. Sanitize output
            response_text = prompt_validator.sanitize_output(response_text)

            # 5. Extract tool usage for audit trail
            steps = result.get("intermediate_steps", [])
            tool_calls = [
                {
                    "tool": step[0].tool,
                    "input": step[0].tool_input,
                    "output": str(step[1])[:500],
                }
                for step in steps
                if hasattr(step[0], "tool")
            ]

            return {
                "response": response_text,
                "blocked": False,
                "tool_calls": tool_calls,
                "session_id": session_id,
            }

        except Exception as e:
            return {
                "response": (
                    "⚠️ Error al procesar la consulta. "
                    "El sistema ERP o el modelo de IA no están disponibles. "
                    "Por favor intente nuevamente o contacte al administrador."
                ),
                "blocked": False,
                "error": str(e),
            }

    async def query_stream(
        self,
        user_input: str,
        session_id: str = "default",
        user_role: str = "analyst",
    ) -> AsyncIterator[str]:
        """Stream response tokens for better UX.

        Yields response tokens as they are generated.
        """
        # Security check first
        validation = prompt_validator.validate(user_input, user_role)
        if not validation.is_safe:
            yield f"⛔ Consulta bloqueada: {validation.reason}"
            return

        # For streaming, we use the OpenAI client directly
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=settings.openai_temperature,
            streaming=True,
        )

        tools = build_tools()
        agent = create_openai_tools_agent(
            llm,
            tools,
            ChatPromptTemplate.from_messages([
                ("system", "Eres un agente de conciliación fiscal. Responde en español."),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]),
        )

        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            max_iterations=5,
            handle_parsing_errors=True,
        )

        try:
            async for event in executor.astream_events(
                {"input": user_input}, version="v1"
            ):
                if event["event"] == "on_chat_model_stream":
                    content = event["data"]["chunk"].content
                    if content:
                        yield content
        except Exception as e:
            yield f"\n\n⚠️ Error: {e}"


# Global agent instance
reconciliation_agent = ReconciliationAgent()
