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

1. 在「点位」「货道」查看售货机布局与库存；「货道」页可直接改库存 / 在途。
2. 在「销量」查看建议补量列（只读，按现网缺口现算），点「生成补货单」即以提交瞬间重算的建议落单。
   - 打开页面之后、提交之前若库存 / 在途被改过，旧建议不得落单：整次生成失败并提示「建议已过期」，补货单数不增；按页面新建议重新生成即可。
3. 在「补货小票」预览建议并生成补货单（打开页面只预览，不落单）。
4. 在「满仓」「汇总」查看已满货道与补货合计——与建议列、补货单同一份现算结果，四处数字始终对账一致。

## 接口约定

| 接口 | 说明 |
| --- | --- |
| `GET /api/refills/preview?location_id=` | 建议补量现算（只读，不落单） |
| `POST /api/refills/run?location_id=` | 生成补货单；可带 `{"expected": [{"lane_id", "fill_qty"}]}` 快照，与提交瞬间现算不一致则 `409 建议已过期` 且不落单 |
| `GET /api/refills` | 补货单列表（单数是否增长以此为准） |
| `GET /api/refills/summary` / `GET /api/refills/full` | 汇总总件数 / 满仓名单（现算） |
| `PATCH /api/lanes/{id}` | 货道改数：`{"stock"?, "in_transit"?, "capacity"?}` |

## 开发与测试

```bash
docker compose exec api pytest -q
```
