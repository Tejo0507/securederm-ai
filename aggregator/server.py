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

import asyncio
import base64
import io
import json
import math
import os
import re
import secrets
import logging
from collections import OrderedDict
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import torch
import uvicorn
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from aggregator.fedavg import federated_average
from aggregator.robust import clip_update, file_sha256, sha256_hex
from config.settings import (
    AGGREGATOR_ADMIN_TOKEN,
    AGGREGATOR_MAX_UPDATE_NORM,
    CLASS_LABELS,
    NUM_CLASSES,
    AGGREGATOR_HOST,
    AGGREGATOR_MAX_NODES,
    AGGREGATOR_PERSIST,
    AGGREGATOR_PORT,
    AGGREGATOR_REGISTRATION_KEY,
    CHECKPOINTS_DIR,
    FEDERATED_ROUNDS,
    USE_DIFFERENTIAL_PRIVACY,
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
_serialized_cache: tuple[int, str] | None = None   # (version, base64 payload)
_aggregation_lock = asyncio.Lock()   # serializes pending_updates / global model changes

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
# hospital_id ends up in log lines and the metrics response; restricting it
# to a conservative charset stops log injection (newlines, control chars)
# and unbounded-length identifiers.
_HOSPITAL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}$")


def _check_hospital_id(v: str) -> str:
    if not _HOSPITAL_ID_RE.fullmatch(v or ""):
        raise ValueError(
            "hospital_id must be 1-64 characters: letters, digits, '_', '-' or '.'"
        )
    return v


class NodeRegistration(BaseModel):
    hospital_id: str
    dataset_size: int

    @field_validator("hospital_id")
    @classmethod
    def _hospital_id_valid(cls, v: str) -> str:
        return _check_hospital_id(v)

    @field_validator("dataset_size")
    @classmethod
    def _dataset_size_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("dataset_size must be positive")
        return v


class NodeRegistrationResponse(BaseModel):
    node_token: str
    model_version: int
    message: str


class TrainingUpdate(BaseModel):
    hospital_id: str
    model_weights_b64: str   # base64-encoded state_dict
    num_samples: int
    training_loss: float
    # Version of the global model this update was trained from; an update
    # built on an older model is stale and would drag the new one backwards.
    base_version: int | None = None
    # SHA-256 of the raw serialized weights, to catch corruption in transit.
    weights_sha256: str | None = None

    @field_validator("hospital_id")
    @classmethod
    def _hospital_id_valid(cls, v: str) -> str:
        return _check_hospital_id(v)

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


def _check_weights_compatible(
    weights: OrderedDict, reference: OrderedDict | None = None
) -> str | None:
    """Return an error message if `weights` can't be averaged into the global model."""
    reference = global_weights if reference is None else reference
    if reference is None:
        return None
    for key, ref in reference.items():
        if key not in weights:
            return f"Uploaded weights are missing '{key}'."
        tensor = weights[key]
        if not isinstance(tensor, torch.Tensor) or tensor.shape != ref.shape:
            return f"Uploaded weight '{key}' has the wrong shape."
        if tensor.is_floating_point() != ref.is_floating_point():
            return f"Uploaded weight '{key}' has the wrong dtype."
        if tensor.is_floating_point() and not torch.isfinite(tensor).all():
            return f"Uploaded weight '{key}' contains NaN or Inf values."
    return None


def _init_global_model() -> None:
    """Create the initial global model if not yet initialized."""
    global global_weights, model_version
    if global_weights is not None:
        return

    def _build(pretrained: bool):
        model = build_model(pretrained=pretrained, device="cpu")
        if USE_DIFFERENTIAL_PRIVACY:
            # DP clients train an Opacus-fixed model (BatchNorm -> GroupNorm),
            # whose state_dict keys differ from the stock ResNet's. The global
            # model must share that architecture or every client update is
            # rejected as an architecture mismatch.
            from hospital_node.privacy_layer import make_model_private
            model = make_model_private(model)
        return model.state_dict()

    restored = _load_persisted_state(_build)
    if restored is not None:
        global_weights, model_version = restored
        logger.info("Global model restored from checkpoint (version %d)", model_version)
        return

    global_weights = _build(pretrained=True)
    model_version = 1
    logger.info("Global model initialized (version %d)", model_version)


_CHECKPOINT_PATH = CHECKPOINTS_DIR / "global_model.pt"
_META_PATH = CHECKPOINTS_DIR / "global_model.meta.json"


def _load_persisted_state(build) -> tuple[OrderedDict, int] | None:
    """Restore (weights, version) saved by _persist_state, or None.

    A checkpoint whose architecture doesn't match the current configuration
    (e.g. saved before differential privacy was switched on) is ignored
    rather than served to nodes that would then fail to train from it.
    """
    if not AGGREGATOR_PERSIST or not _CHECKPOINT_PATH.exists():
        return None
    try:
        meta = json.loads(_META_PATH.read_text()) if _META_PATH.exists() else {}
        expected_digest = meta.get("sha256")
        if expected_digest and file_sha256(_CHECKPOINT_PATH) != expected_digest:
            # Truncated write, disk corruption or tampering: don't serve it.
            logger.error("Saved global model fails its integrity check; ignoring it.")
            return None
        weights = torch.load(_CHECKPOINT_PATH, map_location="cpu", weights_only=True)
        problem = _check_weights_compatible(weights, build(pretrained=False))
        if problem:
            logger.warning("Ignoring saved global model: %s", problem)
            return None
        return weights, max(int(meta.get("model_version", 1)), 1)
    except Exception:
        logger.exception("Could not restore saved global model; starting fresh.")
        return None


def _persist_state() -> None:
    """Atomically save the global model (and its version) so a restart
    doesn't discard every completed round. Also gives the web backend's
    predictor (which loads checkpoints/global_model.pt) a model to serve."""
    if not AGGREGATOR_PERSIST or global_weights is None:
        return
    try:
        CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _CHECKPOINT_PATH.with_suffix(".pt.tmp")
        torch.save(global_weights, tmp)
        digest = file_sha256(tmp)
        os.replace(tmp, _CHECKPOINT_PATH)
        meta_tmp = _META_PATH.with_suffix(".json.tmp")
        # The meta file doubles as a small model card.
        meta_tmp.write_text(json.dumps({
            "model_version": model_version,
            "sha256": digest,
            "num_classes": NUM_CLASSES,
            "class_labels": {str(k): v for k, v in CLASS_LABELS.items()},
            "differential_privacy": USE_DIFFERENTIAL_PRIVACY,
            "rounds_completed": len(round_metrics),
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }))
        os.replace(meta_tmp, _META_PATH)
    except Exception:
        logger.exception("Could not persist global model checkpoint.")


def _validate_token(hospital_id: str, token: str) -> bool:
    """Check that the token matches the registered node."""
    node = registered_nodes.get(hospital_id)
    if node is None:
        return False
    return secrets.compare_digest(node["token"], token or "")


def _is_admin_token(token: str | None) -> bool:
    return bool(AGGREGATOR_ADMIN_TOKEN) and bool(token) and secrets.compare_digest(
        AGGREGATOR_ADMIN_TOKEN, token
    )


def _is_authorized(token: str | None) -> bool:
    """A registered node's token, or the operator's admin token."""
    return _validate_any_token(token) or _is_admin_token(token)


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
    x_registration_key: str | None = Header(None, alias="X-Registration-Key"),
):
    """Register a hospital node and issue an access token.

    When AGGREGATOR_REGISTRATION_KEY is set, enrolling a *new* node also
    requires that key (X-Registration-Key); re-registering an existing node
    is authenticated by its current token instead.

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

    if existing is None:
        if AGGREGATOR_REGISTRATION_KEY and not secrets.compare_digest(
            AGGREGATOR_REGISTRATION_KEY, x_registration_key or ""
        ):
            raise HTTPException(status_code=403, detail="Invalid registration key.")
        if len(registered_nodes) >= AGGREGATOR_MAX_NODES:
            raise HTTPException(status_code=503, detail="Node limit reached.")

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

    if payload.weights_sha256 is not None:
        try:
            actual = await run_in_threadpool(
                lambda: sha256_hex(base64.b64decode(payload.model_weights_b64))
            )
        except Exception:
            raise HTTPException(status_code=400, detail="model_weights_b64 is not valid base64.")
        if not secrets.compare_digest(actual, payload.weights_sha256.lower()):
            raise HTTPException(
                status_code=400, detail="Weights failed their integrity check (corrupt upload)."
            )

    # Deserialize and store the update
    # Decoding ~45 MB and scanning every tensor is seconds of CPU; do it in a
    # worker thread so status checks and other nodes' requests keep flowing.
    try:
        weights = await run_in_threadpool(_deserialize_weights, payload.model_weights_b64)
    except Exception:
        raise HTTPException(
            status_code=400, detail="Could not deserialize model_weights_b64."
        )

    if not isinstance(weights, dict):
        raise HTTPException(status_code=400, detail="model_weights_b64 is not a state_dict.")

    if global_weights is not None and set(weights.keys()) != set(global_weights.keys()):
        raise HTTPException(
            status_code=400,
            detail="Uploaded weights do not match the global model's architecture.",
        )

    problem = await run_in_threadpool(_check_weights_compatible, weights)
    if problem:
        raise HTTPException(status_code=400, detail=problem)

    # Everything that touches pending_updates / the global model happens under
    # one lock: aggregation now awaits a worker thread, so without it two
    # concurrent uploads could both see "enough updates" and aggregate the
    # same batch twice (or append into a list that is being cleared).
    async with _aggregation_lock:
        if payload.base_version is not None and payload.base_version != model_version:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Stale update: trained from model v{payload.base_version}, "
                    f"current is v{model_version}. Download the latest model and retrain."
                ),
            )

        if AGGREGATOR_MAX_UPDATE_NORM > 0:
            weights, norm, was_clipped = await run_in_threadpool(
                clip_update, weights, global_weights, AGGREGATOR_MAX_UPDATE_NORM
            )
            if was_clipped:
                logger.warning(
                    "Update from %s clipped (distance %.2f > limit %.2f)",
                    payload.hospital_id, norm, AGGREGATOR_MAX_UPDATE_NORM,
                )

        # A node may not claim more samples than it declared at registration:
        # num_samples is its FedAvg weight, so an inflated value would let it
        # dominate the average.
        declared = registered_nodes[payload.hospital_id]["dataset_size"]
        effective_samples = min(payload.num_samples, declared)
        if effective_samples != payload.num_samples:
            logger.warning(
                "%s claimed %d samples but registered %d; using %d",
                payload.hospital_id, payload.num_samples, declared, effective_samples,
            )

        # One pending update per node: a node resubmitting before the round
        # closes replaces its earlier update instead of counting twice (which
        # would let a single node satisfy MIN_NODES_FOR_AGGREGATION alone).
        pending_updates[:] = [
            u for u in pending_updates if u["hospital_id"] != payload.hospital_id
        ]
        pending_updates.append({
            "hospital_id": payload.hospital_id,
            "weights": weights,
            "num_samples": effective_samples,
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
            batch = list(pending_updates)
            avg_loss = sum(u["loss"] for u in batch) / len(batch)
            node_names = [u["hospital_id"] for u in batch]
            try:
                global_weights = await run_in_threadpool(federated_average, batch)
            except ValueError as exc:
                logger.error("Aggregation failed, discarding pending updates: %s", exc)
                pending_updates.clear()
                raise HTTPException(status_code=400, detail="Aggregation failed.")
            model_version += 1
            round_metrics.append({
                "round": model_version - 1,
                "nodes": node_names,
                "avg_loss": round(avg_loss, 4),
                "num_nodes": len(batch),
            })
            pending_updates.clear()
            await run_in_threadpool(_persist_state)
            aggregated = True
            logger.info(
                "[Aggregator] Round %d | Nodes: %d | Avg Loss: %.4f",
                model_version - 1,
                len(node_names),
                avg_loss,
            )

        response_pending = len(pending_updates)
        response_version = model_version

    return TrainingUpdateResponse(
        status="accepted",
        pending_updates=response_pending,
        aggregated=aggregated,
        model_version=response_version,
    )


@app.get("/model/latest", response_model=ModelResponse)
async def get_latest_model(x_node_token: str | None = Header(None, alias="X-Node-Token")):
    """Serve the latest global model weights to a registered node (or the operator)."""
    if not _is_authorized(x_node_token):
        raise HTTPException(status_code=403, detail="Invalid node token.")
    if global_weights is None:
        raise HTTPException(status_code=503, detail="Global model not initialized.")

    # Serializing ~45 MB of tensors per request is wasteful when every node
    # downloads the same version; cache the encoded payload per version.
    global _serialized_cache
    if _serialized_cache is None or _serialized_cache[0] != model_version:
        _serialized_cache = (model_version, _serialize_weights(global_weights))
    return ModelResponse(
        model_version=model_version,
        weights_b64=_serialized_cache[1],
    )


@app.get("/model/info")
async def get_model_info(x_node_token: str | None = Header(None, alias="X-Node-Token")):
    """Describe the global model (version, classes, privacy mode) without its weights."""
    if not _is_authorized(x_node_token):
        raise HTTPException(status_code=403, detail="Invalid node token.")
    return {
        "model_version": model_version,
        "num_classes": NUM_CLASSES,
        "class_labels": {str(k): v for k, v in CLASS_LABELS.items()},
        "differential_privacy": USE_DIFFERENTIAL_PRIVACY,
        "rounds_completed": len(round_metrics),
        "min_nodes_for_aggregation": MIN_NODES_FOR_AGGREGATION,
        "max_update_norm": AGGREGATOR_MAX_UPDATE_NORM or None,
    }


@app.get("/status")
async def server_status(x_node_token: str | None = Header(None, alias="X-Node-Token")):
    """Health check. Anonymous callers (load balancers, healthchecks) get only
    liveness; how many hospitals are enrolled or mid-round is network
    information that needs a node or admin token."""
    if not _is_authorized(x_node_token):
        return {"status": "running"}
    return {
        "status": "running",
        "model_version": model_version,
        "registered_nodes": len(registered_nodes),
        "pending_updates": len(pending_updates),
    }


@app.get("/round/metrics")
async def get_round_metrics(x_node_token: str | None = Header(None, alias="X-Node-Token")):
    """Return per-round aggregation metrics.

    Requires a node (or admin) token: the metrics list which hospitals
    took part in each round, which shouldn't be public.
    """
    if not _is_authorized(x_node_token):
        raise HTTPException(status_code=403, detail="Invalid node token.")
    return {
        "current_round": model_version - 1,
        "total_rounds": FEDERATED_ROUNDS,
        "metrics": round_metrics,
    }


# ── Main ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "aggregator.server:app",
        # Loopback unless AGGREGATOR_HOST says otherwise (docker-compose sets
        # 0.0.0.0): binding every interface by default exposed the server to
        # the whole network.
        host=AGGREGATOR_HOST,
        port=AGGREGATOR_PORT,
        reload=False,
        log_level="info",
    )
