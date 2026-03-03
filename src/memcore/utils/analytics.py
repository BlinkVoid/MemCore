"""
Memory Analytics System for MemCore

Provides insights and analysis:
- Memory usage patterns
- Quadrant distribution
- Temporal analysis (creation trends)
- Tag clouds and frequency analysis
- Memory health scores
- Access pattern analysis
"""
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Counter
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class QuadrantStats:
    """Statistics for a memory quadrant."""
    count: int
    avg_importance: float
    avg_confidence: float
    most_common_types: List[str]
    tag_count: int


@dataclass
class TemporalTrend:
    """Memory creation trend over time."""
    date: str
    count: int
    avg_importance: float


class MemoryAnalytics:
    """
    Analytics engine for memory insights.

    Provides comprehensive analysis of memory usage patterns,
    helping users understand their knowledge base.
    """

    def __init__(self, vector_store, graph_store):
        self.vector_store = vector_store
        self.graph_store = graph_store

    async def generate_full_report(self) -> Dict[str, Any]:
        """Generate a complete analytics report."""
        return {
            "overview": await self.get_overview_stats(),
            "quadrants": await self.get_quadrant_analysis(),
            "temporal": await self.get_temporal_analysis(),
            "tags": await self.get_tag_analysis(),
            "types": await self.get_type_distribution(),
            "health": await self.get_health_score(),
            "generated_at": datetime.now().isoformat()
        }

    async def get_overview_stats(self) -> Dict[str, Any]:
        """Get high-level overview statistics."""
        all_memories = self.vector_store.get_all_memories(limit=100000)

        if not all_memories:
            return {"total_memories": 0}

        total = len(all_memories)

        # Calculate averages
        importances = [m.payload.get("importance", 0.5) for m in all_memories]
        avg_importance = sum(importances) / len(importances)

        # High importance count
        high_importance = sum(1 for i in importances if i >= 0.8)

        # Total tags
        all_tags = set()
        for mem in all_memories:
            tags = mem.payload.get("tags", [])
            all_tags.update(tags)

        # Date range
        dates = []
        for mem in all_memories:
            created = mem.payload.get("created_at")
            if created:
                try:
                    if isinstance(created, str):
                        dates.append(datetime.fromisoformat(created.replace('Z', '+00:00')))
                except:
                    pass

        oldest = min(dates) if dates else None
        newest = max(dates) if dates else None

        return {
            "total_memories": total,
            "average_importance": round(avg_importance, 3),
            "high_importance_count": high_importance,
            "unique_tags": len(all_tags),
            "date_range": {
                "oldest": oldest.isoformat() if oldest else None,
                "newest": newest.isoformat() if newest else None,
                "span_days": (newest - oldest).days if oldest and newest else 0
            }
        }

    async def get_quadrant_analysis(self) -> Dict[str, QuadrantStats]:
        """Analyze memories by quadrant."""
        all_memories = self.vector_store.get_all_memories(limit=100000)

        quadrant_data = defaultdict(lambda: {
            "memories": [],
            "importances": [],
            "confidences": [],
            "types": [],
            "tags": set()
        })

        for mem in all_memories:
            payload = mem.payload
            quadrants = payload.get("quadrants", ["general"])

            for quadrant in quadrants:
                qd = quadrant_data[quadrant]
                qd["memories"].append(mem)
                qd["importances"].append(payload.get("importance", 0.5))
                qd["confidences"].append(payload.get("confidence", "medium"))
                qd["types"].append(payload.get("type", "raw"))
                qd["tags"].update(payload.get("tags", []))

        result = {}
        for quadrant, data in quadrant_data.items():
            type_counts = Counter(data["types"])
            avg_imp = sum(data["importances"]) / len(data["importances"]) if data["importances"] else 0

            # Convert confidence to numeric
            conf_map = {"high": 1.0, "medium": 0.5, "low": 0.0}
            conf_scores = [conf_map.get(c, 0.5) for c in data["confidences"]]
            avg_conf = sum(conf_scores) / len(conf_scores) if conf_scores else 0

            result[quadrant] = QuadrantStats(
                count=len(data["memories"]),
                avg_importance=round(avg_imp, 3),
                avg_confidence=round(avg_conf, 3),
                most_common_types=[t for t, _ in type_counts.most_common(3)],
                tag_count=len(data["tags"])
            )

        return result

    async def get_temporal_analysis(self, days: int = 30) -> List[TemporalTrend]:
        """Analyze memory creation trends over time."""
        all_memories = self.vector_store.get_all_memories(limit=100000)

        # Group by date
        daily_data = defaultdict(lambda: {"count": 0, "importances": []})

        cutoff = datetime.now() - timedelta(days=days)

        for mem in all_memories:
            created = mem.payload.get("created_at")
            if not created:
                continue

            try:
                if isinstance(created, str):
                    dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                else:
                    dt = created

                if dt < cutoff:
                    continue

                date_key = dt.strftime("%Y-%m-%d")
                daily_data[date_key]["count"] += 1
                daily_data[date_key]["importances"].append(
                    mem.payload.get("importance", 0.5)
                )
            except:
                continue

        # Build trends
        trends = []
        for date in sorted(daily_data.keys()):
            data = daily_data[date]
            avg_imp = sum(data["importances"]) / len(data["importances"]) if data["importances"] else 0
            trends.append(TemporalTrend(
                date=date,
                count=data["count"],
                avg_importance=round(avg_imp, 3)
            ))

        return trends

    async def get_tag_analysis(self, top_n: int = 20) -> Dict[str, Any]:
        """Analyze tag usage patterns."""
        all_memories = self.vector_store.get_all_memories(limit=100000)

        tag_counts = Counter()
        tag_importance = defaultdict(list)
        tag_quadrants = defaultdict(set)

        for mem in all_memories:
            payload = mem.payload
            tags = payload.get("tags", [])
            importance = payload.get("importance", 0.5)
            quadrants = payload.get("quadrants", ["general"])

            for tag in tags:
                tag_counts[tag] += 1
                tag_importance[tag].append(importance)
                tag_quadrants[tag].update(quadrants)

        # Build tag stats
        tag_stats = []
        for tag, count in tag_counts.most_common(top_n):
            avg_imp = sum(tag_importance[tag]) / len(tag_importance[tag])
            tag_stats.append({
                "tag": tag,
                "count": count,
                "avg_importance": round(avg_imp, 3),
                "quadrants": list(tag_quadrants[tag])
            })

        return {
            "total_unique_tags": len(tag_counts),
            "top_tags": tag_stats,
            "tag_distribution": {
                "high_usage": sum(1 for c in tag_counts.values() if c >= 10),
                "medium_usage": sum(1 for c in tag_counts.values() if 3 <= c < 10),
                "low_usage": sum(1 for c in tag_counts.values() if c < 3)
            }
        }

    async def get_type_distribution(self) -> Dict[str, int]:
        """Get distribution of memory types."""
        all_memories = self.vector_store.get_all_memories(limit=100000)

        type_counts = Counter()
        for mem in all_memories:
            mem_type = mem.payload.get("type", "raw")
            type_counts[mem_type] += 1

        return dict(type_counts)

    async def get_health_score(self) -> Dict[str, Any]:
        """Calculate overall memory system health score."""
        all_memories = self.vector_store.get_all_memories(limit=100000)
        graph_stats = self.graph_store.get_graph_stats()

        if not all_memories:
            return {"overall": 0, "status": "empty"}

        # Factors:
        # 1. Diversity (quadrant coverage)
        quadrants = set()
        for mem in all_memories:
            quadrants.update(mem.payload.get("quadrants", ["general"]))
        quadrant_score = len(quadrants) / 4.0  # 4 main quadrants

        # 2. Importance distribution
        importances = [m.payload.get("importance", 0.5) for m in all_memories]
        high_quality = sum(1 for i in importances if i >= 0.7)
        quality_score = high_quality / len(importances)

        # 3. Recency (recent activity)
        recent_cutoff = datetime.now() - timedelta(days=7)
        recent_count = 0
        for mem in all_memories:
            accessed = mem.payload.get("last_accessed")
            if accessed:
                try:
                    if isinstance(accessed, str):
                        dt = datetime.fromisoformat(accessed.replace('Z', '+00:00'))
                        if dt > recent_cutoff:
                            recent_count += 1
                except:
                    pass

        activity_score = min(recent_count / 10.0, 1.0)  # Cap at 10 recent items

        # 4. Connectivity (graph edges per node)
        node_count = graph_stats.get("memory_nodes", 1)
        edge_count = graph_stats.get("edges", 0)
        connectivity = min(edge_count / max(node_count * 2, 1), 1.0)

        # Overall score (weighted average)
        overall = (
            quadrant_score * 0.25 +
            quality_score * 0.30 +
            activity_score * 0.25 +
            connectivity * 0.20
        )

        # Determine status
        if overall >= 0.8:
            status = "excellent"
        elif overall >= 0.6:
            status = "good"
        elif overall >= 0.4:
            status = "fair"
        else:
            status = "needs_attention"

        return {
            "overall": round(overall, 3),
            "status": status,
            "factors": {
                "quadrant_coverage": round(quadrant_score, 3),
                "quality_ratio": round(quality_score, 3),
                "recent_activity": round(activity_score, 3),
                "connectivity": round(connectivity, 3)
            }
        }

    async def get_memory_clusters(self, min_cluster_size: int = 3) -> List[Dict[str, Any]]:
        """
        Identify clusters of related memories using graph analysis.
        """
        # Get connected components from graph
        clusters = self.graph_store.get_connected_components(min_size=min_cluster_size)

        cluster_stats = []
        for i, node_ids in enumerate(clusters[:10], 1):  # Top 10 clusters
            # Get memory details for cluster
            memories = []
            for node_id in node_ids[:5]:  # Sample first 5
                mem_data = self.vector_store.get_memory_by_id(node_id)
                if mem_data:
                    memories.append({
                        "id": node_id,
                        "summary": mem_data[0].payload.get("summary", "Unknown")
                    })

            cluster_stats.append({
                "cluster_id": i,
                "size": len(node_ids),
                "sample_memories": memories
            })

        return cluster_stats
