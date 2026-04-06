"""
Analytics API for detailed MemCore statistics.
Provides aggregated data for charts and visualizations.
"""
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
from collections import Counter, defaultdict


class AnalyticsProvider:
    """Provides statistical analysis of MemCore data."""

    def __init__(self, vector_store, graph_store, data_dir: str):
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.data_dir = data_dir

    async def get_detailed_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics for dashboard charts."""
        # Get all memories (sample for performance)
        all_memories = self._get_all_memories(limit=5000)

        return {
            "quadrants": self._analyze_quadrants(all_memories),
            "tags": self._analyze_tags(all_memories),
            "types": self._analyze_types(all_memories),
            "importance": self._analyze_importance(all_memories),
            "timeline": self._analyze_timeline(all_memories),
            "sources": self._analyze_sources(all_memories),
            "tag_quadrant_matrix": self._analyze_tag_quadrant_matrix(all_memories),
            "top_files": self._get_top_files(all_memories),
            "generated_at": datetime.now().isoformat()
        }

    def _get_all_memories(self, limit: int = 5000) -> List[Dict]:
        """Fetch memories from vector store."""
        try:
            # Use scroll to get all memories
            results = self.vector_store.client.scroll(
                collection_name=self.vector_store.collection_name,
                limit=limit,
                with_payload=True
            )[0]

            memories = []
            for res in results:
                memories.append({
                    "id": res.id,
                    **res.payload
                })
            return memories
        except Exception as e:
            print(f"[Analytics] Error fetching memories: {e}")
            return []

    def _analyze_quadrants(self, memories: List[Dict]) -> Dict[str, Any]:
        """Analyze quadrant distribution."""
        quadrant_counts = Counter()

        for mem in memories:
            quadrants = mem.get("quadrants", ["general"])
            for q in quadrants:
                quadrant_counts[q] += 1

        total = sum(quadrant_counts.values())

        return {
            name: {
                "count": count,
                "percent": round(count / total * 100, 1) if total > 0 else 0
            }
            for name, count in sorted(quadrant_counts.items(), key=lambda x: x[1], reverse=True)
        }

    def _analyze_tags(self, memories: List[Dict]) -> Dict[str, int]:
        """Analyze tag frequency."""
        tag_counts = Counter()

        for mem in memories:
            tags = mem.get("tags", [])
            tag_counts.update(tags)

        # Return top 50 tags
        return dict(tag_counts.most_common(50))

    def _analyze_types(self, memories: List[Dict]) -> Dict[str, Any]:
        """Analyze memory type distribution."""
        type_counts = Counter()

        for mem in memories:
            mem_type = mem.get("type", "raw")
            type_counts[mem_type] += 1

        total = sum(type_counts.values())

        return {
            mem_type: {
                "count": count,
                "percent": round(count / total * 100, 1) if total > 0 else 0
            }
            for mem_type, count in type_counts.items()
        }

    def _analyze_importance(self, memories: List[Dict]) -> Dict[str, Any]:
        """Analyze importance distribution."""
        high = sum(1 for m in memories if m.get("importance", 0.5) >= 0.8)
        medium = sum(1 for m in memories if 0.5 <= m.get("importance", 0.5) < 0.8)
        low = sum(1 for m in memories if m.get("importance", 0.5) < 0.5)

        total = len(memories)

        return {
            "high": {"count": high, "percent": round(high / total * 100, 1) if total > 0 else 0},
            "medium": {"count": medium, "percent": round(medium / total * 100, 1) if total > 0 else 0},
            "low": {"count": low, "percent": round(low / total * 100, 1) if total > 0 else 0},
            "average": round(sum(m.get("importance", 0.5) for m in memories) / total, 2) if total > 0 else 0
        }

    def _analyze_timeline(self, memories: List[Dict]) -> List[Dict[str, Any]]:
        """Analyze ingestion timeline (last 30 days)."""
        # Group by date
        daily_counts = defaultdict(int)

        for mem in memories:
            created = mem.get("created_at")
            if created:
                try:
                    date = created.split("T")[0]  # Get YYYY-MM-DD
                    daily_counts[date] += 1
                except:
                    pass

        # Fill in last 30 days
        end_date = datetime.now()
        timeline = []

        for i in range(30, -1, -1):
            date = (end_date - timedelta(days=i)).strftime("%Y-%m-%d")
            timeline.append({
                "date": date,
                "count": daily_counts.get(date, 0)
            })

        return timeline

    def _analyze_sources(self, memories: List[Dict]) -> Dict[str, Any]:
        """Analyze memory sources."""
        source_counts = Counter()

        for mem in memories:
            source = mem.get("source_uri", "")
            if source.startswith("obsidian://") or source.startswith("file://"):
                source_counts["obsidian"] += 1
            elif "api" in source.lower():
                source_counts["api"] += 1
            else:
                source_counts["direct"] += 1

        total = sum(source_counts.values())

        return {
            source: {
                "count": count,
                "percent": round(count / total * 100, 1) if total > 0 else 0
            }
            for source, count in source_counts.items()
        }

    def _analyze_tag_quadrant_matrix(self, memories: List[Dict]) -> Dict[str, Dict[str, int]]:
        """Analyze tag-quadrant co-occurrence."""
        matrix = defaultdict(lambda: defaultdict(int))

        for mem in memories:
            tags = mem.get("tags", [])
            quadrants = mem.get("quadrants", ["general"])

            for tag in tags[:5]:  # Top 5 tags per memory
                for quadrant in quadrants:
                    matrix[tag][quadrant] += 1

        # Convert to regular dict
        return {tag: dict(quadrants) for tag, quadrants in matrix.items()}

    def _get_top_files(self, memories: List[Dict], limit: int = 10) -> List[Dict[str, Any]]:
        """Get top source files by memory count."""
        file_counts = Counter()

        for mem in memories:
            source = mem.get("source_uri", "")
            if source:
                # Extract filename
                filename = source.split("/")[-1].split("\\")[-1]
                if filename:
                    file_counts[filename] += 1

        return [
            {"name": name, "count": count}
            for name, count in file_counts.most_common(limit)
        ]

    def get_activity_heatmap(self, days: int = 90) -> Dict[str, Any]:
        """Get activity data for calendar heatmap."""
        memories = self._get_all_memories(limit=10000)

        # Group by date
        daily_counts = defaultdict(int)

        for mem in memories:
            created = mem.get("created_at")
            if created:
                try:
                    date = created.split("T")[0]
                    daily_counts[date] += 1
                except:
                    pass

        # Find most active day for normalization
        max_count = max(daily_counts.values()) if daily_counts else 1

        return {
            "days": days,
            "max_count": max_count,
            "data": dict(daily_counts)
        }
