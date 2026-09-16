"""Role-Based Access Control + Audit Trail.

Every tool call passes through RBAC before reaching the agent.
Every decision is logged for incident investigation and compliance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# RBAC — tool access by role
# ---------------------------------------------------------------------------

# Which tools each role can use.
#viewer: read-only queries only (no tools)
# analyst: ERP tools, no write actions
# admin: everything

_TOOL_ACCESS: dict[str, set[str]] = {
    "viewer": set(),  # no tools — only conversational queries
    "analyst": {
        "get_erp_data",
        "calculate_tax_discrepancy",
        "list_pending_invoices",
        "search_regulations",
    },
    "admin": {
        "get_erp_data",
        "calculate_tax_discrepancy",
        "list_pending_invoices",
        "search_regulations",
        "generate_erp_adjustment",
    },
}


class RBAC:
    """Check whether a role may use a tool, and log every decision."""

    def __init__(self, custom_access: dict[str, set[str]] | None = None):
        self._access = custom_access or _TOOL_ACCESS

    def check_access(self, role: str, tool: str) -> bool:
        """Return True if role may invoke tool."""
        allowed_tools = self._access.get(role, set())
        return tool in allowed_tools

    def get_allowed_tools(self, role: str) -> set[str]:
        """Return the full set of tools a role may use."""
        return self._access.get(role, set()).copy()


# ---------------------------------------------------------------------------
# Audit Trail — immutable log of every decision
# ---------------------------------------------------------------------------

@dataclass
class AuditEntry:
    """One logged decision."""

    timestamp: datetime
    session_id: str
    role: str
    tool: str
    query: str
    allowed: bool
    denial_reason: str | None = None


class AuditTrail:
    """Append-only log keyed by session_id."""

    def __init__(self):
        self._entries: dict[str, list[AuditEntry]] = {}

    def log(
        self,
        role: str,
        tool: str,
        query: str,
        allowed: bool,
        session_id: str,
        denial_reason: str | None = None,
    ) -> AuditEntry:
        """Record one access decision. Returns the entry for chaining."""
        if not allowed and denial_reason is None:
            denial_reason = f"Role '{role}' not authorized for tool '{tool}'"

        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc),
            session_id=session_id,
            role=role,
            tool=tool,
            query=query,
            allowed=allowed,
            denial_reason=denial_reason,
        )

        self._entries.setdefault(session_id, []).append(entry)
        return entry

    def get_entries(self, session_id: str) -> list[AuditEntry]:
        """Return all entries for a session, in chronological order."""
        return list(self._entries.get(session_id, []))

    def get_denials(self, session_id: str) -> list[AuditEntry]:
        """Return only denied entries for a session."""
        return [e for e in self.get_entries(session_id) if not e.allowed]

    def count(self, session_id: str) -> int:
        """Total entries for a session."""
        return len(self._entries.get(session_id, []))


# ---------------------------------------------------------------------------
# Global instances
# ---------------------------------------------------------------------------

rbac = RBAC()
audit_trail = AuditTrail()
