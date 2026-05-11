import json
import pytest
import respx
from httpx import Response, ConnectError
from aura.ollama.client import OllamaClient, ToolCallDetected

@pytest.fixture
def client():
    return OllamaClient()

@pytest.mark.asyncio
@respx.mock
async def test_health_success(client):
    respx.get("http://127.0.0.1:11435/").mock(return_value=Response(200))
    assert await client.health() is True

@pytest.mark.asyncio
@respx.mock
async def test_health_failure(client):
    respx.get("http://127.0.0.1:11435/").mock(side_effect=ConnectError("Connection refused"))
    assert await client.health() is False

@pytest.mark.asyncio
@respx.mock
async def test_stream_chat_yields_tokens(client):
    stream_content = (
        json.dumps({"message": {"content": "Hello"}, "done": False}) + "\n" +
        json.dumps({"message": {"content": " world"}, "done": False}) + "\n" +
        json.dumps({"done": True}) + "\n"
    )
    respx.post("http://127.0.0.1:11435/api/chat").mock(return_value=Response(200, content=stream_content))
    
    tokens = []
    async for token in client.stream_chat(model="gemma:2b", messages=[{"role": "user", "content": "hi"}]):
        tokens.append(token)
    
    assert tokens == ["Hello", " world"]

@pytest.mark.asyncio
@respx.mock
async def test_stream_chat_raises_tool_call(client):
    stream_content = (
        json.dumps({"message": {"content": "I will check that for you."}, "done": False}) + "\n" +
        json.dumps({
            "message": {
                "tool_calls": [{
                    "function": {
                        "name": "get_weather",
                        "arguments": {"location": "London"}
                    }
                }]
            },
            "done": False
        }) + "\n"
    )
    respx.post("http://127.0.0.1:11435/api/chat").mock(return_value=Response(200, content=stream_content))
    
    with pytest.raises(ToolCallDetected) as excinfo:
        async for _ in client.stream_chat(model="gemma:2b", messages=[{"role": "user", "content": "weather in London"}]):
            pass
    
    assert excinfo.value.tool_name == "get_weather"
    assert excinfo.value.args == {"location": "London"}
    assert excinfo.value.partial_response == "I will check that for you."

@pytest.mark.asyncio
@respx.mock
async def test_pull_model_progress(client):
    stream_content = (
        json.dumps({"status": "downloading", "completed": 50, "total": 100}) + "\n" +
        json.dumps({"status": "downloading", "completed": 100, "total": 100}) + "\n" +
        json.dumps({"status": "success"}) + "\n"
    )
    respx.post("http://127.0.0.1:11435/api/pull").mock(return_value=Response(200, content=stream_content))
    
    progress_updates = []
    def on_progress(p):
        progress_updates.append(p)
    
    await client.pull_model(model="gemma:2b", on_progress=on_progress)
    
    assert len(progress_updates) >= 2
    assert progress_updates[0]["percent"] == 50
    assert progress_updates[1]["percent"] == 100
    assert progress_updates[-1]["status"] == "success"

@pytest.mark.asyncio
@respx.mock
async def test_list_models_success(client):
    mock_response = {
        "models": [
            {"name": "gemma:2b", "size": 1000},
            {"name": "nomic-embed-text", "size": 500}
        ]
    }
    respx.get("http://127.0.0.1:11435/api/tags").mock(return_value=Response(200, json=mock_response))
    
    models = await client.list_models()
    assert len(models) == 2
    assert models[0]["name"] == "gemma:2b"
