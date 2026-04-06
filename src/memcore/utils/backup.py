"""
Memory Backup and Restore System for MemCore

Provides full backup/restore capabilities:
- Complete data backup (vector + graph + queue)
- Scheduled automatic backups
- Compression and retention policies
- Point-in-time recovery
"""
import os
import json
import shutil
import zipfile
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BackupInfo:
    """Information about a backup."""
    id: str
    created_at: datetime
    size_bytes: int
    description: str
    includes_vectors: bool
    includes_graph: bool
    includes_queue: bool
    memcore_version: str = "1.0.0"


class MemoryBackupManager:
    """
    Manages backup and restore operations for MemCore.

    Creates compressed archives containing:
    - Vector database (Qdrant storage)
    - Graph database (SQLite)
    - Consolidation queue (SQLite)
    - Metadata and manifest
    """

    def __init__(self, data_dir: str, backup_dir: Optional[str] = None):
        self.data_dir = Path(data_dir)
        self.backup_dir = Path(backup_dir) if backup_dir else self.data_dir / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Paths to data sources
        self.vector_path = self.data_dir / "qdrant_storage"
        self.graph_path = self.data_dir / "memcore_graph.db"
        self.queue_path = self.data_dir / "consolidation_queue.db"

    async def create_backup(
        self,
        description: str = "",
        include_vectors: bool = True,
        include_graph: bool = True,
        include_queue: bool = True
    ) -> Dict[str, Any]:
        """
        Create a new backup archive.

        Args:
            description: Optional description of the backup
            include_vectors: Include vector database
            include_graph: Include graph database
            include_queue: Include consolidation queue

        Returns:
            Backup metadata
        """
        backup_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"memcore_backup_{backup_id}.zip"

        manifest = {
            "backup_id": backup_id,
            "created_at": datetime.now().isoformat(),
            "description": description or f"Manual backup {backup_id}",
            "includes_vectors": include_vectors,
            "includes_graph": include_graph,
            "includes_queue": include_queue,
            "memcore_version": "1.0.0",
            "files": []
        }

        total_size = 0

        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add manifest first
            manifest_data = json.dumps(manifest, indent=2).encode('utf-8')
            zf.writestr("manifest.json", manifest_data)

            # Backup vector database
            if include_vectors and self.vector_path.exists():
                vector_size = self._add_directory_to_zip(zf, self.vector_path, "vectors")
                total_size += vector_size
                manifest["files"].append({"path": "vectors", "size": vector_size})

            # Backup graph database
            if include_graph and self.graph_path.exists():
                graph_size = self.graph_path.stat().st_size
                zf.write(self.graph_path, "graph/memcore_graph.db")
                total_size += graph_size
                manifest["files"].append({"path": "graph/memcore_graph.db", "size": graph_size})

            # Backup queue database
            if include_queue and self.queue_path.exists():
                queue_size = self.queue_path.stat().st_size
                zf.write(self.queue_path, "queue/consolidation_queue.db")
                total_size += queue_size
                manifest["files"].append({"path": "queue/consolidation_queue.db", "size": queue_size})

            # Update manifest with final info
            manifest["total_size_bytes"] = total_size
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        return {
            "backup_id": backup_id,
            "backup_path": str(backup_path),
            "size_bytes": total_size,
            "includes_vectors": include_vectors,
            "includes_graph": include_graph,
            "includes_queue": include_queue
        }

    async def restore_backup(
        self,
        backup_id: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Restore from a backup.

        Args:
            backup_id: ID of backup to restore
            force: Overwrite existing data without confirmation

        Returns:
            Restore results
        """
        backup_path = self.backup_dir / f"memcore_backup_{backup_id}.zip"

        if not backup_path.exists():
            # Try to find by partial match
            matches = list(self.backup_dir.glob(f"*{backup_id}*.zip"))
            if len(matches) == 1:
                backup_path = matches[0]
            elif len(matches) > 1:
                return {
                    "success": False,
                    "error": f"Multiple backups match '{backup_id}'. Please be more specific."
                }
            else:
                return {
                    "success": False,
                    "error": f"Backup not found: {backup_id}"
                }

        # Check for existing data
        has_existing = (
            self.vector_path.exists() or
            self.graph_path.exists() or
            self.queue_path.exists()
        )

        if has_existing and not force:
            return {
                "success": False,
                "error": "Existing data found. Use force=True to overwrite.",
                "requires_force": True
            }

        restored = []
        errors = []

        with zipfile.ZipFile(backup_path, 'r') as zf:
            # Read manifest
            try:
                manifest_data = zf.read("manifest.json")
                manifest = json.loads(manifest_data)
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to read manifest: {e}"
                }

            # Create temp restore directory
            temp_dir = self.data_dir / "temp_restore"
            temp_dir.mkdir(exist_ok=True)

            try:
                # Extract all files
                zf.extractall(temp_dir)

                # Restore vectors
                if manifest.get("includes_vectors"):
                    vector_temp = temp_dir / "vectors"
                    if vector_temp.exists():
                        if self.vector_path.exists():
                            shutil.rmtree(self.vector_path)
                        shutil.move(str(vector_temp), str(self.vector_path))
                        restored.append("vectors")

                # Restore graph
                if manifest.get("includes_graph"):
                    graph_temp = temp_dir / "graph" / "memcore_graph.db"
                    if graph_temp.exists():
                        if self.graph_path.exists():
                            self.graph_path.unlink()
                        graph_temp.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(graph_temp), str(self.graph_path))
                        restored.append("graph")

                # Restore queue
                if manifest.get("includes_queue"):
                    queue_temp = temp_dir / "queue" / "consolidation_queue.db"
                    if queue_temp.exists():
                        if self.queue_path.exists():
                            self.queue_path.unlink()
                        queue_temp.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(queue_temp), str(self.queue_path))
                        restored.append("queue")

            finally:
                # Cleanup temp directory
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)

        return {
            "success": True,
            "backup_id": backup_id,
            "restored": restored,
            "errors": errors,
            "manifest": manifest
        }

    async def list_backups(self) -> List[BackupInfo]:
        """List all available backups."""
        backups = []

        for backup_file in sorted(self.backup_dir.glob("memcore_backup_*.zip"), reverse=True):
            try:
                with zipfile.ZipFile(backup_file, 'r') as zf:
                    manifest_data = zf.read("manifest.json")
                    manifest = json.loads(manifest_data)

                backup_id = manifest["backup_id"]
                created_at = datetime.fromisoformat(manifest["created_at"])
                size_bytes = backup_file.stat().st_size

                backups.append(BackupInfo(
                    id=backup_id,
                    created_at=created_at,
                    size_bytes=size_bytes,
                    description=manifest.get("description", ""),
                    includes_vectors=manifest.get("includes_vectors", True),
                    includes_graph=manifest.get("includes_graph", True),
                    includes_queue=manifest.get("includes_queue", True)
                ))
            except Exception:
                # Skip corrupted backups
                continue

        return backups

    async def delete_backup(self, backup_id: str) -> Dict[str, Any]:
        """Delete a backup."""
        backup_path = self.backup_dir / f"memcore_backup_{backup_id}.zip"

        if not backup_path.exists():
            # Try partial match
            matches = list(self.backup_dir.glob(f"*{backup_id}*.zip"))
            if len(matches) == 1:
                backup_path = matches[0]
            else:
                return {
                    "success": False,
                    "error": f"Backup not found: {backup_id}"
                }

        size_bytes = backup_path.stat().st_size
        backup_path.unlink()

        return {
            "success": True,
            "backup_id": backup_id,
            "freed_bytes": size_bytes
        }

    async def cleanup_old_backups(self, keep_days: int = 30, keep_min: int = 5) -> Dict[str, Any]:
        """
        Remove old backups while keeping minimum count.

        Args:
            keep_days: Delete backups older than this
            keep_min: Always keep at least this many recent backups

        Returns:
            Cleanup results
        """
        backups = await self.list_backups()
        cutoff_date = datetime.now() - timedelta(days=keep_days)

        deleted = []
        errors = []

        # Keep at least keep_min backups, delete rest older than keep_days
        for i, backup in enumerate(backups):
            if i < keep_min:
                continue  # Always keep minimum

            if backup.created_at < cutoff_date:
                result = await self.delete_backup(backup.id)
                if result["success"]:
                    deleted.append({
                        "id": backup.id,
                        "freed_bytes": result["freed_bytes"]
                    })
                else:
                    errors.append({"id": backup.id, "error": result["error"]})

        total_freed = sum(d["freed_bytes"] for d in deleted)

        return {
            "deleted_count": len(deleted),
            "total_freed_bytes": total_freed,
            "deleted": deleted,
            "errors": errors
        }

    def _add_directory_to_zip(self, zf: zipfile.ZipFile, path: Path, arcname: str) -> int:
        """Add a directory to zip file, return total size."""
        total_size = 0
        for file_path in path.rglob("*"):
            if file_path.is_file():
                size = file_path.stat().st_size
                total_size += size
                relative_path = file_path.relative_to(path)
                zf.write(file_path, f"{arcname}/{relative_path}")
        return total_size

    def get_backup_stats(self) -> Dict[str, Any]:
        """Get backup statistics."""
        backups = list(self.backup_dir.glob("memcore_backup_*.zip"))
        total_size = sum(b.stat().st_size for b in backups)

        return {
            "backup_count": len(backups),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "backup_directory": str(self.backup_dir)
        }
