# VendFill 售货机补货

按货道容量、库存与在途量计算缺口，生成不超缺口、非负的补货单。

技术栈：Python 3.12 / FastAPI / SQLAlchemy / PostgreSQL / Vue 3 / TypeScript / Vite

## 启动

```bash
docker compose up --build
```

| 服务 | 地址 |
| --- | --- |
| 前端 | http://localhost:4800 |
| API | http://localhost:9800 |
| API 文档 | http://localhost:9800/docs |
| Postgres | localhost:5449 |

健康检查：`GET http://localhost:9800/api/health`

## 使用说明

1. 在「点位」「货道」查看售货机布局与库存；货道页可直接修改库存/在途（保存后建议即按新缺口重算）。
2. 在「销量」查看按现网缺口现算的建议补量（只读）、汇总总件数与满仓名单，三处与建议列同源自洽。
3. 点「生成补货单」以提交瞬间的缺口重算落单；若提交的建议与提交瞬间缺口不一致，整次生成失败并提示「建议已过期」，不落任何单行（不改写成超缺口或已满仓）。
4. 在「补货小票」「满仓」「汇总」查看最近一张补货单的单行、满仓货道与合计，三者与落单瞬间建议一致。

## 接口约定

- `GET /api/refills/suggest` — 现算建议，不落库。
- `POST /api/refills/run` — 生成补货单；可带 `{"lines":[{"lane_id":..,"fill_qty":..}]}` 做乐观校验，与提交瞬间建议不符则 `409 建议已过期`，整单不落。
- `GET /api/refills/latest|summary|full` — 最近一张补货单及其合计/满仓（无单时 latest 返回 404，summary/full 返回零值）。
- `PATCH /api/lanes/{id}` — 修改货道 `stock` / `in_transit` / `capacity`。

## 开发与测试

```bash
docker compose exec api pytest -q
```
