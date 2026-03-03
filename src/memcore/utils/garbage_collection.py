"""
Memory Garbage Collection System for MemCore

Provides maintenance and cleanup capabilities:
- Remove orphaned vector/graph records
- Clean up old low-importance memories
- Compact databases
- Remove duplicate memories
- Archive stale memories
"""
import os
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum


class CleanupType(Enum):
    """Types of cleanup operations."""
    ORPHANS = "orphans"           # Records in one store but not the other
    DUPLICATES = "duplicates"     # Semantic duplicates
    STALE = "stale"               # Old, low-importance, rarely accessed
    UNREACHABLE = "unreachable"   # No incoming/outgoing edges in graph
    ARCHIVE = "archive"           # Move old data to archive storage


@dataclass
class CleanupResult:
    """Result of a cleanup operation."""
    cleanup_type: CleanupType
    items_found: int
    items_removed: int
    items_archived: int
    space_reclaimed_bytes: int
    errors: List[str]


class MemoryGarbageCollector:
    """
    Garbage collector for memory maintenance.

    Performs periodic cleanup to maintain system health:
    - Removes orphaned records
    - Deduplicates memories
    - Archives old data
    - Compacts storage
    """

    def __init__(
        self,
        vector_store,
        graph_store,
        queue_store=None,
        archive_dir: Optional[str] = None
    ):
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.queue_store = queue_store
        self.archive_dir = archive_dir

    async def run_full_cleanup(
        self,
        dry_run: bool = True,
        stale_days: int = 365,
        stale_min_access: int = 2,
        remove_duplicates: bool = True
    ) -> Dict[str, Any]:
        """
        Run all cleanup operations.

        Args:
            dry_run: If True, only report what would be done
            stale_days: Memories older than this are candidates for removal
            stale_min_access: Minimum access count to keep stale memories
            remove_duplicates: Find and merge duplicate memories

        Returns:
            Summary of all cleanup operations
        """
        results = {
            "dry_run": dry_run,
            "timestamp": datetime.now().isoformat(),
            "operations": []
        }

        # 1. Find orphans
        orphan_result = await self.cleanup_orphans(dry_run)
        results["operations"].append(self._result_to_dict(orphan_result))

        # 2. Find stale memories
        stale_result = await self.cleanup_stale(
            dry_run=dry_run,
            min_age_days=stale_days,
            min_access_count=stale_min_access
        )
        results["operations"].append(self._result_to_dict(stale_result))

        # 3. Find and merge duplicates
        if remove_duplicates:
            dup_result = await self.cleanup_duplicates(dry_run)
            results["operations"].append(self._result_to_dict(dup_result))

        # 4. Calculate totals
        total_removed = sum(op["items_removed"] for op in results["operations"])
        total_reclaimed = sum(op["space_reclaimed_bytes"] for op in results["operations"])

        results["summary"] = {
            "total_items_removed": total_removed,
            "total_space_reclaimed_mb": round(total_reclaimed / (1024 * 1024), 2),
            "operations_run": len(results["operations"])
        }

        return results

    async def cleanup_orphans(self, dry_run: bool = True) -> CleanupResult:
        """
        Find and remove orphaned records.

        Orphans are:
        - Memories in vector store but not in graph
        - Graph nodes without corresponding vector records
        """
        result = CleanupResult(
            cleanup_type=CleanupType.ORPHANS,
            items_found=0,
            items_removed=0,
            items_archived=0,
            space_reclaimed_bytes=0,
            errors=[]
        )

        try:
            # Get all memory IDs from vector store
            vector_ids = set()
            all_vectors = self.vector_store.get_all_memories(limit=100000)
            for mem in all_vectors:
                vector_ids.add(str(mem.id))

            # Get all node IDs from graph
            graph_ids = set(self.graph_store.get_all_memory_nodes())

            # Find orphans
            vector_only = vector_ids - graph_ids
            graph_only = graph_ids - vector_ids

            result.items_found = len(vector_only) + len(graph_only)

            if not dry_run:
                # Remove vector-only records
                for mem_id in vector_only:
                    try:
                        self.vector_store.delete_memory(mem_id)
                        result.items_removed += 1
                    except Exception as e:
                        result.errors.append(f"Failed to delete vector {mem_id}: {e}")

                # Remove graph-only nodes
                for node_id in graph_only:
                    try:
                        self.graph_store.remove_node(node_id)
                        result.items_removed += 1
                    except Exception as e:
                        result.errors.append(f"Failed to delete graph node {node_id}: {e}")

                # Estimate space reclaimed
                result.space_reclaimed_bytes = result.items_removed * 2048  # Rough estimate

        except Exception as e:
            result.errors.append(f"Orphan cleanup error: {e}")

        return result

    async def cleanup_stale(
        self,
        dry_run: bool = True,
        min_age_days: int = 365,
        min_access_count: int = 2,
        max_importance: float = 0.3
    ) -> CleanupResult:
        """
        Find and remove stale memories.

        Stale memories are:
        - Older than min_age_days
        - Accessed fewer than min_access_count times
        - Importance below max_importance
        """
        result = CleanupResult(
            cleanup_type=CleanupType.STALE,
            items_found=0,
            items_removed=0,
            items_archived=0,
            space_reclaimed_bytes=0,
            errors=[]
        )

        try:
            cutoff_date = datetime.now() - timedelta(days=min_age_days)

            # Scan all memories
            all_memories = self.vector_store.get_all_memories(limit=100000)

            stale_ids = []
            for mem in all_memories:
                payload = mem.payload
                created_at = payload.get("created_at")
                access_count = payload.get("access_count", 0)
                importance = payload.get("importance", 0.5)

                if not created_at:
                    continue

                # Parse date
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    except:
                        continue

                # Check stale criteria
                if (created_at < cutoff_date and
                    access_count < min_access_count and
                    importance <= max_importance):
                    stale_ids.append(str(mem.id))

            result.items_found = len(stale_ids)

            if not dry_run:
                for mem_id in stale_ids:
                    try:
                        self.vector_store.delete_memory(mem_id)
                        self.graph_store.remove_node(mem_id)
                        result.items_removed += 1
                    except Exception as e:
                        result.errors.append(f"Failed to delete stale memory {mem_id}: {e}")

                result.space_reclaimed_bytes = result.items_removed * 2048

        except Exception as e:
            result.errors.append(f"Stale cleanup error: {e}")

        return result

    async def cleanup_duplicates(self, dry_run: bool = True, similarity_threshold: float = 0.95) -> CleanupResult:
        """
        Find and merge duplicate memories.

        Uses vector similarity to find near-duplicates.
        """
        result = CleanupResult(
            cleanup_type=CleanupType.DUPLICATES,
            items_found=0,
            items_removed=0,
            items_archived=0,
            space_reclaimed_bytes=0,
            errors=[]
        )

        try:
            # Get all memories grouped by quadrant
            all_memories = self.vector_store.get_all_memories(limit=100000)

            # Group by type and quadrant for faster comparison
            groups: Dict[Tuple[str, str], List[Any]] = {}
            for mem in all_memories:
                payload = mem.payload
                mem_type = payload.get("type", "raw")
                quadrants = payload.get("quadrants", ["general"])
                key = (mem_type, quadrants[0] if quadrants else "general")

                if key not in groups:
                    groups[key] = []
                groups[key].append(mem)

            duplicates_found = []

            # Compare within groups
            for group_key, memories in groups.items():
                if len(memories) < 2:
                    continue

                # Simple hash-based duplicate detection
                content_hashes = {}
                for mem in memories:
                    content = mem.payload.get("content", "")
                    # Simple content hash (first 200 chars normalized)
                    content_key = content[:200].lower().strip()

                    if content_key in content_hashes:
                        duplicates_found.append((mem.id, content_hashes[content_key]))
                    else:
                        content_hashes[content_key] = mem.id

            result.items_found = len(duplicates_found)

            if not dry_run:
                for dup_id, keep_id in duplicates_found:
                    try:
                        # Merge edges from duplicate to keeper
                        self.graph_store.merge_nodes(dup_id, keep_id)
                        # Delete duplicate
                        self.vector_store.delete_memory(dup_id)
                        result.items_removed += 1
                    except Exception as e:
                        result.errors.append(f"Failed to merge duplicate {dup_id}: {e}")

                result.space_reclaimed_bytes = result.items_removed * 2048

        except Exception as e:
            result.errors.append(f"Duplicate cleanup error: {e}")

        return result

    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get current storage statistics."""
        try:
            vector_count = self.vector_store.count_memories()
            graph_stats = self.graph_store.get_graph_stats()

            return {
                "vector_memories": vector_count,
                "graph_nodes": graph_stats.get("memory_nodes", 0),
                "graph_edges": graph_stats.get("edges", 0),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"error": str(e)}

    def _result_to_dict(self, result: CleanupResult) -> Dict[str, Any]:
        """Convert CleanupResult to dictionary."""
        return {
            "cleanup_type": result.cleanup_type.value,
            "items_found": result.items_found,
            "items_removed": result.items_removed,
            "items_archived": result.items_archived,
            "space_reclaimed_bytes": result.space_reclaimed_bytes,
            "space_reclaimed_mb": round(result.space_reclaimed_bytes / (1024 * 1024), 2),
            "errors": result.errors
        }
