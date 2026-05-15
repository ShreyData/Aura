import asyncio
import json
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch

from aura.main import app
from aura.api.deps import get_ollama_client as get_ollama_client_dep
from aura.api.deps import get_approval_gate as get_approval_gate_dep

from aura.tools.approval import get_approval_gate, reset_approval_gate
from aura.tools.registry import get_tool_registry, reset_tool_registry
from aura.events import get_event_bus, reset_event_bus
from aura.ollama.client import ToolCallDetected


# Mocking the OllamaClient for tool detection
class MockOllamaClient:
    def __init__(self):
        self.call_count = 0

    async def health(self):
        return True

    async def stream_chat(self, model, messages, tools):
        self.call_count += 1
        if self.call_count == 1:
            # Simulate detection of a HIGH risk tool call
            raise ToolCallDetected(
                tool_name="write_file",
                tool_args={"path": "test.txt", "content": "hello"},
                partial_response="Writing to file...",
            )
        else:
            # Simulate final response after tool execution
            yield "File written successfully."


@pytest_asyncio.fixture(autouse=True)
async def setup_teardown():
    """Reset singletons and start event bus for each test."""
    reset_approval_gate()
    reset_tool_registry()
    reset_event_bus()

    # Manually populate app state for tests
    bus = get_event_bus()
    registry = get_tool_registry()
    gate = get_approval_gate()

    app.state.event_bus = bus
    app.state.tool_registry = registry
    app.state.approval_gate = gate

    # Start the event bus dispatch loop manually since lifespan doesn't run in ASGITransport
    dispatch_task = asyncio.create_task(bus.dispatch_loop())

    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()

    dispatch_task.cancel()
    try:
        await dispatch_task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_tool_approval_flow_approved():
    """
    Test 2.12: Full approval flow.
    Ensures that a HIGH risk tool call triggers the gate and executes when approved.
    """
    mock_ollama = MockOllamaClient()
    gate = app.state.approval_gate
    bus = app.state.event_bus

    app.dependency_overrides[get_ollama_client_dep] = lambda: mock_ollama
    app.dependency_overrides[get_approval_gate_dep] = lambda: gate

    approval_needed_event = asyncio.Event()
    captured_request_id = None

    async def on_approval_needed(event_type, payload):
        nonlocal captured_request_id
        captured_request_id = payload.get("request_id")
        approval_needed_event.set()

    await bus.subscribe("tool_approval_needed", on_approval_needed)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            # Background task to approve the tool call once it hits the bus
            async def auto_approve():
                await asyncio.wait_for(approval_needed_event.wait(), timeout=5.0)
                await ac.post(
                    "/v1/tools/approve",
                    json={"request_id": captured_request_id, "approved": True},
                )

            approve_task = asyncio.create_task(auto_approve())

            chat_payload = {
                "model": "gemma",
                "messages": [{"role": "user", "content": "write hello to test.txt"}],
                "stream": True,
            }

            full_text = ""
            async with ac.stream(
                "POST", "/v1/chat/completions", json=chat_payload
            ) as response:
                assert response.status_code == 200
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and not line.endswith("[DONE]"):
                        try:
                            chunk = json.loads(line[6:])
                            content = chunk["choices"][0]["delta"].get("content", "")
                            if content:
                                full_text += content
                        except:
                            continue

            await approve_task
            assert "File written successfully" in full_text
    finally:
        await bus.unsubscribe("tool_approval_needed", on_approval_needed)


@pytest.mark.asyncio
async def test_tool_approval_flow_denied():
    """
    Test 2.12: Denial flow.
    Ensures that a HIGH risk tool call is skipped when denied by user.
    """
    mock_ollama = MockOllamaClient()
    gate = app.state.approval_gate
    bus = app.state.event_bus

    app.dependency_overrides[get_ollama_client_dep] = lambda: mock_ollama
    app.dependency_overrides[get_approval_gate_dep] = lambda: gate

    approval_needed_event = asyncio.Event()
    captured_request_id = None

    async def on_approval_needed(event_type, payload):
        nonlocal captured_request_id
        captured_request_id = payload.get("request_id")
        approval_needed_event.set()

    await bus.subscribe("tool_approval_needed", on_approval_needed)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:

            async def auto_deny():
                await asyncio.wait_for(approval_needed_event.wait(), timeout=5.0)
                await ac.post(
                    "/v1/tools/approve",
                    json={"request_id": captured_request_id, "approved": False},
                )

            deny_task = asyncio.create_task(auto_deny())

            chat_payload = {
                "model": "gemma",
                "messages": [{"role": "user", "content": "write hello to test.txt"}],
                "stream": True,
            }

            full_text = ""
            async with ac.stream(
                "POST", "/v1/chat/completions", json=chat_payload
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        full_text += line

            await deny_task
            assert "denied by user" in full_text
    finally:
        await bus.unsubscribe("tool_approval_needed", on_approval_needed)


@pytest.mark.asyncio
async def test_tool_approval_timeout():
    """
    Test 2.12: Timeout behavior.
    Ensures that tool calls are automatically denied on timeout.
    """
    mock_ollama = MockOllamaClient()
    app.dependency_overrides[get_ollama_client_dep] = lambda: mock_ollama

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            resp = await ac.post(
                "/v1/chat/completions",
                json={
                    "model": "gemma",
                    "messages": [
                        {"role": "user", "content": "write hello to test.txt"}
                    ],
                    "stream": False,
                },
            )
            assert "denied by user" in resp.text
