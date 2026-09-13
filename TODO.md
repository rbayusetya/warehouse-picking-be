# Backend TODO

## Completed This Session ✅

- [x] Normalize schema — added master tables (trucks, ksus, dealers, sales_orders, sales_order_items)
- [x] Merge `dev_tata` schema adoption: `sales_order_items` SO lines, `ksus` natural key, dealer/user FKs, `Date` columns, audit FKs (`created_by_id`, `user_id`, `uploaded_by_id`)
- [x] Remove unused M2M tables `sales_order_dealers` and `picking_list_sales_orders` (links derivable from `sales_order_items` and `picking_item_dealers.sales_order_id`)
- [x] Re-apply `init_db` fix — Alembic wrapped in `asyncio.to_thread()` so the event loop isn't blocked at startup
- [x] Update picking_lists to use `truck_id` FK (was flat expedition/plate/driver)
- [x] Update picking_items to use `ksu_code` FK (snapshot columns removed)
- [x] Update picking_item_dealers to use `dealer_id` FK (was flat code/dealer name)
- [x] Update all service queries to use eager-loaded FK relationships
- [x] Update all routers to serialize via compat properties (`picking_id`, `no_ds`, `dealer_code`, …)
- [x] Move `picking_excel.py` from project root into `backend/app/`
- [x] Add `SCHEMA.md` with finalized ERD in Mermaid format
- [x] Verify full flow: Docker build, migration, seed, login, upload, dashboard

## Still Open

### High Priority
- [ ] Add database views (`v_picking_totals`, `v_expedition_stats`, `v_driver_stats`, `v_dealer_confirmation_stats`, `v_item_dealer_summary`) as defined in SCHEMA.md
- [ ] Add `POST /api/auth/logout` endpoint — backend should clear the httpOnly cookie
- [ ] Set httpOnly cookie on `POST /api/auth/login` (Set-Cookie header) so frontend can remove localStorage token management
- [ ] Add input validation on all endpoints (currently accept raw `dict`)

### Medium Priority
- [ ] Dashboard endpoint `GET /api/picking/dashboard` — use `v_picking_totals` view instead of loading all lists
- [ ] Add pagination to `GET /api/picking/` and `GET /api/debts/`
- [ ] Add proper error types (not just `{ "detail": "message" }`)
- [ ] Remove `debug: True` default in config.py for production

### Low Priority
- [ ] Add API rate limiting
- [ ] Add request/response logging middleware
- [ ] Add OpenAPI docs customization (tag descriptions, examples)
- [ ] Add database backup/restore scripts
- [ ] Replace broken macOS `.venv` artifact in repo (it's not git-tracked; consider deleting locally and recreating per OS)
