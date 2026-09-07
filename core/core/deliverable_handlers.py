"""Deliverable RPC handlers for SWARAJ Agent Core."""

from typing import Any
from storage.deliverable_store import DeliverableStore


async def handle_deliverable_rpc(
    method: str,
    msg_id: Any,
    params: dict[str, Any],
    dstore: DeliverableStore,
    send_response_fn: Any,
) -> bool:
    """Dispatch deliverable-related JSON-RPC methods."""
    if method == "deliverable/create":
        deliv_data = params.get("deliverable", {})
        created = await dstore.create_deliverable(deliv_data)
        send_response_fn({"jsonrpc": "2.0", "id": msg_id, "result": {"deliverable": created}})
        return True

    if method == "deliverable/list":
        p_id = params.get("projectId")
        deliverables = await dstore.list_deliverables(p_id, params.get("sessionId"))
        send_response_fn({"jsonrpc": "2.0", "id": msg_id, "result": {"deliverables": deliverables}})
        return True

    if method == "deliverable/get":
        d_id = params.get("deliverableId")
        d = await dstore.get_deliverable(d_id) if d_id else None
        send_response_fn({"jsonrpc": "2.0", "id": msg_id, "result": {"deliverable": d}})
        return True

    if method == "deliverable/verify_field":
        d_id = params.get("deliverableId", "")
        f_id = params.get("fieldId", "")
        res = await dstore.verify_field(d_id, f_id)
        send_response_fn({"jsonrpc": "2.0", "id": msg_id, "result": {"deliverable": res}})
        return True

    if method == "deliverable/cite_claim":
        d_id = params.get("deliverableId", "")
        c_id = params.get("citationId", "")
        res = await dstore.cite_claim(d_id, c_id)
        send_response_fn({"jsonrpc": "2.0", "id": msg_id, "result": {"deliverable": res}})
        return True

    if method == "deliverable/approve":
        d_id = params.get("deliverableId", "")
        checker_id = params.get("checkerId", "user_kulkarni")
        checker_name = params.get("checkerName", "P. V. Kulkarni")
        checker_desig = params.get("checkerDesignation", "Chief Manager - Mechanical")
        narrative = params.get("editedNarrative")
        try:
            res = await dstore.approve(d_id, checker_id, checker_name, checker_desig, narrative)
            send_response_fn({"jsonrpc": "2.0", "id": msg_id, "result": res})
        except Exception as err:
            send_response_fn({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32000, "message": str(err)}})
        return True

    if method == "deliverable/reject":
        d_id = params.get("deliverableId", "")
        checker_id = params.get("checkerId", "user_kulkarni")
        checker_name = params.get("checkerName", "P. V. Kulkarni")
        checker_desig = params.get("checkerDesignation", "Chief Manager - Mechanical")
        reason = params.get("reason", "")
        try:
            res = await dstore.reject(d_id, checker_id, checker_name, checker_desig, reason)
            send_response_fn({"jsonrpc": "2.0", "id": msg_id, "result": res})
        except Exception as err:
            send_response_fn({"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32000, "message": str(err)}})
        return True

    return False
