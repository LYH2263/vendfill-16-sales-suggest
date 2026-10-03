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

# 落单时客户端快照与提交瞬间现算不一致的失败原因，固定文案，不得改写
STALE_DETAIL = "建议已过期"


class ExpectedLine(BaseModel):
    lane_id: int
    fill_qty: int


class RunPayload(BaseModel):
    """客户端页面展示的建议快照；提交瞬间服务端现算结果必须与其一致才允许落单。"""
    expected: list[ExpectedLine] | None = None


def live_summary(db: Session, location_id: int) -> dict:
    """按现网缺口现算的建议：建议列、落单、汇总、满仓共用同一份结果。"""
    lanes = db.scalars(select(Lane).where(Lane.location_id == location_id).order_by(Lane.slot_no)).all()
    payload = [{"id": l.id, "slot_no": l.slot_no, "sku_name": l.sku_name,
                "capacity": l.capacity, "stock": l.stock, "in_transit": l.in_transit} for l in lanes]
    return summarize(build_fill_lines(payload))


@router.get("/preview")
def preview(location_id: int = 1, db: Session = Depends(get_db)):
    """销量页建议补量列：只读现算，不落单。"""
    if not db.get(Location, location_id):
        raise HTTPException(404, "点位不存在")
    return {"location_id": location_id, **live_summary(db, location_id)}


@router.post("/run")
def run_refill(payload: RunPayload | None = None, location_id: int = 1, db: Session = Depends(get_db)):
    """生成补货单：以提交瞬间现网缺口重算的建议写入单行。

    客户端携带 expected（页面建议快照）时，若与提交瞬间现算结果不一致，
    说明打开页面之后库存/在途被改过：整次生成失败（409 建议已过期），
    不产生任何补货单，单行数不增。
    """
    if not db.get(Location, location_id):
        raise HTTPException(404, "点位不存在")
    summary = live_summary(db, location_id)
    if payload is not None and payload.expected is not None:
        current = {line["lane_id"]: line["fill_qty"] for line in summary["lines"]}
        expected = {line.lane_id: line.fill_qty for line in payload.expected}
        if expected != current:
            raise HTTPException(status_code=409, detail=STALE_DETAIL)
    order = RefillOrder(location_id=location_id, created_at=datetime.utcnow(),
                        lines_json=json.dumps(summary, ensure_ascii=False))
    db.add(order)
    db.commit()
    db.refresh(order)
    return {"id": order.id, "location_id": location_id, **summary}


@router.get("")
def list_orders(location_id: int = 1, db: Session = Depends(get_db)):
    orders = db.scalars(select(RefillOrder).where(RefillOrder.location_id == location_id)
                        .order_by(RefillOrder.id.desc())).all()
    out = []
    for o in orders:
        data = json.loads(o.lines_json)
        out.append({"id": o.id, "location_id": o.location_id, "created_at": o.created_at.isoformat(),
                    "total_fill": data.get("total_fill", 0), "line_count": len(data.get("lines", []))})
    return out


@router.get("/latest")
def latest(location_id: int = 1, db: Session = Depends(get_db)):
    """最近一次补货单；只读，不存在时 404，绝不自动落单。"""
    order = db.scalars(select(RefillOrder).where(RefillOrder.location_id == location_id)
                       .order_by(RefillOrder.id.desc())).first()
    if not order:
        raise HTTPException(404, "暂无补货单")
    data = json.loads(order.lines_json)
    return {"id": order.id, "location_id": location_id, **data}


@router.get("/full")
def full_lanes(location_id: int = 1, db: Session = Depends(get_db)):
    """满仓名单：与建议列同一份现算结果（缺口为 0 的货道）。"""
    data = preview(location_id=location_id, db=db)
    return {"location_id": location_id, "lanes": [l for l in data["lines"] if l["status"] == "full"]}


@router.get("/summary")
def refill_summary(location_id: int = 1, db: Session = Depends(get_db)):
    """汇总总件数：与建议列同一份现算结果。"""
    data = preview(location_id=location_id, db=db)
    return {
        "location_id": location_id,
        "total_fill": data["total_fill"],
        "need_fill_count": data["need_fill_count"],
        "full_count": data["full_count"],
        "overbooked_count": data["overbooked_count"],
    }
