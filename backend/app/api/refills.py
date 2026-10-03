import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Lane, Location, RefillOrder
from app.services.fill_engine import build_fill_lines, summarize

router = APIRouter(prefix="/refills", tags=["refills"])


class ClientLine(BaseModel):
    """A suggestion line the client believes to be current (optimistic check)."""
    lane_id: int
    fill_qty: int


class RunRequest(BaseModel):
    lines: list[ClientLine] | None = None


def _live_summary(db: Session, location_id: int) -> dict:
    """Suggestion computed right now from current lane stock/in_transit."""
    lanes = db.scalars(select(Lane).where(Lane.location_id == location_id).order_by(Lane.slot_no)).all()
    payload = [{"id": l.id, "slot_no": l.slot_no, "sku_name": l.sku_name,
                "capacity": l.capacity, "stock": l.stock, "in_transit": l.in_transit} for l in lanes]
    return summarize(build_fill_lines(payload))


def _latest_order(db: Session, location_id: int) -> RefillOrder | None:
    return db.scalars(select(RefillOrder).where(RefillOrder.location_id == location_id)
                      .order_by(RefillOrder.id.desc())).first()


@router.get("/suggest")
def suggest(location_id: int = 1, db: Session = Depends(get_db)):
    """Live read-only suggestion, recomputed per request; never persisted."""
    if not db.get(Location, location_id):
        raise HTTPException(404, "点位不存在")
    return {"location_id": location_id, **_live_summary(db, location_id)}


@router.post("/run")
def run_refill(body: RunRequest | None = None, location_id: int = 1, db: Session = Depends(get_db)):
    """Generate an order from the gaps at the exact submit moment.

    The order lines always come from a fresh submit-moment recompute, never
    from client-supplied values. If the client submits its displayed lines and
    any of them no longer matches the submit-moment suggestion, the whole run
    fails with 409 建议已过期 and nothing is persisted (no capping, no zeroing).
    """
    if not db.get(Location, location_id):
        raise HTTPException(404, "点位不存在")
    summary = _live_summary(db, location_id)
    if body and body.lines:
        fresh = {l["lane_id"]: l["fill_qty"] for l in summary["lines"]}
        for line in body.lines:
            if fresh.get(line.lane_id) != line.fill_qty:
                raise HTTPException(409, "建议已过期")
    order = RefillOrder(location_id=location_id, created_at=datetime.utcnow(),
                        lines_json=json.dumps(summary, ensure_ascii=False))
    db.add(order)
    db.commit()
    db.refresh(order)
    return {"id": order.id, "location_id": location_id, **summary}


@router.get("/latest")
def latest(location_id: int = 1, db: Session = Depends(get_db)):
    order = _latest_order(db, location_id)
    if not order:
        raise HTTPException(404, "尚未生成补货单")
    return {"id": order.id, "location_id": location_id, **json.loads(order.lines_json)}


@router.get("/full")
def full_lanes(location_id: int = 1, db: Session = Depends(get_db)):
    order = _latest_order(db, location_id)
    lanes = [] if not order else [l for l in json.loads(order.lines_json)["lines"] if l["status"] == "full"]
    return {"location_id": location_id, "lanes": lanes}


@router.get("/summary")
def refill_summary(location_id: int = 1, db: Session = Depends(get_db)):
    order = _latest_order(db, location_id)
    data = json.loads(order.lines_json) if order else {}
    return {
        "location_id": location_id,
        "total_fill": data.get("total_fill", 0),
        "need_fill_count": data.get("need_fill_count", 0),
        "full_count": data.get("full_count", 0),
        "overbooked_count": data.get("overbooked_count", 0),
    }
