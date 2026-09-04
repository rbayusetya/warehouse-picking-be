# Backend TODO

## Completed This Session ✅

- [x] Normalize schema — added master tables (trucks, ksu_items, dealers, sales_orders)
- [x] Update picking_lists to use `truck_id` FK (was flat expedition/plate/driver)
- [x] Update picking_items to use `ksu_item_id` FK with snapshot columns (code/name/category)
- [x] Update picking_item_dealers to use `dealer_id` FK (was flat code/dealer name)
- [x] Alembic migration — drops all tables, recreates with normalized schema
- [x] Excel import upserts master tables (trucks, ksu_items, dealers, sales_orders)
- [x] Update all service queries to use eager-loaded FK relationships
- [x] Update all routers to serialize FK fields (l.truck.expedition, d.dealer.name)
- [x] Move `picking_excel.py` from project root into `backend/app/`
- [x] Fix `init_db()` — wrap Alembic in `asyncio.to_thread()` to unblock event loop
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
