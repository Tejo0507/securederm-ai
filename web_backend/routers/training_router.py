import asyncio
import random

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from web_backend.database import get_db, SessionLocal
from web_backend.db_models import Hospital, FederatedRound
from web_backend.auth import get_current_hospital

router = APIRouter()

# In-memory simulation state
_training_state: dict = {
    "active": False,
    "round": 0,
    "total_rounds": 5,
    "loss": 0.0,
    "epoch": 0,
    "samples": 0,
    "logs": [],
    "metrics": [],
}


def _reset_training() -> None:
    _training_state.update(
        {
            "active": False,
            "round": 0,
            "total_rounds": 5,
            "loss": 0.0,
            "epoch": 0,
            "samples": 0,
            "logs": [],
            "metrics": [],
        }
    )


@router.post("/training/start")
async def start_training(
    hospital: Hospital = Depends(get_current_hospital),
    db: Session = Depends(get_db),
):
    if _training_state["active"]:
        return {"status": "already_running", "round": _training_state["round"]}

    _reset_training()
    _training_state["active"] = True

    asyncio.create_task(_simulate_training(hospital.name))

    return {"status": "started", "total_rounds": 5}


async def _simulate_training(hospital_name: str) -> None:
    """Simulate federated training rounds with realistic loss decay."""
    base_loss = 2.5 + random.uniform(-0.2, 0.2)
    partner = "City General Hospital" if "General" not in hospital_name else "Metro Medical Center"

    for round_num in range(1, 6):
        _training_state["round"] = round_num
        _training_state["epoch"] = 1
        _training_state["samples"] = random.randint(800, 1200)

        _training_state["logs"].append(
            f"[Round {round_num}] {hospital_name} training locally..."
        )
        await asyncio.sleep(2)

        loss_a = base_loss * (0.82 ** round_num) + random.uniform(-0.03, 0.03)
        _training_state["loss"] = round(loss_a, 4)
        _training_state["logs"].append(
            f"[Round {round_num}] {hospital_name} — local loss: {loss_a:.4f}"
        )
        await asyncio.sleep(1)

        _training_state["logs"].append(
            f"[Round {round_num}] {hospital_name} uploading encrypted gradients"
        )
        await asyncio.sleep(1)

        loss_b = base_loss * (0.82 ** round_num) + random.uniform(-0.03, 0.03)
        _training_state["logs"].append(
            f"[Round {round_num}] {partner} uploading encrypted gradients"
        )
        await asyncio.sleep(1)

        avg_loss = round((loss_a + loss_b) / 2, 4)
        _training_state["logs"].append(
            f"[Round {round_num}] Aggregator merging updates — Avg Loss: {avg_loss}"
        )

        _training_state["metrics"].append(
            {"round": round_num, "avg_loss": avg_loss, "nodes": 2}
        )

        # Persist to DB
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

    _training_state["active"] = False
    _training_state["logs"].append("✓ Federated training complete!")


@router.get("/training/status")
async def training_status():
    return {
        "active": _training_state["active"],
        "round": _training_state["round"],
        "total_rounds": _training_state["total_rounds"],
        "loss": _training_state["loss"],
        "epoch": _training_state["epoch"],
        "samples": _training_state["samples"],
        "logs": _training_state["logs"][-30:],
        "metrics": _training_state["metrics"],
    }


@router.get("/training/metrics")
async def training_metrics(db: Session = Depends(get_db)):
    if _training_state["metrics"]:
        return {"metrics": _training_state["metrics"]}

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
