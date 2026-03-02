import sqlite3
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

class GraphStore:
    def __init__(self, db_path: str = "data/memcore_graph.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Nodes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    type TEXT,
                    source_uri TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Index for source_uri
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodes_source_uri ON nodes(source_uri)")
            # Edges table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS edges (
                    source TEXT,
                    target TEXT,
                    type TEXT,
                    weight REAL DEFAULT 1.0,
                    metadata TEXT,
                    PRIMARY KEY (source, target, type),
                    FOREIGN KEY (source) REFERENCES nodes (id),
                    FOREIGN KEY (target) REFERENCES nodes (id)
                )
            """)
            # System metadata table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()

    def set_metadata(self, key: str, value: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO system_metadata (key, value) VALUES (?, ?)", (key, value))
            conn.commit()

    def get_metadata(self, key: str) -> Optional[str]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM system_metadata WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else None

    def add_node(self, node_id: str, node_type: str, metadata: Dict[str, Any], source_uri: Optional[str] = None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO nodes (id, type, source_uri, metadata) VALUES (?, ?, ?, ?)",
                (node_id, node_type, source_uri, json.dumps(metadata))
            )
            conn.commit()

    def delete_nodes_by_source(self, source_uri: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Find all node IDs for this source
            cursor.execute("SELECT id FROM nodes WHERE source_uri = ?", (source_uri,))
            node_ids = [row[0] for row in cursor.fetchall()]
            
            if node_ids:
                placeholders = ','.join(['?'] * len(node_ids))
                # Delete related edges
                cursor.execute(f"DELETE FROM edges WHERE source IN ({placeholders}) OR target IN ({placeholders})", node_ids + node_ids)
                # Delete nodes
                cursor.execute(f"DELETE FROM nodes WHERE id IN ({placeholders})", node_ids)
            
            conn.commit()

    def add_edge(self, source: str, target: str, edge_type: str, weight: float = 1.0, metadata: Optional[Dict[str, Any]] = None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO edges (source, target, type, weight, metadata) VALUES (?, ?, ?, ?, ?)",
                (source, target, edge_type, weight, json.dumps(metadata or {}))
            )
            conn.commit()

    def update_edge_weight(self, source: str, target: str, edge_type: str, delta: float):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE edges SET weight = weight + ? WHERE source = ? AND target = ? AND type = ?",
                (delta, source, target, edge_type)
            )
            conn.commit()

    def get_related_nodes(self, node_id: str, edge_type: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT target, type, weight, metadata FROM edges WHERE source = ?"
        params = [node_id]
        if edge_type:
            query += " AND type = ?"
            params.append(edge_type)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_memory_weights(self, memory_ids: List[str], request_id: Optional[str] = None) -> Dict[str, float]:
        """
        Get dynamic weights for memories based on graph edge feedback.

        Returns a dict mapping memory_id -> weight_multiplier where:
        - 1.0 = neutral (no feedback or default)
        - >1.0 = positive feedback (up to 2.0 max)
        - <1.0 = negative feedback (down to 0.5 min)

        Combines:
        1. Direct request->memory edge weights (if request_id provided)
        2. Global popularity (average weight across all request edges)
        """
        if not memory_ids:
            return {}

        weights = {mid: 1.0 for mid in memory_ids}  # Default neutral

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 1. Get direct request->memory edges (specific context)
            if request_id:
                placeholders = ','.join(['?'] * len(memory_ids))
                cursor.execute(f"""
                    SELECT target, weight FROM edges
                    WHERE source = ? AND target IN ({placeholders}) AND type = 'FULFILLED_BY'
                """, (request_id,) + tuple(memory_ids))

                for row in cursor.fetchall():
                    mid = row['target']
                    weight = row['weight']
                    # Convert delta-based weight to multiplier
                    # weight > 1.0 means positive feedback, < 1.0 means negative
                    if weight > 1.0:
                        weights[mid] = min(2.0, 1.0 + (weight - 1.0) * 0.1)  # Cap at 2x boost
                    elif weight < 1.0:
                        weights[mid] = max(0.5, 1.0 + (weight - 1.0) * 0.1)  # Floor at 0.5x

            # 2. Get global popularity (average weight per memory)
            placeholders = ','.join(['?'] * len(memory_ids))
            cursor.execute(f"""
                SELECT target, AVG(weight) as avg_weight, COUNT(*) as edge_count
                FROM edges
                WHERE target IN ({placeholders}) AND type = 'FULFILLED_BY'
                GROUP BY target
            """, tuple(memory_ids))

            for row in cursor.fetchall():
                mid = row['target']
                avg_weight = row['avg_weight']
                edge_count = row['edge_count']

                # Only apply global weight if we have meaningful data (3+ edges)
                if edge_count >= 3:
                    # Blend with existing weight (70% direct, 30% global)
                    global_multiplier = 1.0 + (avg_weight - 1.0) * 0.05  # Dampened effect
                    global_multiplier = max(0.8, min(1.2, global_multiplier))  # Clamp
                    weights[mid] = weights[mid] * 0.7 + global_multiplier * 0.3

        return weights

    def get_node_metadata(self, node_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT metadata FROM nodes WHERE id = ?", (node_id,))
            row = cursor.fetchone()
            return json.loads(row[0]) if row else None

    def add_request_node(self, request_id: str, query: str, answer: str):
        metadata = {"query": query, "answer": answer}
        self.add_node(request_id, "request", metadata)

    def link_request_to_memory(self, request_id: str, memory_id: str, weight: float = 1.0):
        """Create a FULFILLED_BY edge linking a request to a memory that satisfied it."""
        self.add_edge(request_id, memory_id, "FULFILLED_BY", weight)

    def get_stats(self) -> Dict[str, Any]:
        """Returns statistics about the graph store."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Count nodes by type
            cursor.execute("SELECT type, COUNT(*) FROM nodes GROUP BY type")
            node_types = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Count total nodes
            cursor.execute("SELECT COUNT(*) FROM nodes")
            total_nodes = cursor.fetchone()[0]
            
            # Count edges by type
            cursor.execute("SELECT type, COUNT(*) FROM edges GROUP BY type")
            edge_types = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Count total edges
            cursor.execute("SELECT COUNT(*) FROM edges")
            total_edges = cursor.fetchone()[0]
            
            # Get last consolidation time
            last_consolidation = self.get_metadata("last_consolidation")
            
        return {
            "total_nodes": total_nodes,
            "nodes_by_type": node_types,
            "total_edges": total_edges,
            "edges_by_type": edge_types,
            "last_consolidation": last_consolidation,
            "db_path": self.db_path
        }
