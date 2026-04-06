"""
Vault Sync Skill - Manual synchronization with Obsidian vault.

Usage: /vault_sync [force|status]
"""
from typing import Dict, Any, Optional
from datetime import datetime
import os


class VaultSyncSkill:
    """
    Skill for managing Obsidian vault synchronization.

    Usage:
      /vault_sync status    - Check sync status
      /vault_sync force     - Force full vault rescan
    """

    def __init__(self, document_watcher, vector_store, llm):
        self.watcher = document_watcher
        self.vector_store = vector_store
        self.llm = llm

    async def execute(
        self,
        command: str = "status",  # "status" or "force"
        vault_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute vault sync command.

        Args:
            command: "status" or "force"
            vault_path: Optional path to vault (uses configured path if not provided)
        """
        try:
            if command == "status":
                return await self._get_status()
            elif command == "force":
                return await self._force_sync(vault_path)
            else:
                return {
                    "success": False,
                    "error": f"Unknown command: {command}. Use 'status' or 'force'."
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def _get_status(self) -> Dict[str, Any]:
        """Get current vault sync status."""
        if not self.watcher:
            return {
                "success": True,
                "status": "disabled",
                "message": "Document watcher not configured."
            }

        stats = self.watcher.get_stats()

        return {
            "success": True,
            "status": "active" if stats.get("watching") else "inactive",
            "vault_path": stats.get("vault_path"),
            "files_tracked": stats.get("files_tracked", 0),
            "last_scan": stats.get("last_scan"),
            "changes_detected": stats.get("changes_detected", 0)
        }

    async def _force_sync(self, vault_path: Optional[str]) -> Dict[str, Any]:
        """Force a full vault rescan."""
        if not self.watcher:
            return {
                "success": False,
                "error": "Document watcher not configured. Set OBSIDIAN_VAULT_PATH in .env"
            }

        # Perform full rescan
        result = await self.watcher.force_rescan(vault_path)

        return {
            "success": True,
            "command": "force",
            "files_scanned": result.get("files_scanned", 0),
            "files_added": result.get("files_added", 0),
            "files_updated": result.get("files_updated", 0),
            "files_removed": result.get("files_removed", 0),
            "errors": result.get("errors", []),
            "message": f"Force sync complete. {result.get('files_added', 0)} added, {result.get('files_updated', 0)} updated."
        }

    def get_help(self) -> str:
        return """
/vault_sync [command] [--path=/path/to/vault]

Commands:
  status    Show current sync status
  force     Force full vault rescan (use when files seem out of sync)

Examples:
  /vault_sync status
  /vault_sync force
  /vault_sync force --path="C:\\Users\\me\\Obsidian"
"""
