#!/usr/bin/env python3
import asyncio
import os
import sys

# Add src to python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.memcore.main import MemCoreServer

async def main():
    print("Initializing MemCore...")
    server = MemCoreServer()
    
    print("\n--- Test 1: Empty State Evaluation ---")
    result = await server.consolidation_manager.evaluate_environment()
    print("Agent Result:\n", result)
    
    print("\n--- Test 2: Inserting Raw Memory & Evaluating ---")
    import uuid
    from datetime import datetime
    mem_id = str(uuid.uuid4())
    payload = {
        "content": "The user is testing the MemCore Strand Agent integration. They prefer testing incrementally.",
        "summary": "Strand Agent Testing Preferences",
        "quadrants": ["personal", "coding"],
        "timestamp": datetime.now().isoformat(),
        "type": "raw"
    }
    
    # Store directly, simulating mem_save without the background task so we can `await` it synchronously
    vector = await server.llm.get_embedding(payload["content"])
    server.vector_store.upsert_memory(mem_id, vector, payload)
    server.graph_store.add_node(mem_id, "memory", {"summary": payload["summary"], "type": "raw"})
    print("Inserted new memory.")
    
    # Wait a second for database writes
    await asyncio.sleep(1)
    
    print("\n--- Triggering ConsolidationManager... ---")
    result2 = await server.consolidation_manager.evaluate_environment()
    print("Agent Result 2:\n", result2)

    # Gracefully close Qdrant to avoid async shutdown errors
    server.vector_store.client.close()

if __name__ == "__main__":
    asyncio.run(main())
