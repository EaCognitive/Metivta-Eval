"""WebSocket router for real-time evaluation updates."""

from __future__ import annotations

import json
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.database.supabase_manager import db

router = APIRouter()


class ConnectionManager:
    """Track websocket connections and subscriptions."""

    def __init__(self) -> None:
        self.active_connections: dict[str, list[WebSocket]] = {}
        self.evaluation_subscriptions: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        """Register accepted websocket for a user."""
        await websocket.accept()
        self.active_connections.setdefault(user_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        """Remove websocket from active and subscription maps."""
        if user_id in self.active_connections and websocket in self.active_connections[user_id]:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

        for evaluation_id in list(self.evaluation_subscriptions.keys()):
            sockets = self.evaluation_subscriptions[evaluation_id]
            if websocket in sockets:
                sockets.remove(websocket)
            if not sockets:
                del self.evaluation_subscriptions[evaluation_id]

    def subscribe_to_evaluation(self, websocket: WebSocket, evaluation_id: str) -> None:
        """Subscribe websocket to one evaluation feed."""
        self.evaluation_subscriptions.setdefault(evaluation_id, [])
        if websocket not in self.evaluation_subscriptions[evaluation_id]:
            self.evaluation_subscriptions[evaluation_id].append(websocket)

    def unsubscribe_from_evaluation(self, websocket: WebSocket, evaluation_id: str) -> None:
        """Unsubscribe websocket from one evaluation feed."""
        if (
            evaluation_id in self.evaluation_subscriptions
            and websocket in self.evaluation_subscriptions[evaluation_id]
        ):
            self.evaluation_subscriptions[evaluation_id].remove(websocket)

    async def send_personal_message(self, message: dict[str, Any], user_id: str) -> None:
        """Send JSON message to one user."""
        for connection in self.active_connections.get(user_id, []):
            with suppress(Exception):
                await connection.send_json(message)

    async def broadcast_to_evaluation(self, evaluation_id: str, message: dict[str, Any]) -> None:
        """Broadcast JSON message to evaluation subscribers."""
        for connection in self.evaluation_subscriptions.get(evaluation_id, []):
            with suppress(Exception):
                await connection.send_json(message)

    async def broadcast_to_all(self, message: dict[str, Any]) -> None:
        """Broadcast JSON message to all connected users."""
        for connections in self.active_connections.values():
            for connection in connections:
                with suppress(Exception):
                    await connection.send_json(message)


manager = ConnectionManager()


def create_message(
    msg_type: str,
    payload: dict[str, Any],
    evaluation_id: str | None = None,
) -> dict[str, Any]:
    """Build standard websocket payload envelope."""
    return {
        "type": msg_type,
        "timestamp": datetime.now(UTC).isoformat(),
        "evaluation_id": evaluation_id,
        "payload": payload,
    }


@router.websocket("/events")
async def websocket_events(websocket: WebSocket) -> None:
    """Accept websocket events stream with bearer token query param."""
    token = websocket.query_params.get("token", "")
    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return

    user = db.get_user_from_access_token(token)
    if user is None:
        await websocket.close(code=4003, reason="Invalid token")
        return

    user_id = str(user["id"])
    await manager.connect(websocket, user_id)

    try:
        await websocket.send_json(
            create_message(
                "connected",
                {"message": "Connected to MetivtaEval events", "user_id": user_id},
            )
        )

        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json(create_message("error", {"message": "Invalid JSON"}))
                continue

            action = message.get("action")
            evaluation_id = message.get("evaluation_id")

            if action == "subscribe" and evaluation_id:
                manager.subscribe_to_evaluation(websocket, str(evaluation_id))
                await websocket.send_json(
                    create_message(
                        "subscribed",
                        {"message": f"Subscribed to evaluation {evaluation_id}"},
                        str(evaluation_id),
                    )
                )
                continue

            if action == "unsubscribe" and evaluation_id:
                manager.unsubscribe_from_evaluation(websocket, str(evaluation_id))
                await websocket.send_json(
                    create_message(
                        "unsubscribed",
                        {"message": f"Unsubscribed from evaluation {evaluation_id}"},
                        str(evaluation_id),
                    )
                )
                continue

            if action == "ping":
                await websocket.send_json(create_message("pong", {"ok": True}))
                continue

            await websocket.send_json(create_message("error", {"message": "Unknown action"}))

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)


async def notify_evaluation_started(evaluation_id: UUID, user_id: str) -> None:
    """Notify that an evaluation started."""
    message = create_message(
        "evaluation.started",
        {"status": "running", "progress": 0},
        str(evaluation_id),
    )
    await manager.broadcast_to_evaluation(str(evaluation_id), message)
    await manager.send_personal_message(message, user_id)


async def notify_evaluation_progress(
    evaluation_id: UUID,
    user_id: str,
    progress: int,
    metrics: dict[str, Any] | None = None,
) -> None:
    """Notify progress updates for an evaluation."""
    message = create_message(
        "evaluation.progress",
        {"progress": progress, "metrics": metrics or {}},
        str(evaluation_id),
    )
    await manager.broadcast_to_evaluation(str(evaluation_id), message)
    await manager.send_personal_message(message, user_id)


async def notify_evaluation_completed(
    evaluation_id: UUID, user_id: str, results: dict[str, Any]
) -> None:
    """Notify completion of an evaluation."""
    message = create_message(
        "evaluation.completed",
        {"status": "completed", "progress": 100, "results": results},
        str(evaluation_id),
    )
    await manager.broadcast_to_evaluation(str(evaluation_id), message)
    await manager.send_personal_message(message, user_id)


async def notify_evaluation_failed(evaluation_id: UUID, user_id: str, error: str) -> None:
    """Notify evaluation failure."""
    message = create_message(
        "evaluation.failed",
        {"status": "failed", "error": error},
        str(evaluation_id),
    )
    await manager.broadcast_to_evaluation(str(evaluation_id), message)
    await manager.send_personal_message(message, user_id)


async def notify_leaderboard_updated() -> None:
    """Notify all users leaderboard has new data."""
    await manager.broadcast_to_all(
        create_message("leaderboard.updated", {"message": "Leaderboard has been updated"})
    )
