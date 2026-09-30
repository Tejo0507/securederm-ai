import asyncio
import random

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from web_backend.database import get_db, SessionLocal
from web_backend.db_models import Hospital, FederatedRound
from web_backend.auth import get_current_hospital, verify_csrf

router = APIRouter()


def _fresh_state() -> dict:
    return {
        "active": False,
        "round": 0,
        "total_rounds": 5,
        "loss": 0.0,
        "epoch": 0,
        "samples": 0,
        "logs": [],
        "metrics": [],
    }


# In-memory simulation state, keyed by hospital_id. This used to be a
# single shared dict, which meant every hospital's "training status" was
# actually whichever hospital most recently clicked Start — including
# that hospital's name, showing up unauthenticated in another tenant's
# dashboard (or to a client with no session at all: /training/status had
# no auth dependency).
_training_state: dict[int, dict] = {}


def _state_for(hospital_id: int) -> dict:
    return _training_state.setdefault(hospital_id, _fresh_state())


@router.post("/training/start")
async def start_training(
    request: Request,
    hospital: Hospital = Depends(get_current_hospital),
    db: Session = Depends(get_db),
):
    verify_csrf(request)
    state = _state_for(hospital.id)
    if state["active"]:
        return {"status": "already_running", "round": state["round"]}

    _training_state[hospital.id] = _fresh_state()
    _training_state[hospital.id]["active"] = True

    asyncio.create_task(_simulate_training(hospital.id, hospital.name))

    return {"status": "started", "total_rounds": 5}


async def _simulate_training(hospital_id: int, hospital_name: str) -> None:
    """Simulate federated training rounds with realistic loss decay."""
    state = _training_state[hospital_id]
    base_loss = 2.5 + random.uniform(-0.2, 0.2)
    partner = "City General Hospital" if "General" not in hospital_name else "Metro Medical Center"

    for round_num in range(1, 6):
        state["round"] = round_num
        state["epoch"] = 1
        state["samples"] = random.randint(800, 1200)

        state["logs"].append(
            f"[Round {round_num}] {hospital_name} training locally..."
        )
        await asyncio.sleep(2)

        loss_a = base_loss * (0.82 ** round_num) + random.uniform(-0.03, 0.03)
        state["loss"] = round(loss_a, 4)
        state["logs"].append(
            f"[Round {round_num}] {hospital_name} — local loss: {loss_a:.4f}"
        )
        await asyncio.sleep(1)

        state["logs"].append(
            f"[Round {round_num}] {hospital_name} uploading encrypted gradients"
        )
        await asyncio.sleep(1)

        loss_b = base_loss * (0.82 ** round_num) + random.uniform(-0.03, 0.03)
        state["logs"].append(
            f"[Round {round_num}] {partner} uploading encrypted gradients"
        )
        await asyncio.sleep(1)

        avg_loss = round((loss_a + loss_b) / 2, 4)
        state["logs"].append(
            f"[Round {round_num}] Aggregator merging updates — Avg Loss: {avg_loss}"
        )

        state["metrics"].append(
            {"round": round_num, "avg_loss": avg_loss, "nodes": 2}
        )

        # Persist to DB — this table represents the shared federated
        # network history, unlike `state`, which is this hospital's own
        # live simulation and must not leak to anyone else.
        try:
            db = SessionLocal()
            fr = FederatedRound(
                round_number=round_num,
                participating_hospitals=f"{hospital_name}, {partner}",
                avg_loss=avg_loss,
            )
            db.add(fr)
            db.commit()
            db.close()
        except Exception:
            pass

        await asyncio.sleep(1)

    state["active"] = False
    state["logs"].append("✓ Federated training complete!")


@router.get("/training/status")
async def training_status(hospital: Hospital = Depends(get_current_hospital)):
    state = _state_for(hospital.id)
    return {
        "active": state["active"],
        "round": state["round"],
        "total_rounds": state["total_rounds"],
        "loss": state["loss"],
        "epoch": state["epoch"],
        "samples": state["samples"],
        "logs": state["logs"][-30:],
        "metrics": state["metrics"],
    }


@router.get("/training/metrics")
async def training_metrics(db: Session = Depends(get_db)):
    # Always the persisted network-wide history (FederatedRound), not the
    # in-memory `_training_state` — that's per-hospital now, and "recent
    # rounds across the network" is supposed to be shared, unlike a live
    # per-hospital training status.
    rounds = db.query(FederatedRound).order_by(FederatedRound.round_number).all()
    return {
        "metrics": [
            {
                "round": r.round_number,
                "avg_loss": r.avg_loss,
                "nodes": len(r.participating_hospitals.split(","))
                if r.participating_hospitals
                else 0,
            }
            for r in rounds
        ]
    }


@router.get("/federated/rounds")
async def federated_rounds(db: Session = Depends(get_db)):
    rounds = (
        db.query(FederatedRound)
        .order_by(FederatedRound.round_number.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "round_number": r.round_number,
            "participating_hospitals": r.participating_hospitals,
            "avg_loss": r.avg_loss,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rounds
    ]
