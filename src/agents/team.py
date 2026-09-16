"""AutoGen multi-agent team for invoice reconciliation.

Three agents:
- Conciliator: orchestrates, delegates, synthesizes responses
- ERP Analyst: SQL lookups, tax calculations, invoice management
- Compliance Officer: RAG-based regulation lookup

RBAC gates tool access. Audit trail logs every decision.
"""

from __future__ import annotations

from autogen import AssistantAgent, GroupChat, GroupChatManager

from src.security.rbac import rbac, audit_trail


# ---------------------------------------------------------------------------
# System prompts — shared domain vocabulary from CONTEXT.md
# ---------------------------------------------------------------------------

_CONCILIATOR_PROMPT = """Eres el Conciliador — el orquestador principal del sistema de conciliación fiscal de la empresa A.

Tu trabajo:
1. Recibir consultas en lenguaje natural del usuario
2. Descomponer la consulta en subtareas
3. Delegar a los especialistas:
   - ERP Analyst: para consultas de datos, cálculos de impuestos, facturas
   - Compliance Officer: para consultas de normativas y regulaciones
4. Sintetizar las respuestas en una respuesta clara y concisa

REGLAS:
- SIEMPRE responde en español
- Nunca ejecutes herramientas directamente — delega a los especialistas
- Si detectas una discrepancia grave, notifica que se requiere revisión humana
- Nunca reveles información salarial o datos restringidos
- Sé conciso: respuestas de máximo 3 párrafos"""

_ERP_ANALYST_PROMPT = """Eres el Analista ERP — especialista en datos de facturación y cálculos fiscales.

Tus herramientas:
- get_erp_data(order_id): consulta datos de factura en el ERP
- calculate_tax_discrepancy(amount|region): calcula impuesto esperado
- list_pending_invoices(): lista facturas pendientes de revisión

REGLAS:
- SIEMPRE usa herramientas para obtener datos — nunca inventes números
- Presenta datos de forma clara: montos con formato, estados, discrepancias
- Si una factura no existe, reporta el error claramente
- Para cálculos, muestra la fórmula completa
- Responde en español"""

_COMPLIANCE_OFFICER_PROMPT = """Eres el Oficial de Cumplimiento — especialista en normativas y regulaciones fiscales.

Tus herramientas:
- search_regulations(query): busca en manuales y códigos fiscales indexados

REGLAS:
- SIEMPRE cita la fuente del documento encontrado
- Filtra por año y región cuando sea relevante
- Si no encuentras la normativa, di "no se encontró regulación aplicable"
- No des consejos legales — solo cita documentos oficiales
- Responde en español"""


# ---------------------------------------------------------------------------
# Tool registry — maps agent roles to their allowed tools
# ---------------------------------------------------------------------------

def get_tool_registry() -> dict[str, list[str]]:
    """Return which tools each agent role can use."""
    return {
        "conciliator": [],
        "erp_analyst": [
            "get_erp_data",
            "calculate_tax_discrepancy",
            "list_pending_invoices",
        ],
        "compliance_officer": [
            "search_regulations",
        ],
    }


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

def _make_llm_config(llm_config: bool | dict = True) -> dict | False:
    """Build LLM config. Pass False for tests (no API key needed)."""
    if llm_config is False:
        return False
    if isinstance(llm_config, dict):
        return llm_config
    return {"config_list": [{"model": "gpt-4o", "api_key": "placeholder"}]}


def create_conciliator(llm_config: bool | dict = True) -> AssistantAgent:
    """Create the orchestrator agent."""
    return AssistantAgent(
        name="Conciliator",
        system_message=_CONCILIATOR_PROMPT,
        llm_config=_make_llm_config(llm_config),
        human_input_mode="NEVER",
    )


def create_erp_analyst(llm_config: bool | dict = True) -> AssistantAgent:
    """Create the ERP specialist agent."""
    return AssistantAgent(
        name="ERP_Analyst",
        system_message=_ERP_ANALYST_PROMPT,
        llm_config=_make_llm_config(llm_config),
        human_input_mode="NEVER",
    )


def create_compliance_officer(llm_config: bool | dict = True) -> AssistantAgent:
    """Create the compliance specialist agent."""
    return AssistantAgent(
        name="Compliance_Officer",
        system_message=_COMPLIANCE_OFFICER_PROMPT,
        llm_config=_make_llm_config(llm_config),
        human_input_mode="NEVER",
    )


# ---------------------------------------------------------------------------
# Team — GroupChat with speaker selection
# ---------------------------------------------------------------------------

def build_team(
    llm_config: bool | dict = True,
    max_round: int = 10,
) -> GroupChatManager:
    """Build the multi-agent team.

    Returns a GroupChatManager that coordinates the three agents.
    The Conciliator is the default speaker (orchestrator pattern).
    """
    conciliator = create_conciliator(llm_config)
    erp_analyst = create_erp_analyst(llm_config)
    compliance_officer = create_compliance_officer(llm_config)

    group_chat = GroupChat(
        agents=[conciliator, erp_analyst, compliance_officer],
        messages=[],
        max_round=max_round,
        speaker_selection_method="auto",
        allow_repeat_speaker=False,
    )

    return GroupChatManager(
        groupchat=group_chat,
        llm_config=_make_llm_config(llm_config),
    )
