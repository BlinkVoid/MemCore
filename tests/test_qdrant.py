from qdrant_client import QdrantClient
import os
from pathlib import Path

# Get project root (parent of tests directory)
project_root = Path(__file__).parent.parent
path = str(project_root / "dataCrystal" / "qdrant_storage")
print(f"Attempting to connect to Qdrant at {path}...")
try:
    client = QdrantClient(path=path)
    print("Success! Connection established.")
    collections = client.get_collections()
    print(f"Collections: {collections}")
except Exception as e:
    print(f"FAILED: {e}")
