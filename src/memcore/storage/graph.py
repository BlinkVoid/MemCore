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

    def get_node_metadata(self, node_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT metadata FROM nodes WHERE id = ?", (node_id,))
            row = cursor.fetchone()
            return json.loads(row[0]) if row else None

    def add_request_node(self, request_id: str, query: str, answer: str):
        metadata = {"query": query, "answer": answer}
        self.add_node(request_id, "request", metadata)
