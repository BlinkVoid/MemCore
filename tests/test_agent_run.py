from src.memcore.main import MemCoreAgent
import asyncio

async def test():
    print("Initializing agent...")
    agent = MemCoreAgent()
    print("Agent initialized. Starting run()...")
    # Minimal run logic
    await agent.run(mode="http", host="127.0.0.1", port=8080, dashboard_port=8081)

if __name__ == "__main__":
    try:
        asyncio.run(test())
    except KeyboardInterrupt:
        print("Stopped.")
