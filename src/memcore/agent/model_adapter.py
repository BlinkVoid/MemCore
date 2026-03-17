import logging
from typing import Any, Optional
from collections.abc import AsyncGenerator

from strands.models.litellm import LiteLLMModel
from strands.types.streaming import StreamEvent

from src.memcore.utils.llm import LLMInterface, _log_activity

logger = logging.getLogger(__name__)


class MemCoreStrandModel(LiteLLMModel):
    """Adapter bridging MemCore's LLMInterface with the Strands SDK's LiteLLMModel.

    Delegates all streaming/formatting to the SDK's battle-tested LiteLLMModel
    while using MemCore's LLMInterface for dynamic model name resolution and
    activity logging.
    """

    def __init__(
        self,
        llm_interface: LLMInterface,
        tier: str = "strong",
        system_prompt: Optional[str] = None,
    ):
        self.llm = llm_interface
        self.tier = tier
        self.system_prompt = system_prompt

        model_id = self.llm.get_model(self.tier)
        logger.info("MemCoreStrandModel initializing with model_id=%s, tier=%s", model_id, tier)

        # Initialize the parent LiteLLMModel with the resolved model name.
        # Must use stream=True (default) — DeepSeek rejects stream_options when stream=False.
        super().__init__(
            model_id=model_id,
        )

    # --- Override stream to add activity logging ---

    async def stream(
        self,
        messages: Any,
        tool_specs: Any | None = None,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Stream using the parent LiteLLMModel implementation with activity logging."""
        model_name = self.llm.get_model(self.tier)

        # Ensure model_id stays current (in case provider config changed at runtime)
        current_config = self.get_config()
        if current_config.get("model_id") != model_name:
            self.update_config(model_id=model_name)

        try:
            async for event in super().stream(
                messages,
                tool_specs=tool_specs,
                system_prompt=system_prompt,
                **kwargs,
            ):
                yield event
            _log_activity("strand_agent_stream", model_name, self.tier, "success")
        except Exception as e:
            _log_activity("strand_agent_stream", model_name, self.tier, "error", str(e))
            raise
