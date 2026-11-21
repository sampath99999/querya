from types import SimpleNamespace
from typing import Any

import pytest
from anthropic.types import Message
from openai.types.chat import ChatCompletion

from querya.agent import TOOL_SPECS
from querya.config import Settings
from querya.llm import ChatMessage, ToolCall, build_llm_client
from querya.llm.anthropic_client import AnthropicClient, to_anthropic_messages
from querya.llm.openai_client import OpenAICompatibleClient, to_openai_messages


class _Recorder:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.kwargs: dict[str, Any] = {}

    async def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        return self.response


def _anthropic_message() -> Message:
    return Message.model_validate(
        {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-5-5",
            "content": [
                {"type": "thinking", "thinking": "Need orders by month.", "signature": "sig"},
                {"type": "text", "text": "Checking the orders table."},
                {"type": "tool_use", "id": "tu_1", "name": "run_sql", "input": {"sql": "SELECT 1"}},
            ],
            "stop_reason": "tool_use",
            "stop_sequence": None,
            "usage": {"input_tokens": 812, "output_tokens": 64},
        }
    )


async def test_anthropic_client_parses_blocks_and_sends_no_sampling_params() -> None:
    recorder = _Recorder(_anthropic_message())
    client = AnthropicClient(
        model="claude-opus-5-5",
        max_tokens=4096,
        timeout_s=30,
        client=SimpleNamespace(messages=recorder),  # type: ignore[arg-type]
    )
    response = await client.complete(
        system="sys", messages=[ChatMessage(role="user", content="hi")], tools=TOOL_SPECS
    )

    assert response.text == "Checking the orders table."
    assert response.reasoning == "Need orders by month."
    assert response.tool_calls == [
        ToolCall(id="tu_1", name="run_sql", arguments={"sql": "SELECT 1"})
    ]
    assert response.usage.input_tokens == 812
    assert response.provider_payload[0]["type"] == "thinking"

    sent = recorder.kwargs
    assert sent["model"] == "claude-opus-5-5"
    assert sent["system"] == "sys"
    assert sent["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert "temperature" not in sent
    assert "tool_choice" not in sent
    assert {t["name"] for t in sent["tools"]} == {s.name for s in TOOL_SPECS}
    assert "input_schema" in sent["tools"][0]


def test_anthropic_history_replays_payload_and_groups_tool_results() -> None:
    payload = [{"type": "thinking", "thinking": "x", "signature": "s"}]
    messages = [
        ChatMessage(role="user", content="q"),
        ChatMessage(
            role="assistant",
            content="ignored when payload is present",
            tool_calls=[ToolCall(id="a", name="list_tables")],
            provider_payload=payload,
        ),
        ChatMessage(role="tool", tool_call_id="a", content="tables"),
        ChatMessage(role="tool", tool_call_id="b", content="boom", is_error=True),
        ChatMessage(role="assistant", content="", tool_calls=[ToolCall(id="c", name="run_sql")]),
    ]
    out = to_anthropic_messages(messages)
    assert [m["role"] for m in out] == ["user", "assistant", "user", "assistant"]
    assert out[1]["content"] == payload
    assert [b["tool_use_id"] for b in out[2]["content"]] == ["a", "b"]
    assert out[2]["content"][1]["is_error"] is True
    assert out[3]["content"] == [{"type": "tool_use", "id": "c", "name": "run_sql", "input": {}}]


def _completion(message: dict[str, Any]) -> ChatCompletion:
    return ChatCompletion.model_validate(
        {
            "id": "c1",
            "object": "chat.completion",
            "created": 0,
            "model": "qwen2.5-coder:3b",
            "choices": [{"index": 0, "finish_reason": "tool_calls", "message": message}],
            "usage": {"prompt_tokens": 900, "completion_tokens": 40, "total_tokens": 940},
        }
    )


def _openai_client(response: ChatCompletion) -> tuple[OpenAICompatibleClient, _Recorder]:
    recorder = _Recorder(response)
    fake = SimpleNamespace(chat=SimpleNamespace(completions=recorder))
    client = OpenAICompatibleClient(
        model="qwen2.5-coder:3b",
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        max_tokens=1024,
        timeout_s=30,
        client=fake,  # type: ignore[arg-type]
    )
    return client, recorder


async def test_openai_client_parses_native_tool_calls() -> None:
    client, recorder = _openai_client(
        _completion(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "describe_table", "arguments": '{"table": "orders"}'},
                    },
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {"name": "run_sql", "arguments": "{not json"},
                    },
                ],
            }
        )
    )
    response = await client.complete(system="sys", messages=[], tools=TOOL_SPECS)
    assert response.tool_calls[0].arguments == {"table": "orders"}
    assert response.tool_calls[1].arguments == {"_unparsed": "{not json"}
    assert response.usage.output_tokens == 40
    assert recorder.kwargs["temperature"] == 0.0
    assert recorder.kwargs["messages"][0] == {"role": "system", "content": "sys"}
    assert recorder.kwargs["tools"][0]["type"] == "function"


@pytest.mark.parametrize(
    "content",
    [
        '{"name": "run_sql", "arguments": {"sql": "SELECT 1"}}',
        'Sure:\n```json\n{"name": "run_sql", "parameters": {"sql": "SELECT 1"}}\n```',
        '{"name": "run_sql", "arguments": "{\\"sql\\": \\"SELECT 1\\"}"}',
    ],
)
async def test_openai_client_recovers_tool_calls_printed_as_text(content: str) -> None:
    client, _ = _openai_client(_completion({"role": "assistant", "content": content}))
    response = await client.complete(system="sys", messages=[], tools=TOOL_SPECS)
    assert response.text == ""
    assert response.tool_calls[0].name == "run_sql"
    assert response.tool_calls[0].arguments == {"sql": "SELECT 1"}


async def test_openai_client_keeps_plain_text_and_unknown_json() -> None:
    client, _ = _openai_client(
        _completion({"role": "assistant", "content": '{"name": "rm_rf", "arguments": {}}'})
    )
    response = await client.complete(system="sys", messages=[], tools=TOOL_SPECS)
    assert response.tool_calls == []
    assert "rm_rf" in response.text


def test_openai_history_format() -> None:
    out = to_openai_messages(
        "sys",
        [
            ChatMessage(role="user", content="q"),
            ChatMessage(
                role="assistant",
                tool_calls=[ToolCall(id="x", name="run_sql", arguments={"sql": "SELECT 1"})],
            ),
            ChatMessage(role="tool", tool_call_id="x", content="1 row(s)"),
        ],
    )
    assert out[2]["content"] is None
    assert out[2]["tool_calls"][0]["function"]["arguments"] == '{"sql": "SELECT 1"}'
    assert out[3] == {"role": "tool", "tool_call_id": "x", "content": "1 row(s)"}


def test_factory_picks_provider_and_default_model() -> None:
    ollama = build_llm_client(Settings(_env_file=None))  # type: ignore[call-arg]
    assert ollama.provider == "openai"
    assert ollama.model == "qwen2.5-coder:3b"
    claude = build_llm_client(
        Settings(llm_provider="anthropic", anthropic_api_key="test-key", _env_file=None)  # type: ignore[call-arg, arg-type]
    )
    assert claude.provider == "anthropic"
    assert claude.model == "claude-opus-5-5"
