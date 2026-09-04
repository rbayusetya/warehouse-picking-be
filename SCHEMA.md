# Database Schema

> Normalized schema for the Picking Control Gudang application.
> All data is seeded from Excel imports. Master tables are auto-created during import.

---

## ERD Diagram

```mermaid
erDiagram
    %% ─── Master Tables ───

    USERS {
        uuid id PK
        varchar username UK "NOT_NULL"
        varchar password_hash "NOT_NULL"
        varchar name "NOT_NULL"
        varchar role "NOT_NULL admin|kepala|ekspedisi|dealer"
        varchar role_label "NOT_NULL"
        varchar expedition "NULLABLE ekspedisi only"
        varchar dealer_code "NULLABLE dealer only"
        boolean is_active "DEFAULT true"
        datetime created_at
    }

    TRUCKS {
        uuid id PK
        varchar expedition "NOT_NULL"
        varchar plate "NOT_NULL"
        varchar driver_name "NOT_NULL"
    }

    KSU_ITEMS {
        uuid id PK
        varchar code "NOT_NULL UK"
        varchar name "NOT_NULL"
        varchar category "NOT_NULL"
    }

    DEALERS {
        uuid id PK
        varchar code "NOT_NULL UK"
        varchar name "NOT_NULL"
    }

    SALES_ORDERS {
        uuid id PK
        varchar so_number "NOT_NULL UK"
        varchar ksu_item_id FK "NOT_NULL"
        float ksu_quantity "NOT_NULL"
        varchar dealer_id FK "NOT_NULL"
    }

    %% ─── Transaction Tables ───

    PICKING_LISTS {
        uuid id PK
        varchar picking_id "NOT_NULL UK No Picking List"
        varchar date "NOT_NULL"
        varchar no_ds "NULLABLE Delivery Schedule"
        uuid truck_id FK "NOT_NULL"
        varchar status "DEFAULT draft draft|picked|handover_completed|closed"
        varchar source_file "NULLABLE"
        datetime created_at
        datetime updated_at
    }

    PICKING_ITEMS {
        uuid id PK
        uuid picking_list_id FK "NOT_NULL"
        uuid ksu_item_id FK "NOT_NULL"
        varchar code "NOT_NULL snapshot from KSU"
        varchar name "NOT_NULL snapshot from KSU"
        varchar category "NOT_NULL snapshot from KSU"
        float planned_qty "DEFAULT 0"
        float actual_qty "DEFAULT 0"
        boolean confirmed "DEFAULT false"
        text note "DEFAULT empty"
    }

    PICKING_ITEM_DEALERS {
        uuid id PK
        uuid picking_item_id FK "NOT_NULL"
        uuid dealer_id FK "NOT_NULL"
        varchar no_so "NULLABLE Sales Order number"
        float qty "DEFAULT 0"
    }

    %% ─── Operational Tables ───

    HANDOVERS {
        uuid id PK
        uuid picking_list_id FK "NOT_NULL UK"
        varchar admin_name "NOT_NULL"
        varchar driver_name "NOT_NULL"
        text signature_admin_url "NULLABLE"
        text signature_driver_url "NULLABLE"
        varchar created_by "NULLABLE"
        varchar created_at "NOT_NULL"
    }

    SETTLEMENTS {
        uuid id PK
        uuid picking_item_id FK "NOT_NULL"
        float qty "NOT_NULL"
        varchar date "NOT_NULL"
        varchar driver "NOT_NULL"
        text note "DEFAULT empty"
        varchar by "NULLABLE"
        varchar at "NOT_NULL"
    }

    SETTLEMENT_HANDOVERS {
        uuid id PK
        uuid settlement_id FK "NOT_NULL UK"
        varchar admin_name "NOT_NULL"
        varchar driver_name "NOT_NULL"
        text signature_admin_url "NULLABLE"
        text signature_driver_url "NULLABLE"
        varchar created_by "NULLABLE"
        varchar created_at "NOT_NULL"
    }

    DEALER_CONFIRMATIONS {
        uuid id PK
        uuid picking_item_id FK "NOT_NULL"
        varchar dealer_code "NOT_NULL"
        varchar status "NOT_NULL match|shortage|excess"
        text signature_dealer_url "NULLABLE"
        text signature_driver_url "NULLABLE"
        varchar created_at "NOT_NULL"
    }

    DEALER_RETURNS {
        uuid id PK
        uuid dealer_confirmation_id FK "NOT_NULL UK"
        varchar driver "NOT_NULL"
        varchar return_date "NOT_NULL"
        text notes "DEFAULT empty"
    }

    HISTORY_ENTRIES {
        uuid id PK
        uuid picking_list_id FK "NOT_NULL"
        varchar at "NOT_NULL"
        varchar by "NULLABLE"
        text text "NOT_NULL"
    }

    UPLOADED_FILES {
        uuid id PK
        varchar filename "NOT_NULL"
        varchar original_name "NOT_NULL"
        text file_url "NULLABLE"
        varchar uploaded_by "NULLABLE"
        datetime created_at
    }

    %% ─── Relationships ───

    USERS ||--o{ PICKING_LISTS : "uploads import"

    TRUCKS ||--|{ PICKING_LISTS : "assigned to"

    PICKING_LISTS ||--|{ PICKING_ITEMS : "contains"
    PICKING_LISTS ||--o| HANDOVERS : "has"
    PICKING_LISTS ||--|{ HISTORY_ENTRIES : "tracked by"

    KSU_ITEMS ||--|{ PICKING_ITEMS : "references"
    KSU_ITEMS ||--o{ SALES_ORDERS : "listed in"

    PICKING_ITEMS ||--|{ PICKING_ITEM_DEALERS : "distributed to"
    PICKING_ITEMS ||--|{ SETTLEMENTS : "paid via"
    PICKING_ITEMS ||--|{ DEALER_CONFIRMATIONS : "confirmed by"

    DEALERS ||--|{ PICKING_ITEM_DEALERS : "receives"
    DEALERS ||--o{ SALES_ORDERS : "owns"

    SETTLEMENTS ||--o| SETTLEMENT_HANDOVERS : "signed off"

    DEALER_CONFIRMATIONS ||--o| DEALER_RETURNS : "may return"
```

---

## Views

### `v_picking_totals`

Aggregated totals per picking list. Used by dashboard stats and debt calculations.

```sql
CREATE OR REPLACE VIEW v_picking_totals AS
SELECT
    pl.id AS picking_list_id,
    pl.picking_id,
    pl.date,
    pl.status,
    pl.expedition,
    pl.driver,
    COALESCE(SUM(pi.planned_qty), 0) AS total_planned,
    COALESCE(SUM(pi.actual_qty), 0) AS total_actual,
    COALESCE(SUM(pi.confirmed::int), 0) AS confirmed_count,
    COUNT(pi.id) AS total_items,
    CASE
        WHEN pl.status IN ('picked', 'handover_completed', 'closed')
        THEN GREATEST(
            COALESCE(SUM(pi.planned_qty), 0)
            - COALESCE(SUM(pi.actual_qty), 0)
            - COALESCE((SELECT SUM(s.qty) FROM settlements s WHERE s.picking_item_id = pi.id), 0),
            0
        )
        ELSE 0
    END AS total_debt
FROM picking_lists pl
LEFT JOIN picking_items pi ON pi.picking_list_id = pl.id
GROUP BY pl.id;
```

### `v_item_dealer_summary`

Per-item dealer distribution. Used by dealer page and dashboard dealer summary.

```sql
CREATE OR REPLACE VIEW v_item_dealer_summary AS
SELECT
    pi.id AS picking_item_id,
    pi.code AS item_code,
    pi.name AS item_name,
    pi.category AS item_category,
    pi.planned_qty,
    pi.actual_qty,
    pl.picking_id,
    pl.date,
    pl.driver,
    pl.expedition,
    d.id AS dealer_id,
    d.code AS dealer_code,
    d.name AS dealer_name,
    pid.qty AS dealer_qty,
    pid.no_so,
    dc.status AS confirmation_status
FROM picking_items pi
JOIN picking_lists pl ON pl.id = pi.picking_list_id
JOIN picking_item_dealers pid ON pid.picking_item_id = pi.id
JOIN dealers d ON d.id = pid.dealer_id
LEFT JOIN dealer_confirmations dc ON dc.picking_item_id = pi.id AND dc.dealer_code = d.code;
```

### `v_expedition_stats`

Per-expedition breakdown. Used by dashboard expedition table.

```sql
CREATE OR REPLACE VIEW v_expedition_stats AS
SELECT
    t.expedition,
    t.plate,
    t.driver_name,
    COUNT(pl.id) AS total_lists,
    COUNT(pl.id) FILTER (WHERE pl.status = 'draft') AS draft_count,
    COUNT(pl.id) FILTER (WHERE pl.status = 'picked') AS picked_count,
    COUNT(pl.id) FILTER (WHERE pl.handover_id IS NOT NULL) AS handover_count,
    COALESCE(SUM(vpt.total_planned), 0) AS total_items,
    COALESCE(SUM(vpt.total_debt), 0) AS total_debt
FROM trucks t
LEFT JOIN picking_lists pl ON pl.truck_id = t.id
LEFT JOIN v_picking_totals vpt ON vpt.picking_list_id = pl.id
GROUP BY t.id, t.expedition, t.plate, t.driver_name;
```

### `v_driver_stats`

Per-driver breakdown. Used by dashboard driver table.

```sql
CREATE OR REPLACE VIEW v_driver_stats AS
SELECT
    t.driver_name,
    t.expedition,
    COUNT(pl.id) AS total_lists,
    COUNT(pl.id) FILTER (WHERE pl.status = 'draft') AS draft_count,
    COUNT(pl.id) FILTER (WHERE pl.status = 'picked') AS picked_count,
    COUNT(pl.id) FILTER (WHERE pl.handover_id IS NOT NULL) AS handover_count,
    COALESCE(SUM(vpt.total_planned), 0) AS total_items,
    COALESCE(SUM(vpt.total_debt), 0) AS total_debt
FROM trucks t
LEFT JOIN picking_lists pl ON pl.truck_id = t.id
LEFT JOIN v_picking_totals vpt ON vpt.picking_list_id = pl.id
GROUP BY t.id, t.driver_name, t.expedition;
```

### `v_dealer_confirmation_stats`

Dealer confirmation summary. Used by dashboard dealer summary.

```sql
CREATE OR REPLACE VIEW v_dealer_confirmation_stats AS
SELECT
    d.id AS dealer_id,
    d.code AS dealer_code,
    d.name AS dealer_name,
    COUNT(pi.id) AS total_items,
    COUNT(dc.id) FILTER (WHERE dc.status = 'match') AS match_count,
    COUNT(dc.id) FILTER (WHERE dc.status = 'shortage') AS shortage_count,
    COUNT(dc.id) FILTER (WHERE dc.status = 'excess') AS excess_count,
    COUNT(pi.id) - COUNT(dc.id) AS pending_count
FROM dealers d
JOIN picking_item_dealers pid ON pid.dealer_id = d.id
JOIN picking_items pi ON pi.id = pid.picking_item_id
LEFT JOIN dealer_confirmations dc ON dc.picking_item_id = pi.id AND dc.dealer_code = d.code
GROUP BY d.id, d.code, d.name;
```

---

## Table Summary

| Category | Table | Purpose |
|----------|-------|---------|
| **Master** | `users` | Authentication & roles |
| **Master** | `trucks` | Expedition/plate/driver lookup |
| **Master** | `ksu_items` | Product catalog (code, name, category) |
| **Master** | `dealers` | Dealer directory |
| **Master** | `sales_orders` | Sales order → product → dealer link |
| **Transaction** | `picking_lists` | Picking list headers |
| **Transaction** | `picking_items` | Picking list line items (with KSU snapshot) |
| **Transaction** | `picking_item_dealers` | Dealer assignments per item |
| **Operational** | `handovers` | Admin → driver sign-off |
| **Operational** | `settlements` | Debt payment records |
| **Operational** | `settlement_handovers` | Settlement sign-off |
| **Operational** | `dealer_confirmations` | Dealer receipt status |
| **Operational** | `dealer_returns` | Return records |
| **Operational** | `history_entries` | Audit trail |
| **Operational** | `uploaded_files` | File upload tracking |
| **View** | `v_picking_totals` | Aggregated totals per list |
| **View** | `v_item_dealer_summary` | Item → dealer distribution |
| **View** | `v_expedition_stats` | Per-expedition breakdown |
| **View** | `v_driver_stats` | Per-driver breakdown |
| **View** | `v_dealer_confirmation_stats` | Dealer confirmation summary |

---

## Import Flow

When an Excel file is uploaded:

1. **Parse Excel** → extract picking lists, items, dealer assignments
2. **Upsert `trucks`** → deduplicate by (expedition, plate, driver_name)
3. **Upsert `ksu_items`** → deduplicate by (code, name, category)
4. **Upsert `dealers`** → deduplicate by (code)
5. **Upsert `sales_orders`** → deduplicate by (so_number) if present
6. **Insert `picking_lists`** → FK to truck_id
7. **Insert `picking_items`** → FK to ksu_item_id, snapshot code/name/category
8. **Insert `picking_item_dealers`** → FK to dealer_id, link to sales order
9. **Insert `history_entries`** → audit trail

All master table operations are **upsert** (insert or update on conflict) so re-importing the same Excel doesn't create duplicates.
