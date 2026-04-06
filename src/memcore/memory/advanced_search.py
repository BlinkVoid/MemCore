"""
Advanced Search System for MemCore

Provides filtering capabilities for memories based on:
- Date ranges (created, last accessed)
- Memory type (raw, consolidated, reflection)
- Confidence level
- Tags
- Importance range
- Quadrants
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum


class DateFilterType(Enum):
    """Types of date filters."""
    CREATED_AFTER = "created_after"
    CREATED_BEFORE = "created_before"
    CREATED_BETWEEN = "created_between"
    ACCESSED_AFTER = "accessed_after"
    ACCESSED_BEFORE = "accessed_before"
    ACCESSED_BETWEEN = "accessed_between"


@dataclass
class SearchFilters:
    """Container for all search filter parameters."""
    # Type filters
    memory_types: Optional[List[str]] = None  # raw, consolidated, reflection, instruction

    # Quadrant filters
    quadrants: Optional[List[str]] = None

    # Confidence filters
    min_confidence: Optional[str] = None  # high, medium, low

    # Importance range
    min_importance: Optional[float] = None  # 0.0 - 1.0
    max_importance: Optional[float] = None  # 0.0 - 1.0

    # Date filters
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    accessed_after: Optional[datetime] = None
    accessed_before: Optional[datetime] = None

    # Tag filters
    include_tags: Optional[List[str]] = None
    exclude_tags: Optional[List[str]] = None

    # Content filters
    content_contains: Optional[str] = None
    summary_contains: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert filters to dictionary for serialization."""
        result = {}
        for key, value in self.__dict__.items():
            if value is not None:
                if isinstance(value, datetime):
                    result[key] = value.isoformat()
                else:
                    result[key] = value
        return result


class AdvancedSearch:
    """
    Advanced search with multiple filter criteria.

    Performs semantic search first, then applies filters.
    """

    CONFIDENCE_LEVELS = {
        "high": 3,
        "medium": 2,
        "low": 1
    }

    def __init__(self, vector_store, llm):
        self.vector_store = vector_store
        self.llm = llm

    async def search(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Perform advanced search with filters.

        Args:
            query: Semantic search query (can be empty for filter-only search)
            filters: SearchFilters object with filter criteria
            limit: Maximum results to return
            offset: Pagination offset

        Returns:
            Dictionary with results and metadata
        """
        # If no query, we'll do a brute force scan (slower)
        # If query provided, do semantic search first
        if query and query.strip():
            query_vector = await self.llm.get_embedding(query)
            # Get more results than needed for filtering
            raw_results = self.vector_store.search_memories(
                query_vector,
                limit=limit * 3,  # Get extra for filtering
                filter_quadrants=filters.quadrants if filters else None
            )
        else:
            # No semantic query - get recent memories
            raw_results = self._get_all_memories(limit * 3)

        # Apply filters
        filtered_results = self._apply_filters(raw_results, filters)

        # Apply pagination
        total = len(filtered_results)
        paginated_results = filtered_results[offset:offset + limit]

        return {
            "results": paginated_results,
            "total": total,
            "returned": len(paginated_results),
            "offset": offset,
            "limit": limit,
            "filters_applied": filters.to_dict() if filters else {}
        }

    def _get_all_memories(self, limit: int) -> List[Any]:
        """Get memories without semantic query (uses dummy vector)."""
        import numpy as np
        dummy_vector = np.zeros(self.llm.get_embedding_dimension())
        return self.vector_store.search_memories(dummy_vector, limit=limit)

    def _apply_filters(
        self,
        results: List[Any],
        filters: Optional[SearchFilters]
    ) -> List[Dict[str, Any]]:
        """Apply all filter criteria to results."""
        if not filters:
            return [self._format_result(r) for r in results]

        filtered = []
        for result in results:
            payload = result.payload

            # Type filter
            if filters.memory_types:
                mem_type = payload.get("type", "raw")
                if mem_type not in filters.memory_types:
                    continue

            # Confidence filter
            if filters.min_confidence:
                conf = payload.get("confidence", "medium")
                if self.CONFIDENCE_LEVELS.get(conf, 0) < self.CONFIDENCE_LEVELS.get(filters.min_confidence, 0):
                    continue

            # Importance range filter
            importance = payload.get("importance", 0.5)
            if filters.min_importance is not None and importance < filters.min_importance:
                continue
            if filters.max_importance is not None and importance > filters.max_importance:
                continue

            # Date filters
            created_at = payload.get("created_at")
            if created_at:
                try:
                    if isinstance(created_at, str):
                        created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    else:
                        created_dt = created_at

                    if filters.created_after and created_dt < filters.created_after:
                        continue
                    if filters.created_before and created_dt > filters.created_before:
                        continue
                except:
                    pass

            last_accessed = payload.get("last_accessed")
            if last_accessed:
                try:
                    if isinstance(last_accessed, str):
                        accessed_dt = datetime.fromisoformat(last_accessed.replace('Z', '+00:00'))
                    else:
                        accessed_dt = last_accessed

                    if filters.accessed_after and accessed_dt < filters.accessed_after:
                        continue
                    if filters.accessed_before and accessed_dt > filters.accessed_before:
                        continue
                except:
                    pass

            # Tag filters
            tags = payload.get("tags", [])
            if filters.include_tags:
                if not any(tag in tags for tag in filters.include_tags):
                    continue
            if filters.exclude_tags:
                if any(tag in tags for tag in filters.exclude_tags):
                    continue

            # Content filters (case-insensitive substring match)
            if filters.content_contains:
                content = payload.get("content", "").lower()
                if filters.content_contains.lower() not in content:
                    continue

            if filters.summary_contains:
                summary = payload.get("summary", "").lower()
                if filters.summary_contains.lower() not in summary:
                    continue

            # Passed all filters
            filtered.append(self._format_result(result))

        return filtered

    def _format_result(self, result: Any) -> Dict[str, Any]:
        """Format a search result for return."""
        payload = result.payload
        return {
            "id": result.id,
            "summary": payload.get("summary", ""),
            "content": payload.get("content", ""),
            "content_preview": payload.get("content", "")[:200],
            "type": payload.get("type", "raw"),
            "quadrants": payload.get("quadrants", ["general"]),
            "confidence": payload.get("confidence", "medium"),
            "importance": payload.get("importance", 0.5),
            "tags": payload.get("tags", []),
            "created_at": payload.get("created_at"),
            "last_accessed": payload.get("last_accessed"),
            "source_uri": payload.get("source_uri"),
            "score": getattr(result, 'score', 1.0)
        }

    def parse_date_filter(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats."""
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%SZ"
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None

    def get_available_tags(self) -> List[str]:
        """Get all unique tags across memories."""
        # This would need a scan of all memories
        # For now, return empty list
        return []

    def get_date_range(self) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Get the date range of all memories."""
        # This would need a scan of all memories
        # For now, return None
        return None, None
