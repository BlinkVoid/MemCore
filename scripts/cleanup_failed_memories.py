#!/usr/bin/env python3
"""
cleanup_failed_memories.py
Quick utility to purge permanently stuck consolidation jobs 
and their associated 'type: raw' Qdrant points.
"""

import os
import sys

# Add src to python path so explicit imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.memcore.storage.queue import ConsolidationQueue
from src.memcore.storage.vector import VectorStore

def main():
    print("Initializing MemCore stores...")
    # These initialize their DB connections on __init__
    queue = ConsolidationQueue()
    vector_store = VectorStore()
    
    print("\n--- Purging SQLite Queue Backlog ---")
    conn = __import__('sqlite3').connect(queue.db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM consolidation_jobs")
    job_count = cursor.fetchone()[0]
    
    cursor.execute("DELETE FROM consolidation_jobs")
    conn.commit()
    print(f"Purged {job_count} jobs from the SQLite consolidation_jobs table.")
    
    conn.close()

    print("\n--- Modifying Qdrant Bad Memories ---")
    # Get the current raw memories from Qdrant that were stalling the process
    raw_memories = vector_store.get_raw_memories(limit=1000)
    print(f"Found {len(raw_memories)} 'type: raw' memories in Qdrant.")
    
    count_marked_failed = 0
    for record in raw_memories:
        memory_id = record.id
        payload = record.payload or {}
        
        # Change type to failed_raw
        payload["type"] = "failed_raw"
        
        # Qdrant set_payload preserves vectors, so we just update the payload
        try:
            vector_store.update_memory(memory_id, payload)
            count_marked_failed += 1
        except Exception as e:
            print(f"Failed to update {memory_id}: {e}")

    print(f"Successfully marked {count_marked_failed} raw memories as 'failed_raw'.")
    print("\nCleanup Complete. The infinite loop target list is now clear.")

if __name__ == "__main__":
    main()
