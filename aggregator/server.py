"""
Federated Aggregation Server.

FastAPI application that coordinates the federated learning process:
  - Hospital nodes register and receive tokens
  - Nodes upload model weight updates after local training
  - Server aggregates weights using FedAvg
  - Nodes download the latest global model

Run with:
    python -m aggregator.server
"""

import base64
import io
import math
import secrets
import logging
from collections import OrderedDict
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import torch
import uvicorn
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from aggregator.fedavg import federated_average
from config.settings import (
    AGGREGATOR_PORT,
    NUM_CLASSES,
    FEDERATED_ROUNDS,
)
from model.architecture import build_model

# ── Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("aggregator")

# ── In-memory state ─────────────────────────────────────────────────────
registered_nodes: dict[str, dict] = {}       # hospital_id → node info
pending_updates: list[dict] = []             # updates waiting for aggregation
model_version: int = 0
global_weights: OrderedDict | None = None
round_metrics: list[dict] = []               # per-round metrics history

# Minimum nodes required before aggregation
MIN_NODES_FOR_AGGREGATION = 2

# A ResNet18 state_dict is ~45 MB raw; base64 adds ~33% overhead. This
# caps how much a single /training/update request can make the server
# buffer in memory before validation even starts, so a hostile or just
# broken client can't hand it an arbitrarily large body as a cheap DoS.
MAX_TRAINING_UPDATE_BYTES = 200 * 1024 * 1024


# ── Lifespan ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_global_model()
    logger.info("Aggregation server ready on port %d", AGGREGATOR_PORT)
    yield


# ── FastAPI App ──────────────────────────────────────────────────────────
app = FastAPI(
    title="SecureDerm AI — Aggregation Server",
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def _body_size_limit(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if (
        content_length
        and content_length.isdigit()
        and int(content_length) > MAX_TRAINING_UPDATE_BYTES
    ):
        return JSONResponse(status_code=413, content={"detail": "Request body too large."})
    return await call_next(request)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    """Never let a raw traceback reach the client — log it server-side
    and return a generic message instead."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


# ── Request / Response Schemas ───────────────────────────────────────────
class NodeRegistration(BaseModel):
    hospital_id: str
    dataset_size: int


class NodeRegistrationResponse(BaseModel):
    node_token: str
    model_version: int
    message: str


class TrainingUpdate(BaseModel):
    hospital_id: str
    model_weights_b64: str   # base64-encoded state_dict
    num_samples: int
    training_loss: float

    @field_validator("hospital_id")
    @classmethod
    def _hospital_id_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("hospital_id must not be blank")
        return v

    @field_validator("num_samples")
    @classmethod
    def _num_samples_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("num_samples must be positive")
        return v

    @field_validator("training_loss")
    @classmethod
    def _loss_finite(cls, v: float) -> float:
        if not math.isfinite(v) or v < 0:
            raise ValueError("training_loss must be a finite, non-negative number")
        return v


class TrainingUpdateResponse(BaseModel):
    status: str
    pending_updates: int
    aggregated: bool
    model_version: int


class ModelResponse(BaseModel):
    model_version: int
    weights_b64: str


# ── Helpers ──────────────────────────────────────────────────────────────
def _serialize_weights(state_dict: OrderedDict) -> str:
    """Serialize a state_dict to a base64 string."""
    buffer = io.BytesIO()
    torch.save(state_dict, buffer)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _deserialize_weights(b64_string: str) -> OrderedDict:
    """Deserialize a base64 string back to a state_dict."""
    raw = base64.b64decode(b64_string)
    buffer = io.BytesIO(raw)
    return torch.load(buffer, map_location="cpu", weights_only=True)


def _init_global_model() -> None:
    """Create the initial global model if not yet initialized."""
    global global_weights, model_version
    if global_weights is None:
        model = build_model(pretrained=True, device="cpu")
        global_weights = model.state_dict()
        model_version = 1
        logger.info("Global model initialized (version %d)", model_version)


def _validate_token(hospital_id: str, token: str) -> bool:
    """Check that the token matches the registered node."""
    node = registered_nodes.get(hospital_id)
    if node is None:
        return False
    return secrets.compare_digest(node["token"], token or "")


def _validate_any_token(token: str | None) -> bool:
    """Check that the token matches *some* currently registered node."""
    if not token:
        return False
    return any(
        secrets.compare_digest(node["token"], token)
        for node in registered_nodes.values()
    )


# ── Endpoints ────────────────────────────────────────────────────────────
@app.post("/node/register", response_model=NodeRegistrationResponse)
async def register_node(
    payload: NodeRegistration,
    x_node_token: str | None = Header(None, alias="X-Node-Token"),
):
    """Register a hospital node and issue an access token.

    A hospital_id that is already registered can only be re-registered
    (to rotate its token, e.g. after a restart) by presenting its
    existing token — otherwise anyone could reach the aggregator and
    hijack an already-registered node's identity to submit poisoned
    updates or steal its token.
    """
    hospital_id = payload.hospital_id
    if not hospital_id or not hospital_id.strip():
        raise HTTPException(status_code=400, detail="hospital_id must not be blank")

    existing = registered_nodes.get(hospital_id)
    if existing is not None and not secrets.compare_digest(
        existing["token"], x_node_token or ""
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Node '{hospital_id}' is already registered. "
                "Provide its current X-Node-Token to re-register."
            ),
        )

    # Generate a secure token for this node
    token = secrets.token_urlsafe(32)

    registered_nodes[hospital_id] = {
        "dataset_size": payload.dataset_size,
        "token": token,
        "registered_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(
        "Node registered: %s (dataset_size=%d)", hospital_id, payload.dataset_size
    )

    return NodeRegistrationResponse(
        node_token=token,
        model_version=model_version,
        message=f"Node {hospital_id} registered successfully.",
    )


@app.post("/training/update", response_model=TrainingUpdateResponse)
async def submit_update(
    payload: TrainingUpdate,
    x_node_token: str = Header(..., alias="X-Node-Token"),
):
    """
    Receive model weight updates from a hospital node.

    When enough updates are collected, triggers FedAvg aggregation.
    """
    global global_weights, model_version

    # Verify token
    if not _validate_token(payload.hospital_id, x_node_token):
        raise HTTPException(status_code=403, detail="Invalid node token.")

    # Deserialize and store the update
    try:
        weights = _deserialize_weights(payload.model_weights_b64)
    except Exception:
        raise HTTPException(
            status_code=400, detail="Could not deserialize model_weights_b64."
        )

    if global_weights is not None and set(weights.keys()) != set(global_weights.keys()):
        raise HTTPException(
            status_code=400,
            detail="Uploaded weights do not match the global model's architecture.",
        )

    pending_updates.append({
        "hospital_id": payload.hospital_id,
        "weights": weights,
        "num_samples": payload.num_samples,
        "loss": payload.training_loss,
    })

    logger.info(
        "Update received from %s (loss=%.4f, samples=%d). Pending: %d",
        payload.hospital_id,
        payload.training_loss,
        payload.num_samples,
        len(pending_updates),
    )

    # Check if we have enough updates to aggregate
    aggregated = False
    if len(pending_updates) >= MIN_NODES_FOR_AGGREGATION:
        avg_loss = sum(u["loss"] for u in pending_updates) / len(pending_updates)
        node_names = [u["hospital_id"] for u in pending_updates]
        global_weights = federated_average(pending_updates)
        model_version += 1
        round_metrics.append({
            "round": model_version - 1,
            "nodes": node_names,
            "avg_loss": round(avg_loss, 4),
            "num_nodes": len(pending_updates),
        })
        pending_updates.clear()
        aggregated = True
        logger.info(
            "[Aggregator] Round %d | Nodes: %d | Avg Loss: %.4f",
            model_version - 1,
            len(node_names),
            avg_loss,
        )

    return TrainingUpdateResponse(
        status="accepted",
        pending_updates=len(pending_updates),
        aggregated=aggregated,
        model_version=model_version,
    )


@app.get("/model/latest", response_model=ModelResponse)
async def get_latest_model(x_node_token: str | None = Header(None, alias="X-Node-Token")):
    """Serve the latest global model weights to a registered node."""
    if not _validate_any_token(x_node_token):
        raise HTTPException(status_code=403, detail="Invalid node token.")
    if global_weights is None:
        raise HTTPException(status_code=503, detail="Global model not initialized.")

    weights_b64 = _serialize_weights(global_weights)
    return ModelResponse(
        model_version=model_version,
        weights_b64=weights_b64,
    )


@app.get("/status")
async def server_status():
    """Health check / status endpoint."""
    return {
        "status": "running",
        "model_version": model_version,
        "registered_nodes": len(registered_nodes),
        "pending_updates": len(pending_updates),
    }


@app.get("/round/metrics")
async def get_round_metrics():
    """Return per-round aggregation metrics."""
    return {
        "current_round": model_version - 1,
        "total_rounds": FEDERATED_ROUNDS,
        "metrics": round_metrics,
    }


# ── Main ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "aggregator.server:app",
        host="0.0.0.0",
        port=AGGREGATOR_PORT,
        reload=False,
        log_level="info",
    )
