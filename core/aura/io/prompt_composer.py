import json
from typing import Any, Dict, List, Optional

import structlog

from aura.io.screen import ScreenCapture

logger = structlog.get_logger()


def build_messages(
    messages: List[Dict[str, Any]],
    screen_capture: Optional[ScreenCapture | str] = None,
    rag_context: Optional[List[str]] = None,
    tool_schemas: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Synthesizes the final message list for Ollama inference.

    - Injects tool schemas into the system prompt in XML format.
    - Prepends RAG context as a system message.
    - Attaches screen capture to the images array of the last user message.
    """
    final_messages = [dict(m) for m in messages]

    # 1. Extract Base64 from ScreenCapture or raw string
    base64_image = None
    has_screenshot = False

    if isinstance(screen_capture, ScreenCapture):
        base64_image = screen_capture.base64_jpeg
        has_screenshot = True
    elif isinstance(screen_capture, str):
        base64_image = screen_capture
        has_screenshot = True

    # 2. Inject Screen Capture into Messages
    if base64_image:
        # Find the last user message to attach the image
        for i in range(len(final_messages) - 1, -1, -1):
            if final_messages[i].get("role") == "user":
                if "images" not in final_messages[i]:
                    final_messages[i]["images"] = []
                # Ensure we don't duplicate the same capture
                if base64_image not in final_messages[i]["images"]:
                    final_messages[i]["images"].append(base64_image)
                break
        else:
            logger.warning("prompt_composer_no_user_message_for_image")

    # 3. Construct System Instructions
    system_content = (
        "You are Aura, a privacy-first, ambient AI assistant. "
        "You can see the user's screen and act on their operating system. "
        "Always be concise and helpful.\n\n"
    )

    if has_screenshot:
        system_content += (
            "IMPORTANT: A screenshot of the user's current screen is attached "
            "to their last message. Analyze it to provide context-aware help.\n\n"
        )

    if tool_schemas:
        system_content += "Available Tools:\n"
        system_content += "<tools>\n"
        for tool in tool_schemas:
            system_content += "  <tool>\n"
            system_content += f"    <name>{tool.get('name')}</name>\n"
            system_content += (
                f"    <description>{tool.get('description')}</description>\n"
            )
            system_content += (
                f"    <parameters>{json.dumps(tool.get('parameters'))}</parameters>\n"
            )
            system_content += "  </tool>\n"
        system_content += "</tools>\n\n"
        system_content += (
            "To call a tool, output a JSON object in the format: "
            '{"tool": "tool_name", "args": {"arg1": "val1"}}\n\n'
        )

    # 3. Construct Context Message (RAG)
    context_content = ""
    if rag_context:
        context_content = "Relevant context from user documents:\n"
        for chunk in rag_context:
            context_content += f"--- CHUNK ---\n{chunk}\n"
        context_content += "\nUse this context if relevant to the user's request.\n"

    # 4. Final Assembly
    # We want system instructions at the very top.
    # If there's already a system message in the history, we merge.
    # Otherwise, we prepend our generated one.

    combined_system_message = system_content + context_content

    # Check if the first message is a system message
    if final_messages and final_messages[0].get("role") == "system":
        # Prepend our logic to their existing system message
        original_content = final_messages[0].get("content", "")
        final_messages[0]["content"] = combined_system_message + original_content
    else:
        # Insert a new system message at the beginning
        final_messages.insert(0, {"role": "system", "content": combined_system_message})

    return final_messages
