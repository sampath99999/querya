import json
import logging
import re
import uuid
from collections.abc import Sequence
from typing import Any

import openai

from querya.llm.base import ChatMessage, LLMError, LLMResponse, ToolCall, ToolSpec, Usage

logger = logging.getLogger(__name__)

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


class OpenAICompatibleClient:
    """Chat Completions client. Works with OpenAI and with Ollama's /v1 endpoint."""

    provider = "openai"

    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        api_key: str,
        max_tokens: int,
        timeout_s: float,
        temperature: float = 0.0,
        client: openai.AsyncOpenAI | None = None,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = client or openai.AsyncOpenAI(
            base_url=base_url, api_key=api_key, timeout=timeout_s
        )

    async def complete(
        self,
        *,
        system: str,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
    ) -> LLMResponse:
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=to_openai_messages(system, messages),  # type: ignore[arg-type]
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": t.name,
                            "description": t.description,
                            "parameters": t.parameters,
                        },
                    }
                    for t in tools
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        except openai.APIError as exc:
            logger.warning("openai-compatible request failed: %s", exc)
            raise LLMError(f"LLM API error: {exc}") from exc

        if not response.choices:
            raise LLMError("LLM returned no choices")
        message = response.choices[0].message
        text = (message.content or "").strip()
        calls = [
            ToolCall(
                id=call.id or _new_id(),
                name=call.function.name,
                arguments=_parse_arguments(call.function.arguments),
            )
            for call in (message.tool_calls or [])
            if call.type == "function"
        ]
        if not calls and text:
            inline = _inline_tool_call(text, {t.name for t in tools})
            if inline is not None:
                calls, text = [inline], ""

        usage = response.usage
        return LLMResponse(
            text=text,
            tool_calls=calls,
            usage=Usage(
                input_tokens=usage.prompt_tokens if usage else None,
                output_tokens=usage.completion_tokens if usage else None,
            ),
            model=response.model or self.model,
        )


def to_openai_messages(system: str, messages: Sequence[ChatMessage]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for msg in messages:
        if msg.role == "user":
            out.append({"role": "user", "content": msg.content})
        elif msg.role == "assistant":
            entry: dict[str, Any] = {"role": "assistant", "content": msg.content or None}
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
                    }
                    for c in msg.tool_calls
                ]
            out.append(entry)
        else:
            out.append({"role": "tool", "tool_call_id": msg.tool_call_id, "content": msg.content})
    return out


def _new_id() -> str:
    return f"call_{uuid.uuid4().hex[:12]}"


def _parse_arguments(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"_unparsed": raw}
    return parsed if isinstance(parsed, dict) else {"_unparsed": raw}


def _inline_tool_call(text: str, tool_names: set[str]) -> ToolCall | None:
    # Small local models sometimes print the tool call as JSON instead of using the
    # tool-calling channel. Accept it only when it clearly names one of our tools.
    match = _JSON_OBJECT_RE.search(text)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or payload.get("name") not in tool_names:
        return None
    args = payload.get("arguments", payload.get("parameters", {}))
    if isinstance(args, str):
        args = _parse_arguments(args)
    if not isinstance(args, dict):
        return None
    return ToolCall(id=_new_id(), name=payload["name"], arguments=args)
