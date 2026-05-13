from typing import Annotated, Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from aura.api.schemas import PendingToolCall, ToolApprovalRequest
from aura.tools.registry import ToolRegistry, get_tool_registry
from aura.tools.approval import ApprovalGate, get_approval_gate

router = APIRouter(prefix="/v1/tools", tags=["tools"])


@router.get("")
async def list_tools(
    registry: Annotated[ToolRegistry, Depends(get_tool_registry)]
) -> List[Dict[str, Any]]:
    """
    Returns a list of all registered and available tools with their
    schemas and risk levels.
    """
    return registry.list_tools()


@router.get("/schemas")
async def get_tool_schemas(
    registry: Annotated[ToolRegistry, Depends(get_tool_registry)]
) -> List[Dict[str, Any]]:
    """
    Returns the JSON schemas for all available tools, ready for
    injection into the LLM system prompt.
    """
    return registry.generate_tool_schemas()


@router.get("/pending")
async def list_pending_tools(
    gate: Annotated[ApprovalGate, Depends(get_approval_gate)]
) -> List[PendingToolCall]:
    """
    Returns a list of all tool calls currently awaiting user approval.
    """
    return await gate.get_pending()


@router.post("/approve")
async def approve_tool(
    request: ToolApprovalRequest,
    gate: Annotated[ApprovalGate, Depends(get_approval_gate)]
) -> Dict[str, Any]:
    """
    Processes a user's response (approve/deny) for a pending tool call.
    """
    success = await gate.respond(request.request_id, request.approved)
    if not success:
        raise HTTPException(
            status_code=404, 
            detail=f"Pending tool call with ID '{request.request_id}' not found."
        )
    
    return {"status": "success", "message": "Tool approval response processed."}
