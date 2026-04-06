"""
MemCore Skills - User-facing slash commands for admin and utility tasks.

Skills are interactive commands that users invoke explicitly,
unlike MCP tools which the AI uses automatically during conversation.
"""

from .feedback_skill import FeedbackSkill
from .vault_sync_skill import VaultSyncSkill
from .consolidate_export_skill import ConsolidateExportSkill
from .recategorize_skill import RecategorizeSkill
from .ingest_consolidated_skill import IngestConsolidatedSkill

__all__ = [
    "FeedbackSkill",
    "VaultSyncSkill",
    "ConsolidateExportSkill",
    "RecategorizeSkill",
    "IngestConsolidatedSkill",
]
