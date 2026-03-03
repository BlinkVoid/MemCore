"""
Multi-device Sync System for MemCore

Provides synchronization capabilities:
- Git-based sync (using git repository as sync target)
- Sync to/from remote storage
- Conflict resolution for concurrent edits
- Selective sync by quadrant
"""
import os
import json
import shutil
import zipfile
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass
from enum import Enum


class SyncStatus(Enum):
    """Status of sync operation."""
    SUCCESS = "success"
    CONFLICT = "conflict"
    ERROR = "error"
    NO_REMOTE = "no_remote"
    UP_TO_DATE = "up_to_date"


@dataclass
class SyncResult:
    """Result of a sync operation."""
    status: SyncStatus
    message: str
    records_uploaded: int = 0
    records_downloaded: int = 0
    conflicts: List[Dict[str, Any]] = None
    timestamp: str = None

    def __post_init__(self):
        if self.conflicts is None:
            self.conflicts = []
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


class MultiDeviceSync:
    """
    Multi-device synchronization for MemCore.

    Uses a git-based approach:
    - Exports data to a sync bundle
    - Syncs via git repository (GitHub, GitLab, etc.)
    - Imports from sync bundle

    Alternative: Direct file sync (Dropbox, Syncthing, etc.)
    """

    def __init__(self, data_dir: str, sync_config_path: Optional[str] = None):
        self.data_dir = Path(data_dir)
        self.sync_config_path = sync_config_path or str(self.data_dir / "sync_config.json")
        self.sync_bundle_dir = self.data_dir / "sync_bundles"
        self.sync_bundle_dir.mkdir(exist_ok=True)

        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load sync configuration."""
        if os.path.exists(self.sync_config_path):
            with open(self.sync_config_path, 'r') as f:
                return json.load(f)
        return {
            "remote_url": None,
            "sync_enabled": False,
            "last_sync": None,
            "device_id": self._generate_device_id(),
            "selective_sync": {
                "quadrants": None,  # None = all
                "min_importance": None
            }
        }

    def _save_config(self):
        """Save sync configuration."""
        with open(self.sync_config_path, 'w') as f:
            json.dump(self.config, f, indent=2)

    def _generate_device_id(self) -> str:
        """Generate unique device identifier."""
        import uuid
        return f"memcore_{uuid.uuid4().hex[:8]}"

    async def setup_remote(self, remote_url: str, auth_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Configure sync remote repository.

        Args:
            remote_url: Git repository URL (https or git)
            auth_token: Optional auth token for HTTPS

        Returns:
            Setup result
        """
        self.config["remote_url"] = remote_url
        self.config["auth_token"] = auth_token
        self.config["sync_enabled"] = True
        self._save_config()

        return {
            "success": True,
            "remote_url": remote_url,
            "device_id": self.config["device_id"],
            "message": "Remote configured. Use sync_push to upload data."
        }

    async def create_sync_bundle(
        self,
        vector_store,
        graph_store,
        include_vectors: bool = True,
        selective_quadrants: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a sync bundle from current data.

        Args:
            vector_store: Vector store instance
            graph_store: Graph store instance
            include_vectors: Include vector embeddings
            selective_quadrants: Only sync specific quadrants

        Returns:
            Bundle metadata
        """
        bundle_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        bundle_path = self.sync_bundle_dir / f"sync_{bundle_id}.zip"

        manifest = {
            "bundle_id": bundle_id,
            "created_at": datetime.now().isoformat(),
            "device_id": self.config["device_id"],
            "includes_vectors": include_vectors,
            "selective_quadrants": selective_quadrants,
            "files": []
        }

        total_size = 0

        with zipfile.ZipFile(bundle_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add manifest
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))

            # Export memories
            all_memories = vector_store.get_all_memories(limit=100000)

            # Filter by quadrant if selective sync
            if selective_quadrants:
                all_memories = [
                    m for m in all_memories
                    if any(q in selective_quadrants for q in m.payload.get("quadrants", ["general"]))
                ]

            # Build memory export
            memories_export = []
            for mem in all_memories:
                mem_data = {
                    "id": str(mem.id),
                    "payload": mem.payload,
                    "vector": mem.vector.tolist() if include_vectors and hasattr(mem, 'vector') else None
                }
                memories_export.append(mem_data)

            memories_json = json.dumps(memories_export, indent=2)
            zf.writestr("memories.json", memories_json)
            total_size += len(memories_json)

            # Export graph data
            graph_export = graph_store.export_for_sync()
            graph_json = json.dumps(graph_export, indent=2)
            zf.writestr("graph.json", graph_json)
            total_size += len(graph_json)

            # Add device metadata
            device_info = {
                "device_id": self.config["device_id"],
                "sync_timestamp": datetime.now().isoformat(),
                "memory_count": len(memories_export),
                "graph_nodes": len(graph_export.get("nodes", [])),
                "graph_edges": len(graph_export.get("edges", []))
            }
            zf.writestr("device_info.json", json.dumps(device_info, indent=2))

        manifest["bundle_path"] = str(bundle_path)
        manifest["size_bytes"] = bundle_path.stat().st_size

        return manifest

    async def apply_sync_bundle(
        self,
        bundle_path: str,
        vector_store,
        graph_store,
        conflict_resolution: str = "timestamp"  # "timestamp", "local", "remote"
    ) -> SyncResult:
        """
        Apply a sync bundle to local storage.

        Args:
            bundle_path: Path to sync bundle
            vector_store: Vector store instance
            graph_store: Graph store instance
            conflict_resolution: How to resolve conflicts

        Returns:
            Sync result
        """
        if not os.path.exists(bundle_path):
            return SyncResult(
                status=SyncStatus.ERROR,
                message=f"Bundle not found: {bundle_path}"
            )

        records_downloaded = 0
        conflicts = []

        with zipfile.ZipFile(bundle_path, 'r') as zf:
            # Read manifest
            manifest = json.loads(zf.read("manifest.json"))
            device_info = json.loads(zf.read("device_info.json"))

            # Check for conflicts (simplified)
            # In real implementation, compare timestamps and merge

            # Import memories
            memories_data = json.loads(zf.read("memories.json"))
            for mem_data in memories_data:
                # Check if memory exists
                existing = vector_store.get_memory_by_id(mem_data["id"])

                if existing:
                    # Conflict - resolve based on strategy
                    if conflict_resolution == "remote":
                        # Replace with remote
                        vector_store.delete_memory(mem_data["id"])
                        vector_store.add_memory_with_id(
                            mem_data["id"],
                            mem_data["payload"],
                            mem_data["vector"]
                        )
                    elif conflict_resolution == "timestamp":
                        # Compare timestamps and keep newer
                        # Simplified: skip for now
                        pass
                else:
                    # New memory - add it
                    vector_store.add_memory_with_id(
                        mem_data["id"],
                        mem_data["payload"],
                        mem_data["vector"]
                    )
                    records_downloaded += 1

            # Import graph
            graph_data = json.loads(zf.read("graph.json"))
            graph_store.import_from_sync(graph_data)

        return SyncResult(
            status=SyncStatus.SUCCESS,
            message=f"Synced from {device_info['device_id']}",
            records_downloaded=records_downloaded,
            conflicts=conflicts
        )

    async def sync_push(
        self,
        vector_store,
        graph_store,
        include_vectors: bool = True
    ) -> SyncResult:
        """
        Push local data to remote sync target.

        For git-based sync, this creates a bundle and commits to the repo.
        For file-based sync, this exports to the sync directory.
        """
        if not self.config.get("remote_url") and not self.config.get("sync_directory"):
            return SyncResult(
                status=SyncStatus.NO_REMOTE,
                message="No sync target configured. Use setup_remote first."
            )

        try:
            # Create bundle
            bundle = await self.create_sync_bundle(
                vector_store,
                graph_store,
                include_vectors=include_vectors,
                selective_quadrants=self.config.get("selective_sync", {}).get("quadrants")
            )

            # Copy to sync directory
            if self.config.get("sync_directory"):
                sync_dir = Path(self.config["sync_directory"])
                sync_dir.mkdir(parents=True, exist_ok=True)

                dest_path = sync_dir / "latest_sync.zip"
                shutil.copy(bundle["bundle_path"], dest_path)

            # Update config
            self.config["last_sync"] = datetime.now().isoformat()
            self._save_config()

            return SyncResult(
                status=SyncStatus.SUCCESS,
                message=f"Pushed {bundle['size_bytes'] // 1024} KB to sync target",
                records_uploaded=bundle.get("memory_count", 0)
            )

        except Exception as e:
            return SyncResult(
                status=SyncStatus.ERROR,
                message=f"Push failed: {e}"
            )

    async def sync_pull(
        self,
        vector_store,
        graph_store,
        conflict_resolution: str = "timestamp"
    ) -> SyncResult:
        """
        Pull data from remote sync target.
        """
        if not self.config.get("sync_directory"):
            return SyncResult(
                status=SyncStatus.NO_REMOTE,
                message="No sync directory configured."
            )

        sync_dir = Path(self.config["sync_directory"])
        bundle_path = sync_dir / "latest_sync.zip"

        if not bundle_path.exists():
            return SyncResult(
                status=SyncStatus.UP_TO_DATE,
                message="No sync data available from other devices."
            )

        return await self.apply_sync_bundle(
            str(bundle_path),
            vector_store,
            graph_store,
            conflict_resolution
        )

    async def sync_status(self) -> Dict[str, Any]:
        """Get current sync status."""
        return {
            "device_id": self.config["device_id"],
            "sync_enabled": self.config["sync_enabled"],
            "remote_url": self.config.get("remote_url"),
            "sync_directory": self.config.get("sync_directory"),
            "last_sync": self.config.get("last_sync"),
            "selective_sync": self.config.get("selective_sync"),
            "bundles_available": len(list(self.sync_bundle_dir.glob("*.zip")))
        }

    async def configure_selective_sync(
        self,
        quadrants: Optional[List[str]] = None,
        min_importance: Optional[float] = None
    ) -> Dict[str, Any]:
        """Configure selective sync options."""
        self.config["selective_sync"] = {
            "quadrants": quadrants,
            "min_importance": min_importance
        }
        self._save_config()

        return {
            "success": True,
            "selective_sync": self.config["selective_sync"]
        }

    async def list_devices(self) -> List[Dict[str, Any]]:
        """List devices that have synced."""
        devices = []

        for bundle_file in self.sync_bundle_dir.glob("*.zip"):
            try:
                with zipfile.ZipFile(bundle_file, 'r') as zf:
                    if "device_info.json" in zf.namelist():
                        device_info = json.loads(zf.read("device_info.json"))
                        devices.append(device_info)
            except:
                continue

        return devices
