import logging
from collections.abc import Sequence
from typing import Any

import anthropic

from querya.llm.base import ChatMessage, LLMError, LLMResponse, ToolCall, ToolSpec, Usage

logger = logging.getLogger(__name__)


class AnthropicClient:
    provider = "anthropic"

    def __init__(
        self,
        *,
        model: str,
        max_tokens: int,
        timeout_s: float,
        api_key: str | None = None,
        show_thinking: bool = True,
        client: anthropic.AsyncAnthropic | None = None,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.show_thinking = show_thinking
        self._client = client or anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout_s)

    async def complete(
        self,
        *,
        system: str,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
    ) -> LLMResponse:
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": to_anthropic_messages(messages),
            "tools": [
                {"name": t.name, "description": t.description, "input_schema": t.parameters}
                for t in tools
            ],
        }
        if self.show_thinking:
            params["thinking"] = {"type": "adaptive", "display": "summarized"}
        try:
            response = await self._client.messages.create(**params)
        except anthropic.APIError as exc:
            logger.warning("anthropic request failed: %s", exc)
            raise LLMError(f"Anthropic API error: {exc}") from exc

        text_parts: list[str] = []
        thinking_parts: list[str] = []
        calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "thinking" and block.thinking:
                thinking_parts.append(block.thinking)
            elif block.type == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name, arguments=dict(block.input)))

        return LLMResponse(
            text="\n".join(text_parts).strip(),
            reasoning="\n".join(thinking_parts).strip() or None,
            tool_calls=calls,
            usage=Usage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            ),
            model=response.model,
            provider_payload=[block.to_dict() for block in response.content],
        )


def to_anthropic_messages(messages: Sequence[ChatMessage]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for msg in messages:
        if msg.role == "user":
            out.append({"role": "user", "content": msg.content})
        elif msg.role == "assistant":
            content: list[dict[str, Any]]
            if msg.provider_payload is not None:
                content = list(msg.provider_payload)
            else:
                content = [{"type": "text", "text": msg.content}] if msg.content else []
                content += [
                    {"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments}
                    for c in msg.tool_calls
                ]
            out.append({"role": "assistant", "content": content})
        else:
            block = {
                "type": "tool_result",
                "tool_use_id": msg.tool_call_id,
                "content": msg.content,
                "is_error": msg.is_error,
            }
            # Results for parallel tool calls belong in a single user turn.
            prev = out[-1] if out else None
            if prev and prev["role"] == "user" and isinstance(prev["content"], list):
                prev["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
    return out
