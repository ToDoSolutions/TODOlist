"""Endpoint MCP (Model Context Protocol) — Streamable HTTP.

JSON-RPC 2.0 sobre POST /api/mcp/: initialize, tools/list, tools/call,
ping y notifications/*. Auth igual que el resto de la API (Bearer API key
`tl_...`, JWT o cookie); las tools exigen el scope correspondiente.

Respuestas en application/json (single response — el server no usa SSE
push; los clientes MCP aceptan JSON plano en Streamable HTTP).
"""
import json

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .tools import call_tool, list_tools, tool_result_payload

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "todolist-mcp", "version": "1.0.0"}
_MAX_BODY = 64 * 1024


def _rpc_error(req_id, code, message):
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message},
    }


def _rpc_result(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _handle(request, msg):
    """Procesa un mensaje JSON-RPC. Devuelve dict respuesta o None
    (notifications no tienen respuesta)."""
    method = msg.get("method")
    req_id = msg.get("id")

    if isinstance(method, str) and method.startswith("notifications/"):
        return None  # notifications nunca responden
    if req_id is None:
        # request sin id → notificación inválida; ignorar
        return None

    if method == "initialize":
        return _rpc_result(req_id, {
            "protocolVersion": msg.get("params", {}).get(
                "protocolVersion", PROTOCOL_VERSION
            ),
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
        })
    if method == "ping":
        return _rpc_result(req_id, {})
    if method == "tools/list":
        return _rpc_result(req_id, {"tools": list_tools()})
    if method == "tools/call":
        params = msg.get("params") or {}
        result, error = call_tool(
            request, params.get("name", ""), params.get("arguments")
        )
        return _rpc_result(req_id, tool_result_payload(result, error))
    return _rpc_error(req_id, -32601, f"Method not found: {method}")


@api_view(["POST"])
@permission_classes([IsAuthenticated])  # scope por tool en call_tool
def mcp_endpoint(request):
    if len(request.body) > _MAX_BODY:
        return Response(status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return Response(
            _rpc_error(None, -32700, "Parse error"),
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(payload, list):
        if not payload:
            return Response(
                _rpc_error(None, -32600, "Invalid Request"),
                status=status.HTTP_400_BAD_REQUEST,
            )
        out = [_handle(request, m) for m in payload if isinstance(m, dict)]
        out = [r for r in out if r is not None]
        if not out:
            return Response(status=status.HTTP_202_ACCEPTED)
        return Response(out)

    if not isinstance(payload, dict):
        return Response(
            _rpc_error(None, -32600, "Invalid Request"),
            status=status.HTTP_400_BAD_REQUEST,
        )
    result = _handle(request, payload)
    if result is None:
        return Response(status=status.HTTP_202_ACCEPTED)
    return Response(result)
