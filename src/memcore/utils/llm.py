import asyncio
import litellm
import logging
import os
import json
import shutil
import warnings
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastembed import TextEmbedding

logger = logging.getLogger(__name__)


def _log_activity(operation: str, model: str, tier: str, status: str = "success", error: str = None):
    """Log LLM activity to the activity log file."""
    try:
        # Determine project root for log path
        project_root = Path(__file__).parent.parent.parent.parent
        log_dir = project_root / "dataCrystal" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "activity.jsonl"

        entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "model": model,
            "tier": tier,
            "status": status
        }
        if error:
            entry["error"] = error

        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        # Silently fail - logging shouldn't break the app
        pass

# Provider API key environment variable mapping
PROVIDER_API_KEYS = {
    "bedrock": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
    "gemini": ["GEMINI_API_KEY"],
    "kimi": ["MOONSHOT_API_KEY"],
    "deepseek": ["DEEPSEEK_API_KEY"],
    "ollama": [],  # No API key needed for local LLM
}

# Default embedding model for all providers
# IMPORTANT: Changing this after data is stored requires re-indexing!
# DEFAULT: intfloat/multilingual-e5-large - Multilingual, supports 100+ languages including Chinese
# Alternative: BAAI/bge-base-en-v1.5 (768-dim, 210MB) - English-only, smaller
DEFAULT_EMBEDDING_MODEL = "intfloat/multilingual-e5-large"  # 1024-dim, 2.24GB, multilingual

MODEL_CATALOGUE = {
    "bedrock": {
        "fast": "bedrock/anthropic.claude-3-5-haiku-20241022-v1:0",
        "strong": "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
        "embedding": f"local/{DEFAULT_EMBEDDING_MODEL}"  # Vendor-agnostic local embedding
    },
    "gemini": {
        "fast": "gemini/gemini-2.0-flash",
        "strong": "gemini/gemini-2.0-pro-exp-02-05",
        "embedding": f"local/{DEFAULT_EMBEDDING_MODEL}"  # Vendor-agnostic local embedding
    },
    "kimi": {
        "fast": "moonshot/moonshot-v1-8k",
        "strong": "moonshot/moonshot-v2-5-32k",
        "embedding": f"local/{DEFAULT_EMBEDDING_MODEL}"  # Vendor-agnostic local embedding
    },
    "deepseek": {
        "fast": "deepseek/deepseek-chat",
        "strong": "deepseek/deepseek-reasoner",
        "embedding": f"local/{DEFAULT_EMBEDDING_MODEL}"  # Vendor-agnostic local embedding
    },
    "local": {
        "embedding": DEFAULT_EMBEDDING_MODEL
    },
    "ollama": {
        "fast": "ollama/qwen2.5:7b",  # Fast, good for routing
        "strong": "ollama/qwen2.5:14b",  # Better for consolidation
        "embedding": f"local/{DEFAULT_EMBEDDING_MODEL}"  # Still use local embeddings
    }
}

class LLMInterface:
    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or os.getenv("LLM_PROVIDER", "bedrock")
        self.catalogue = MODEL_CATALOGUE.get(self.provider, MODEL_CATALOGUE["bedrock"])
        self._local_embedder = None
        self._validate_api_key()
        
        # Eagerly initialize local embedder to avoid deadlocks in async tasks
        embedding_model = os.getenv("EMBEDDING_MODEL", self.catalogue.get("embedding", f"local/{DEFAULT_EMBEDDING_MODEL}"))
        if embedding_model.startswith("local/"):
            print(f"[LLM] Pre-initializing local embedder: {embedding_model}", flush=True)
            model_name = embedding_model.replace("local/", "")
            try:
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", message=".*mean pooling instead of CLS.*")
                    self._local_embedder = TextEmbedding(model_name=model_name, providers=["CPUExecutionProvider"])
                print("[LLM] Local embedder initialized.", flush=True)
            except Exception as e:
                print(f"[LLM] Failed to initialize local embedder: {e}", flush=True)

    def _validate_api_key(self):
        """Validates that required API keys are set for the selected provider."""
        required_keys = PROVIDER_API_KEYS.get(self.provider, [])
        missing_keys = [key for key in required_keys if not os.getenv(key)]
        if missing_keys:
            raise ValueError(
                f"Provider '{self.provider}' requires the following environment variables: {', '.join(missing_keys)}. "
                f"Please set them in your .env file."
            )

    def get_model(self, tier: str) -> str:
        """Resolves the model string based on provider and tier."""
        env_override = os.getenv(f"LLM_MODEL_{tier.upper()}")
        if env_override:
            return env_override
        return self.catalogue.get(tier, self.catalogue["fast"])

    async def completion(self, messages: List[Dict[str, str]], tier: str = "fast", **kwargs) -> str:
        model = self.get_model(tier)

        # Route to CLI backend if model starts with "cli/"
        if model.startswith("cli/"):
            return await self._cli_completion(model, messages, tier, **kwargs)

        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                **kwargs
            )
            _log_activity("completion", model, tier, "success")
            return response.choices[0].message.content
        except Exception as e:
            _log_activity("completion", model, tier, "error", str(e))
            raise

    async def _cli_completion(self, model: str, messages: List[Dict[str, str]], tier: str, **kwargs) -> str:
        """Route completion through a CLI tool (claude, kimi) using subscription instead of API.

        Model format: cli/<tool>  e.g. cli/claude, cli/kimi
        """
        cli_tool = model.replace("cli/", "")

        if not shutil.which(cli_tool):
            raise RuntimeError(f"CLI tool '{cli_tool}' not found on PATH")

        # Flatten messages into a single prompt
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.append(f"[System Instructions]\n{content}\n")
            else:
                prompt_parts.append(content)

        prompt = "\n\n".join(prompt_parts)

        # If JSON output was requested, add explicit instruction
        if kwargs.get("response_format", {}).get("type") == "json_object":
            prompt += "\n\nIMPORTANT: Respond with valid JSON only. No markdown fences, no explanation."

        # Build CLI command
        if cli_tool == "claude":
            cmd = ["claude", "-p", prompt, "--allowedTools", "", "--output-format", "text"]
        elif cli_tool == "kimi":
            cmd = ["kimi", "--print", "--final-message-only", "-p", prompt]
        else:
            raise ValueError(f"Unsupported CLI tool: {cli_tool}. Use 'claude' or 'kimi'.")

        logger.info("CLI completion via %s (tier=%s, prompt_len=%d)", cli_tool, tier, len(prompt))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            response = stdout.decode("utf-8", errors="replace").strip()

            if proc.returncode != 0:
                err_msg = stderr.decode("utf-8", errors="replace").strip()
                raise RuntimeError(f"{cli_tool} exited with code {proc.returncode}: {err_msg}")

            if not response:
                raise RuntimeError(f"{cli_tool} returned empty response")

            # Strip markdown JSON fences if present
            if response.startswith("```json"):
                response = response.removeprefix("```json").removesuffix("```").strip()
            elif response.startswith("```"):
                response = response.removeprefix("```").removesuffix("```").strip()

            _log_activity("cli_completion", cli_tool, tier, "success")
            return response
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            _log_activity("cli_completion", cli_tool, tier, "error", "timeout after 120s")
            raise RuntimeError(f"{cli_tool} timed out after 120 seconds")
        except Exception as e:
            _log_activity("cli_completion", cli_tool, tier, "error", str(e))
            raise

    async def get_embedding(self, text: str) -> List[float]:
        embedding_model = os.getenv("EMBEDDING_MODEL", self.catalogue.get("embedding", f"local/{DEFAULT_EMBEDDING_MODEL}"))
        
        if embedding_model.startswith("local/"):
            if self._local_embedder is None:
                model_name = embedding_model.replace("local/", "")
                # Initialize fastembed with the specified model
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", message=".*mean pooling instead of CLS.*")
                    try:
                        self._local_embedder = TextEmbedding(model_name=model_name, providers=["CPUExecutionProvider"])
                    except Exception:
                        # Fallback to default if model name not recognized
                        self._local_embedder = TextEmbedding(providers=["CPUExecutionProvider"])
            
            # fastembed's embed() returns a generator of numpy arrays
            embeddings = list(self._local_embedder.embed([text]))
            return embeddings[0].tolist()
        
        # Fallback to cloud embedding via litellm (for vendors that require cloud embeddings)
        response = await litellm.aembedding(
            model=embedding_model,
            input=[text]
        )
        return response.data[0].embedding

    def get_embedding_dimension(self) -> int:
        """Returns the expected dimension of the current embedding model."""
        embedding_model = os.getenv("EMBEDDING_MODEL", self.catalogue.get("embedding", f"local/{DEFAULT_EMBEDDING_MODEL}"))
        
        if embedding_model.startswith("local/"):
            model_name = embedding_model.replace("local/", "")
            # Common local model dimensions
            if "bge-small" in model_name.lower():
                return 384  # BGE-small: 384-dim (lightweight, lower quality)
            if "bge-base" in model_name.lower():
                return 768  # BGE-base: 768-dim (recommended balance)
            if "bge-large" in model_name.lower():
                return 1024  # BGE-large: 1024-dim (highest quality, slower)
            if "bge-m3" in model_name.lower():
                return 1024  # BGE-M3: 1024-dim (multilingual, state-of-the-art)
            if "gte-large" in model_name.lower() or "mxbai-embed-large" in model_name.lower():
                return 1024  # Other 1024-dim models
            if "snowflake-arctic-embed-m" in model_name.lower():
                return 768  # Snowflake M series: 768-dim
            if "snowflake-arctic-embed-l" in model_name.lower():
                return 1024  # Snowflake L series: 1024-dim
            if "multilingual-e5-large" in model_name.lower():
                return 1024  # E5-large: 1024-dim
            if "minilm" in model_name.lower() or "all-minilm" in model_name.lower():
                return 384  # MiniLM: 384-dim
            if "jina-embeddings-v2" in model_name.lower() and "small" not in model_name.lower():
                return 768  # Jina base models: 768-dim
            if "nomic-embed" in model_name.lower():
                return 768  # Nomic: 768-dim
            return 768  # Default: assume 768-dim for unknown local models
        
        # Standard cloud dimensions (if user explicitly overrides to use cloud)
        if "titan-embed-text-v2" in embedding_model: return 1024
        if "text-embedding-3-small" in embedding_model: return 1536
        if "text-embedding-3-large" in embedding_model: return 3072
        if "text-embedding-004" in embedding_model: return 768
        if "moonshot-embed" in embedding_model: return 1536
        return 1536 # Default fallback
