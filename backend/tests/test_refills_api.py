"""补货落单的对账测试：建议列 / 落单 / 汇总 / 满仓四处数字必须一致。

核心规则：点生成时以「提交瞬间」现网缺口重算的建议写入单行；
若客户端仍用打开页面时的旧建议落单，整次失败（409 建议已过期），单行数不增。
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import Lane, Location

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# (slot_no, sku, capacity, stock, in_transit)
SEED_LANES = [
    ("A1", "矿泉水", 20, 5, 0),    # 缺口 15
    ("B1", "薯片", 12, 3, 2),      # 缺口 7
    ("C1", "能量棒", 10, 0, 0),    # 缺口 10
    ("C2", "口香糖", 24, 24, 0),   # 缺口 0 → 满仓
]


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    loc = Location(code="VM-T", name="测试点位", address="")
    db.add(loc)
    db.flush()
    for slot, sku, cap, stock, transit in SEED_LANES:
        db.add(Lane(location_id=loc.id, slot_no=slot, sku_name=sku,
                    capacity=cap, stock=stock, in_transit=transit))
    db.commit()
    db.close()
    app.dependency_overrides[get_db] = override_get_db
    # 不用 with 包裹：避免触发 lifespan 连接真实 Postgres，测试全程走内存 SQLite
    yield TestClient(app)
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def preview(client):
    r = client.get("/api/refills/preview", params={"location_id": 1})
    assert r.status_code == 200
    return r.json()


def expected_of(data):
    return [{"lane_id": l["lane_id"], "fill_qty": l["fill_qty"]} for l in data["lines"]]


def line_of(data, slot):
    return next(l for l in data["lines"] if l["slot_no"] == slot)


def order_count(client):
    r = client.get("/api/refills", params={"location_id": 1})
    assert r.status_code == 200
    return len(r.json())


def test_preview_computed_live(client):
    data = preview(client)
    assert line_of(data, "A1")["fill_qty"] == 15
    assert line_of(data, "B1")["fill_qty"] == 7
    assert line_of(data, "C1")["fill_qty"] == 10
    assert line_of(data, "C2")["fill_qty"] == 0
    assert line_of(data, "C2")["status"] == "full"
    assert data["total_fill"] == 32
    assert data["full_count"] == 1


def test_run_with_matching_expected_creates_order(client):
    data = preview(client)
    r = client.post("/api/refills/run", params={"location_id": 1},
                    json={"expected": expected_of(data)})
    assert r.status_code == 200
    body = r.json()
    assert body["total_fill"] == 32
    assert {l["lane_id"]: l["fill_qty"] for l in body["lines"]} == \
           {l["lane_id"]: l["fill_qty"] for l in data["lines"]}
    assert order_count(client) == 1


def test_run_without_expected_uses_submission_moment_values(client):
    r = client.post("/api/refills/run", params={"location_id": 1})
    assert r.status_code == 200
    assert r.json()["total_fill"] == 32
    assert order_count(client) == 1


def test_stale_expected_rejected_and_no_order_created(client):
    stale = expected_of(preview(client))  # 打开页面时的旧建议
    c1 = next(l for l in client.get("/api/lanes").json() if l["slot_no"] == "C1")
    r = client.patch(f"/api/lanes/{c1['id']}", json={"stock": 7})  # 提交前抬高 C1 库存
    assert r.status_code == 200

    r = client.post("/api/refills/run", params={"location_id": 1}, json={"expected": stale})
    assert r.status_code == 409
    # 失败原因固定为「建议已过期」，不得改写成超缺口或已满仓
    assert r.json()["detail"] == "建议已过期"
    assert order_count(client) == 0  # 单行数不增


def test_seed_scenario_c1_order_uses_new_suggestion(client):
    """种子场景：销量页记下 C1=10，抬高 C1 库存后再生成，单上 C1 必须等于新建议 3。"""
    assert line_of(preview(client), "C1")["fill_qty"] == 10
    c1 = next(l for l in client.get("/api/lanes").json() if l["slot_no"] == "C1")
    client.patch(f"/api/lanes/{c1['id']}", json={"stock": 7})

    fresh = preview(client)  # 提交瞬间重算
    assert line_of(fresh, "C1")["fill_qty"] == 3
    r = client.post("/api/refills/run", params={"location_id": 1},
                    json={"expected": expected_of(fresh)})
    assert r.status_code == 200
    assert line_of(r.json(), "C1")["fill_qty"] == 3

    latest = client.get("/api/refills/latest", params={"location_id": 1}).json()
    assert line_of(latest, "C1")["fill_qty"] == 3


def test_four_views_reconcile(client):
    """建议列、落单、汇总、满仓四处数字必须对账一致。"""
    data = preview(client)
    r = client.post("/api/refills/run", params={"location_id": 1},
                    json={"expected": expected_of(data)})
    assert r.status_code == 200
    order = r.json()

    summary = client.get("/api/refills/summary", params={"location_id": 1}).json()
    assert summary["total_fill"] == order["total_fill"] == data["total_fill"]

    full = client.get("/api/refills/full", params={"location_id": 1}).json()
    full_from_order = [l for l in order["lines"] if l["status"] == "full"]
    assert {l["lane_id"] for l in full["lanes"]} == {l["lane_id"] for l in full_from_order}
    assert summary["full_count"] == len(full["lanes"])

    # 货道改数后，建议列 / 汇总 / 满仓一起跟新
    c1 = next(l for l in client.get("/api/lanes").json() if l["slot_no"] == "C1")
    client.patch(f"/api/lanes/{c1['id']}", json={"stock": 10})  # C1 变满仓
    data2 = preview(client)
    assert line_of(data2, "C1")["fill_qty"] == 0
    assert line_of(data2, "C1")["status"] == "full"
    summary2 = client.get("/api/refills/summary", params={"location_id": 1}).json()
    assert summary2["total_fill"] == data2["total_fill"] == 22
    full2 = client.get("/api/refills/full", params={"location_id": 1}).json()
    assert {l["slot_no"] for l in full2["lanes"]} == {"C1", "C2"}


def test_latest_has_no_side_effect(client):
    r = client.get("/api/refills/latest", params={"location_id": 1})
    assert r.status_code == 404
    assert order_count(client) == 0  # GET 不得自动落单


def test_patch_lane_validation(client):
    c1 = next(l for l in client.get("/api/lanes").json() if l["slot_no"] == "C1")
    assert client.patch(f"/api/lanes/{c1['id']}", json={"stock": -1}).status_code == 422
    assert client.patch("/api/lanes/9999", json={"stock": 1}).status_code == 404
