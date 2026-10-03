"""Acceptance: sales-page suggestion / generate / summary / full-list reconciliation.

Seed lane C1: capacity 10, stock 0, in_transit 0 -> suggested fill 10.
"""


def _lane_id(client, slot_no):
    lanes = client.get("/api/lanes").json()
    return next(l["id"] for l in lanes if l["slot_no"] == slot_no)


def _line(summary, slot_no):
    return next(l for l in summary["lines"] if l["slot_no"] == slot_no)


def test_suggest_is_live_and_follows_lane_changes(client):
    s = client.get("/api/refills/suggest").json()
    assert _line(s, "C1")["fill_qty"] == 10
    cid = _lane_id(client, "C1")
    r = client.patch(f"/api/lanes/{cid}", json={"stock": 6})
    assert r.status_code == 200
    assert r.json()["gap"] == 4
    s2 = client.get("/api/refills/suggest").json()
    assert _line(s2, "C1")["fill_qty"] == 4  # 改数后建议列必须跟新


def test_suggest_never_persists_an_order(client):
    client.get("/api/refills/suggest")
    assert client.get("/api/refills/latest").status_code == 404


def test_run_writes_submit_moment_suggestion_not_stale_page_value(client):
    # 记下页上旧建议 C1=10，随后抬高 C1 库存，再生成：单上必须是新建议 4
    cid = _lane_id(client, "C1")
    client.patch(f"/api/lanes/{cid}", json={"stock": 6})
    r = client.post("/api/refills/run")
    assert r.status_code == 200
    assert _line(r.json(), "C1")["fill_qty"] == 4
    latest = client.get("/api/refills/latest").json()
    assert _line(latest, "C1")["fill_qty"] == 4


def test_run_with_stale_lines_fails_409_and_adds_no_order(client):
    cid = _lane_id(client, "C1")
    client.patch(f"/api/lanes/{cid}", json={"stock": 6})
    r = client.post("/api/refills/run", json={"lines": [{"lane_id": cid, "fill_qty": 10}]})
    assert r.status_code == 409
    assert r.json()["detail"] == "建议已过期"  # 不得改写成超缺口或已满仓
    assert client.get("/api/refills/latest").status_code == 404  # 单行数不增


def test_stale_run_after_success_keeps_existing_order_untouched(client):
    first = client.post("/api/refills/run").json()
    cid = _lane_id(client, "C1")
    client.patch(f"/api/lanes/{cid}", json={"stock": 6})
    r = client.post("/api/refills/run", json={"lines": [{"lane_id": cid, "fill_qty": 10}]})
    assert r.status_code == 409
    latest = client.get("/api/refills/latest").json()
    assert latest["id"] == first["id"]  # 没有产生新单


def test_run_with_fresh_lines_succeeds(client):
    s = client.get("/api/refills/suggest").json()
    lines = [{"lane_id": l["lane_id"], "fill_qty": l["fill_qty"]} for l in s["lines"]]
    r = client.post("/api/refills/run", json={"lines": lines})
    assert r.status_code == 200
    assert r.json()["total_fill"] == s["total_fill"]


def test_run_with_unknown_lane_in_lines_is_stale(client):
    r = client.post("/api/refills/run", json={"lines": [{"lane_id": 99999, "fill_qty": 1}]})
    assert r.status_code == 409
    assert r.json()["detail"] == "建议已过期"


def test_summary_and_full_reconcile_with_latest_order(client):
    run = client.post("/api/refills/run").json()
    latest = client.get("/api/refills/latest").json()
    assert latest["lines"] == run["lines"]
    summary = client.get("/api/refills/summary").json()
    assert summary["total_fill"] == sum(l["fill_qty"] for l in latest["lines"])
    assert summary["total_fill"] == latest["total_fill"]
    full = client.get("/api/refills/full").json()["lanes"]
    assert {l["lane_id"] for l in full} == {l["lane_id"] for l in latest["lines"] if l["status"] == "full"}
    assert summary["full_count"] == len(full)


def test_summary_and_full_empty_before_first_order(client):
    assert client.get("/api/refills/latest").status_code == 404
    s = client.get("/api/refills/summary").json()
    assert s["total_fill"] == 0 and s["full_count"] == 0
    assert client.get("/api/refills/full").json()["lanes"] == []


def test_run_accepts_empty_json_post_like_frontend(client):
    # frontend api() always sends Content-Type: application/json, with no body
    r = client.post("/api/refills/run", headers={"Content-Type": "application/json"})
    assert r.status_code == 200


def test_patch_lane_validation(client):
    cid = _lane_id(client, "C1")
    assert client.patch(f"/api/lanes/{cid}", json={"stock": -1}).status_code == 422
    assert client.patch(f"/api/lanes/{cid}", json={"capacity": 0}).status_code == 422
    assert client.patch("/api/lanes/99999", json={"stock": 1}).status_code == 404
