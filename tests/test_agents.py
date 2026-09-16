"""Tests for the AutoGen agent team — multi-agent orchestration.

Seams under test:
1. Agent factory creates correct agent types
2. Tool registry maps tools to agents correctly
3. RBAC integration gates tool access per agent role
4. Team formation produces valid GroupChat
"""

import pytest
from unittest.mock import MagicMock, patch

from src.agents.team import (
    create_erp_analyst,
    create_compliance_officer,
    create_conciliator,
    build_team,
    get_tool_registry,
)
from src.security.rbac import RBAC


# ---------------------------------------------------------------------------
# Agent creation
# ---------------------------------------------------------------------------

class TestAgentCreation:

    def test_erp_analyst_has_system_message(self):
        agent = create_erp_analyst(llm_config=False)
        assert agent is not None
        assert "ERP" in agent.system_message or "erp" in agent.system_message.lower()

    def test_compliance_officer_has_system_message(self):
        agent = create_compliance_officer(llm_config=False)
        assert agent is not None
        assert "normativ" in agent.system_message.lower() or "regulat" in agent.system_message.lower()

    def test_conciliator_has_system_message(self):
        agent = create_conciliator(llm_config=False)
        assert agent is not None
        msg = agent.system_message.lower()
        assert "conciliat" in msg or "orchestrat" in msg or "empresa" in msg


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

class TestToolRegistry:

    def test_erp_analyst_has_erp_tools(self):
        registry = get_tool_registry()
        erp_tools = registry["erp_analyst"]
        assert "get_erp_data" in erp_tools
        assert "calculate_tax_discrepancy" in erp_tools

    def test_compliance_officer_has_rag_tool(self):
        registry = get_tool_registry()
        compliance_tools = registry["compliance_officer"]
        assert "search_regulations" in compliance_tools

    def test_conciliator_has_no_tools(self):
        registry = get_tool_registry()
        conciliator_tools = registry.get("conciliator", [])
        assert len(conciliator_tools) == 0

    def test_all_registered_tools_exist(self):
        """Every tool in the registry must be importable."""
        from src.tools.erp_tools import get_erp_data, calculate_tax_discrepancy, list_pending_invoices
        registry = get_tool_registry()
        all_tools = []
        for tools in registry.values():
            all_tools.extend(tools)
        # All tools should be known function names
        known = {"get_erp_data", "calculate_tax_discrepancy", "list_pending_invoices", "search_regulations"}
        assert set(all_tools).issubset(known)


# ---------------------------------------------------------------------------
# RBAC integration
# ---------------------------------------------------------------------------

class TestRBACIntegration:

    def test_rbac_gates_erp_analyst_tools(self):
        rbac = RBAC()
        assert rbac.check_access("analyst", "get_erp_data") is True
        assert rbac.check_access("analyst", "generate_erp_adjustment") is False

    def test_rbac_gates_compliance_tools(self):
        rbac = RBAC()
        assert rbac.check_access("analyst", "search_regulations") is True

    def test_viewer_cannot_trigger_any_tool(self):
        rbac = RBAC()
        registry = get_tool_registry()
        for tools in registry.values():
            for tool in tools:
                assert rbac.check_access("viewer", tool) is False


# ---------------------------------------------------------------------------
# Team formation
# ---------------------------------------------------------------------------

class TestTeamFormation:

    def test_team_has_three_agents(self):
        team = build_team(llm_config=False)
        assert team is not None
        # GroupChatManager wraps a GroupChat with the agents
        agent_names = [a.name for a in team.groupchat.agents]
        assert len(agent_names) == 3

    def test_team_includes_all_roles(self):
        team = build_team(llm_config=False)
        agent_names = {a.name.lower() for a in team.groupchat.agents}
        # At least one agent for each role
        has_conciliator = any("conciliat" in n or "orchestrat" in n for n in agent_names)
        has_erp = any("erp" in n or "analyst" in n for n in agent_names)
        has_compliance = any("complianc" in n or "regulat" in n for n in agent_names)
        assert has_conciliator
        assert has_erp
        assert has_compliance
