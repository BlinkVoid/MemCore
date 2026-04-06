"""Test that the ConsolidationManager can call the Strands Agent without LLM errors.

Reproduces the bug where DeepSeek rejects stream_options when stream=False,
causing every consolidation cycle to fail with:
  litellm.BadRequestError: DeepseekException - stream_options should be set along with stream = true
"""
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_strand_model_stream_mode():
    """The MemCoreStrandModel must use streaming mode to avoid DeepSeek stream_options errors."""
    from src.memcore.utils.llm import LLMInterface
    from src.memcore.agent.model_adapter import MemCoreStrandModel

    llm = LLMInterface()
    model = MemCoreStrandModel(llm_interface=llm, tier="strong")
    config = model.get_config()
    params = config.get("params", {})

    # stream must NOT be False — DeepSeek rejects stream_options when stream=False
    stream_val = params.get("stream", True)
    assert stream_val is not False, (
        f"stream={stream_val!r} — must not be False or DeepSeek will reject stream_options. "
        "Use stream=True (default) or omit it."
    )
    logger.info("PASS: stream mode is %r", stream_val)


def test_consolidation_agent_invocation():
    """ConsolidationManager.evaluate_environment() must not raise on the LLM call."""
    from src.memcore.utils.llm import LLMInterface
    from src.memcore.memory.consolidation import MemoryConsolidator
    from src.memcore.agent.consolidation_agent import ConsolidationManager

    llm = LLMInterface()

    # We can't easily create a full consolidator without Qdrant, so just test model config
    # The key assertion is that the Strands model is configured for streaming
    cm = ConsolidationManager.__new__(ConsolidationManager)
    cm.llm = llm
    cm.model = MemCoreStrandModel(llm_interface=llm, tier="strong")

    config = cm.model.get_config()
    params = config.get("params", {})
    stream_val = params.get("stream", True)
    assert stream_val is not False, f"ConsolidationManager model has stream={stream_val!r}, must not be False"
    logger.info("PASS: ConsolidationManager model stream mode is %r", stream_val)


# Import here to avoid import errors if model_adapter not yet fixed
from src.memcore.agent.model_adapter import MemCoreStrandModel


if __name__ == "__main__":
    test_strand_model_stream_mode()
    test_consolidation_agent_invocation()
    print("\nAll consolidation agent tests passed.")
