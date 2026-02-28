import asyncio
import uuid
from src.memcore.main import MemCoreAgent

async def run_scenario_coding_transfer():
    print("
--- Scenario A: Coding Knowledge Transfer ---")
    agent = MemCoreAgent()
    
    # 1. Ingest raw memory
    print("Ingesting naming convention...")
    await agent.handle_mem_rem({
        "content": "All files in the 'core' directory must use snake_case naming.",
        "summary": "Core naming convention",
        "quadrants": ["coding"]
    })
    
    # 2. Force Consolidation (Simulating Sleep Phase)
    print("Triggering manual consolidation...")
    # In a real test, we'd mock the raw memories to consolidate
    # For now, we'll verify the storage manually
    
    # 3. Request Context
    print("Requesting naming context...")
    response = await agent.handle_mem_request("How should I name a file in the core folder?")
    print(f"Agent Response:
{response[0].text}")

async def run_scenario_conflict():
    print("
--- Scenario B: Identity Conflict ---")
    agent = MemCoreAgent()
    
    # 1. Initial Fact
    await agent.handle_mem_rem({
        "content": "The user is an expert in Python.",
        "summary": "User expertise",
        "quadrants": ["personal"]
    })
    
    # 2. Conflicting Fact
    await agent.handle_mem_rem({
        "content": "The user is moving away from Python to Rust.",
        "summary": "User technology shift",
        "quadrants": ["personal"]
    })
    
    # 3. Request
    response = await agent.handle_mem_request("What is the user's primary language?")
    print(f"Agent Response:
{response[0].text}")

async def run_scenario_feedback_rca():
    print("\n--- Scenario C: Feedback Loop & RCA ---")
    agent = MemCoreAgent()
    
    # 1. Store two similar but different memories
    print("Storing version-specific memories...")
    await agent.handle_mem_rem({
        "content": "Library Version 1.0 uses 'init_v1()'.",
        "summary": "V1 Initialization",
        "quadrants": ["coding"]
    })
    
    # 2. Request context (might get the wrong one or both)
    print("Requesting init call...")
    response = await agent.handle_mem_request("How do I initialize the library?")
    print(f"Agent Response:\n{response[0].text}")
    
    # Assume the first result was [ID_1] and it was wrong
    import re
    match = re.search(r"\[([a-f0-9\-]+)\]", response[0].text)
    if match:
        wrong_id = match.group(1)
        # 3. Submit Negative Feedback
        print(f"Submitting negative feedback for {wrong_id}...")
        feedback_res = await agent.handle_feedback({
            "request_id": "some-request-id", # In real use, we'd use the real one
            "memory_id": wrong_id,
            "rating": -1,
            "reason": "This is for the old version, I need v2."
        })
        print(f"RCA Result:\n{feedback_res[0].text}")

async def run_scenario_doc_sync():
    print("\n--- Scenario D: Document Synchronization ---")
    import os
    import tempfile
    
    # Create a temporary obsidian vault
    with tempfile.TemporaryDirectory() as tmp_vault:
        os.environ["OBSIDIAN_VAULT_PATH"] = tmp_vault
        agent = MemCoreAgent()
        
        # 1. Create a markdown file
        test_file = os.path.join(tmp_vault, "project_notes.md")
        with open(test_file, "w") as f:
            f.write("# Project Alpha\nThis project uses Python 3.12.")
        
        print(f"Created file: {test_file}")
        
        # 2. Manually trigger reindex (normally the watcher does this)
        await agent.reindex_file(test_file)
        
        # 3. Query the memory
        response = await agent.handle_mem_query("What version of Python does Project Alpha use?")
        print(f"Initial Response:\n{response[0].text}")
        
        # 4. Modify the file
        print("Modifying file...")
        with open(test_file, "w") as f:
            f.write("# Project Alpha\nThis project now uses Python 3.13 and Rust.")
        
        # 5. Trigger reindex again
        await agent.reindex_file(test_file)
        
        # 6. Query again
        response = await agent.handle_mem_query("What version of Python does Project Alpha use?")
        print(f"Updated Response:\n{response[0].text}")

if __name__ == "__main__":
    asyncio.run(run_scenario_coding_transfer())
    asyncio.run(run_scenario_conflict())
    asyncio.run(run_scenario_feedback_rca())
    asyncio.run(run_scenario_doc_sync())
