# Backend TODO

## Completed This Session ✅

- [x] Merge `dev_tata` (fast-forward) — schema source of truth is now tata's normalized ERD
- [x] Adopted schema features: `sales_order_items` SO lines, `ksus` natural key (`code` PK), dealer/user FKs, `Date` columns, audit FKs (`created_by_id`, `user_id`, `uploaded_by_id`)
- [x] Remove unused M2M tables `sales_order_dealers` and `picking_list_sales_orders` (links derivable from `sales_order_items` and `picking_item_dealers.sales_order_id`; verified written-but-never-read before removal)
- [x] Re-apply `init_db` fix — Alembic wrapped in `asyncio.to_thread()` so the event loop isn't blocked at startup (was reverted by the tata merge)
- [x] Re-integrate `picking_excel.py` into `backend/app/` (deleted by tata's commit) and import as `app.picking_excel` — byte-identical to the project-root copy
- [x] Drop the Dockerfile `COPY picking_excel.py .` root-copy workaround — backend no longer depends on the project root
- [x] Update `SCHEMA.md` (ERD, design notes, view definitions, import flow) and this file
- [x] Verify on scratch DB: full Alembic chain (`08e53341e9eb → befa64175889 → c1a4f7b2d901`), 17 tables, M2M absent
- [x] Verify ORM round-trip with app session config (`expire_on_commit=False`) incl. compat properties (`no_so`, `code`, `name`, `category`)
- [x] Verify server boot: uvicorn up, Swagger UI at `/docs` (swagger-ui-dist@5), OpenAPI 3.1 with 16 paths, `POST /api/auth/login` returns JWT, authed `GET /api/picking/` → 200
- [x] Verify integrated parser against real `dummypicking.xlsx`: 3 lists, 19 items in first list, dealer rows with `noSo/code/dealer/qty`

### Earlier sessions ✅

- [x] Normalize schema — master tables (`trucks`, `ksus`, `dealers`, `sales_orders`, `sales_order_items`)
- [x] `picking_lists` → `truck_id` FK; `picking_items` → `ksu_code` FK (snapshot columns removed); `picking_item_dealers` → `dealer_id` FK
- [x] Update all service queries to eager-loaded FK relationships; routers serialize via compat properties (`picking_id`, `no_ds`, `dealer_code`, …)
- [x] Destructive Alembic migration `c1a4f7b2d901` (schema reset; data disposable by design)
- [x] Full-flow verification on the pre-merge schema: Docker build, migration, seed, login, upload, dashboard

## Still Open

### Verification follow-ups (post-merge re-checks)
- [ ] Docker build + full container flow (the last verified Docker build predates the schema change and Dockerfile edit)
- [ ] End-to-end Excel upload through the running API with `dummypicking.xlsx` (parser verified standalone; upload endpoint not yet re-tested post-merge)

### High Priority
- [ ] Add database views (`v_picking_totals`, `v_expedition_stats`, `v_driver_stats`, `v_dealer_confirmation_stats`, `v_item_dealer_summary`) as defined in SCHEMA.md
- [ ] Add `POST /api/auth/logout` endpoint — backend should clear the httpOnly cookie
- [ ] Set httpOnly cookie on `POST /api/auth/login` (Set-Cookie header) so frontend can remove localStorage token management
- [ ] Add input validation on all endpoints (currently accept raw `dict`)

### Medium Priority
- [ ] Caddyfile: route `/docs` and `/openapi.json` to the backend — currently only `/api/*` is proxied, so Swagger UI is unreachable through the public entry (`:15000`)
- [ ] Dashboard endpoint `GET /api/picking/dashboard` — use `v_picking_totals` view instead of loading all lists
- [ ] Add pagination to `GET /api/picking/` and `GET /api/debts/`
- [ ] Add proper error types (not just `{ "detail": "message" }`)
- [ ] Remove `debug: True` default in config.py for production

### Low Priority
- [ ] Add `__pycache__/` and `.venv-linux/` to `.gitignore` (only `.idea` is ignored today; caches keep showing up as untracked)
- [ ] Replace broken macOS `.venv` artifact locally; recreate per-OS and never commit
- [ ] Add API rate limiting
- [ ] Add request/response logging middleware
- [ ] Add OpenAPI docs customization (tag descriptions, examples)
- [ ] Add database backup/restore scripts
