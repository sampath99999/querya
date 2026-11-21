from collections.abc import Sequence
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class LLMError(RuntimeError):
    pass


class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class Usage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "tool"]
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None
    is_error: bool = False
    # Provider-native assistant content (e.g. Anthropic thinking blocks) that has to be
    # replayed verbatim on the next request.
    provider_payload: Any = None


class LLMResponse(BaseModel):
    text: str = ""
    reasoning: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    model: str
    provider_payload: Any = None

    def to_message(self) -> ChatMessage:
        return ChatMessage(
            role="assistant",
            content=self.text,
            tool_calls=self.tool_calls,
            provider_payload=self.provider_payload,
        )


@runtime_checkable
class LLMClient(Protocol):
    provider: str
    model: str

    async def complete(
        self,
        *,
        system: str,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
    ) -> LLMResponse: ...
