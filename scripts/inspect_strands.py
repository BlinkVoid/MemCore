import importlib.metadata

try:
    files = importlib.metadata.files('strands-agents')
    top_level = set()
    for f in files:
        parts = f.parts
        if len(parts) > 0 and not parts[0].endswith('.dist-info'):
            top_level.add(parts[0])
    print("TOP LEVEL MODULES:", top_level)
except Exception as e:
    print(f"Error: {e}")
