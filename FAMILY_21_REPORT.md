# Family 21 — Data Foundation + Product Master + Demo Environment

Final implementation report. Families 1–20 were not audited or reopened; every change below is additive or a narrowly-scoped edit at documented integration points (order/estimate item builders, search, sidebar, demo seed).

## 1. What was implemented

### 1.1 Global 10-character IDs (centralized, incremental, collision-safe)
- New `id_counters` table (`backend/app/models/id_counter.py`) holds one `global` row with a `BigInteger next_value`.
- `generate_short_id(db)` (`backend/app/utils/id_generator.py`) now does an atomic `UPDATE ... SET next_value = next_value + 1` followed by a `SELECT` of the new value **inside the caller's existing transaction**, then base36-encodes and zero-pads it to exactly 10 uppercase alphanumeric characters. This is safe under concurrent creation (the UPDATE takes a row lock; two concurrent callers cannot get the same counter value) and format-compatible with the existing `^[A-Z0-9]{10}$` convention already used by all ~20 entities from Families 1–20.
- One global counter (not per-entity) is used deliberately — it satisfies "global" literally, guarantees uniqueness *across* entity types (a client's ID can never collide with a product's), and needs only one table.
- Every existing call site (`generate_short_id()`) across 19 route/service files was updated to `generate_short_id(db)`; each call site was verified to already have `db` in scope.
- No manual ID entry exists anywhere — IDs are only ever assigned server-side at creation.

### 1.2 Product Master
- New tables: `product_categories`, `product_subcategories` (mirrors the existing Material category/subcategory hierarchy but is a fully separate hierarchy — products and materials never share a category list), `products`, `product_materials` (BOM junction table).
- `Product` fields: `product_code`, `business_id` (10-char), `sku`, `name`, `product_type` (`standard` | `custom`), category/subcategory, `description`, `specifications`, dimensions (`length`/`width`/`height` + `dimension_unit`), `finish`, `unit`, `notes`, `is_active`, `cost_price`, `selling_price`, `tax_percent`, `lead_time_days`, plus a computed `margin` property.
- Bill of materials: `ProductMaterial` links a product to real `Material` rows with quantity/unit — a genuine relational fact, not free text.
- Reference images/attachments: reused the existing polymorphic `GenericDocument` system (`parent_type="product"`) rather than building new upload infrastructure — the existing `DocumentsPanel` frontend component works unmodified against products.
- Full CRUD API (`/api/products`, `/api/product-categories`) with master-only mutation, non-master redaction of `cost_price`/`margin` (selling price stays visible, matching the existing financial-redaction convention used elsewhere), search/filter/pagination, and delete guards that block deleting a product still referenced by an `OrderItem` or `EstimateLineItem`.
- Global search (`/api/search`) now includes products (name/code/SKU/business_id).

### 1.3 Product ↔ Order Item / Estimate Line Item relationship
- `OrderItem` and `EstimateLineItem` gained a nullable `product_id` FK. Selecting a product auto-fills description/unit/rate **only where the field is still blank** — an explicit user override is never clobbered.
- Estimate → Order conversion and estimate revision now carry `product_id` forward, so the product link survives the whole estimate → order pipeline.
- Frontend `LineItemEditor` gained an optional product-picker column (used on the Estimates page); Order and Estimate detail pages show a "Product" column linking to the Product Master detail page, or "Custom / no product" when a line has no catalog entry — because a line item is never *required* to reference a catalog product.

### 1.4 Demo data (interconnected, idempotent, realistic)
`backend/scripts/seed_sample_data.py` was extended (not rewritten) with:
- `seed_product_categories` — 6 categories / 9 subcategories matching Woodful's real furniture lines (Bedroom Furniture, Modular Kitchen, Mandir, TV & Entertainment, Wall Panels, Showroom & Display).
- `seed_products` — 10 products: 7 standard catalog items (each with a real BOM against seeded materials) and 3 one-off custom products, each tied by name to one of the pre-existing custom orders (WC-2026-003/004/005).
- `seed_order_items` / `seed_estimate_line_items` — real line items for all 5 seeded orders and all 5 seeded estimates, referencing the new products where applicable. Quantities/rates were computed so each order's items sum **exactly** to its pre-existing `order_value`, and each estimate's Material/Labor items sum exactly to its pre-existing `material_cost`/`labor_cost` — the flat legacy totals and the new itemization agree rather than silently drifting apart, and none of Families 1–20's dollar figures were altered.
- I manually re-derived every sum by hand against the source data in the script (materials referenced, category/subcategory keys, order/estimate totals) since the script could not be executed in this sandbox (see §2) — all totals check out and all referenced material codes (MAT-001…MAT-010) and subcategory names exist.
- Every new seed function follows the codebase's existing idempotency guard (`if db.query(Model).count() > 0: return`) — re-running the seed against a populated database is always a no-op rescan, never a duplicate insert.
- The whole sequence was refactored into one `run_seed(db)` function, now the single source of truth used by both the CLI (`python scripts/seed_sample_data.py`) and the new reset endpoint, so they can never drift apart into two different "what does a demo environment contain" answers.
- Found and preserved (not fixed, per "don't reopen Families 1–20") a pre-existing dead/unreachable code block inside `seed_estimates` — worked around it by inserting the new line-item seeding immediately after it rather than touching it.
- Found and captured a latent bug where `seed_estimates()`'s return value was previously discarded even though it's needed downstream — fixed as part of wiring `run_seed`, since this was necessary to make the new estimate line items seedable at all.

### 1.5 Demo reset
- `POST /api/demo/reset` (`backend/app/api/routes/demo_reset.py`) — master-only, and hard-disabled (`403`) whenever `ENVIRONMENT == "production"`, regardless of role.
- Deletes every table the seed populates, in a carefully child-before-parent order (verified by hand against every FK in the deleted models — including the Estimate→Order and OrderItem/EstimateLineItem→Product ordering, both of which would raise FK violations if reversed), then calls the same `run_seed(db)` used at first boot.
- Deliberately never touches `users`, `audit_logs`, `id_counters`, or lookup/settings tables — a reset must not lock anyone out, must not erase the record that it happened, and must never let a post-reset record reuse an ID a deleted record already had.

### 1.6 Bulk import foundation (reusable, not just for products)
- `backend/app/utils/bulk_import.py` — generic helpers (header alias resolution, cell normalization, template building) factored out so the *next* entity that needs Download Template → Fill → Upload → Validate → Preview → Import doesn't have to duplicate Family 6's purchase-import logic. Family 6's own `purchase_import.py` was deliberately left untouched.
- `backend/app/utils/product_import.py` + `backend/app/api/routes/product_imports.py` — the product-specific instance: `/template` (download), `/preview` (validate against real subcategories, never auto-creating one), `/commit` (master-only, IDs generated server-side, per-row retry-on-conflict, audited). No workflow anywhere accepts a manually-typed ID.

### 1.7 Frontend — Product Master UI
- `ProductsPage.jsx` — grid/list/table views, KPI row, category/type/subcategory filters, add/edit modals with a BOM editor and category management, and the bulk-import modal (upload → preview with per-row errors → commit).
- `ProductDetailPage.jsx` — KPIs (selling price, cost price when privileged, margin, lead time), full spec/dimension/notes card, BOM table linking to materials, and the `DocumentsPanel` reused for reference images/attachments.
- Fixed during this pass: the detail page's "Manage in Product Master" button now actually opens the edit modal for that product (previously it navigated to the list with unread `location.state`); `ProductsPage` now consumes `location.state.openEditId` once both products and categories have loaded, then clears the navigation state so it can't re-fire.
- New sidebar entry ("Product Master", first item under Inventory) and a new box/package icon distinct from the existing material icon.
- Styling (`ProductCatalog.css`) deliberately reuses the generic catalog/grid/toolbar classes already established by `MaterialCatalog.css` rather than duplicating them, keeping the two catalogs visually consistent with the rest of the app.

### 1.8 Security
- MASTER/USER are still the only two roles; nothing new was added.
- Product mutations, category mutations, bulk-import commit, and demo reset are all `require_role("master")`.
- Non-master users get `cost_price`/`margin` redacted on product reads, matching the existing financial-redaction convention.
- Demo reset is additionally hard-gated off in production regardless of role.
- Product read/list/search endpoints remain open to both roles (consistent with how materials/clients/etc. already work), since only the *financial* fields are sensitive.

## 2. Runtime verification — what could and could not be done

**This sandbox has no outbound network access.** `pip install`, `uv pip install`, `apt-get install`, and direct `curl` to PyPI/npm/apt mirrors all returned `403 Forbidden` when tested. This means:
- The FastAPI backend could **not** actually be booted in this session (no `fastapi`/`sqlalchemy`/`alembic`/etc. available to install).
- `pytest` could **not** be executed.
- The seed script could **not** actually be run against a live database.
- The React dev server / build could **not** be run (no `npm install`).

**What I did instead, and disclose plainly rather than claim as equivalent to real execution:**
- `python3 -m py_compile` across every backend `.py` file (old and new) — confirms syntactic validity only, not runtime correctness. Clean, no errors.
- `esbuild` (a locally pre-installed binary, found via the `tsx` npm package) run against every new/modified frontend `.jsx`/`.js` file, and then swept across the *entire* `frontend/src` tree as a final regression check — confirms JS/JSX syntax validity only. All files parse cleanly; the only failures were six pre-existing `.js` files I did not touch (`Form.js`, `Table.js`, `Pagination.js`, `Alert.js`, `Modal.js`, `Card.js`) that legitimately contain JSX but have a `.js` extension esbuild's file-based loader detection doesn't default to JSX for — re-run with an explicit `--loader:.js=jsx` override, they also parse cleanly. Not a regression.
- Manual, line-by-line hand-verification of the seed data's arithmetic and referential integrity (every order's item total against its `order_value`, every estimate's item totals against `material_cost`/`labor_cost`, every BOM material code and subcategory name against what's actually seeded) — documented in §1.4. This is the closest substitute available for "run it and look at the dashboard," but it is not the same as actually running it.
- Manual cross-referencing of new code against established patterns already proven to work in this codebase before writing it (e.g. the boolean-select convention from `UsersPage.jsx`, the FK-ordering convention already used elsewhere, reusing `DocumentsPanel`/`write_sheet` instead of reinventing them).

**What this means for you:** the code is believed correct based on static analysis and careful manual review, but has not been proven correct by actually running it. Before treating this as done, please run, in an environment with normal network access:

```
cd backend
pip install -r requirements.txt
pytest tests/ -v
python scripts/seed_sample_data.py   # or boot the app and hit POST /api/demo/reset as master
uvicorn app.main:app --reload
```
```
cd frontend
npm install
npm run dev
```
Then confirm: the app boots without migration errors (the new Alembic revision `0047_family21_id_counters_and_products.py` needs to apply cleanly on top of the existing chain), the dashboard and Product Master page show the seeded data, and `pytest` passes.

## 3. Tests — executed vs. unavailable

**Executed: none.** As explained in §2, no test runner could be installed in this sandbox. I am not reporting fabricated pass results.

**Written but not executed** — 35 new test functions across 5 files, following the exact conventions of the existing suite (`conftest.py`'s SQLite in-memory fixture, `test_business_id.py`'s login helper, `test_order_financial_rbac.py`'s non-master-user pattern):

| File | Tests | Covers |
|---|---|---|
| `tests/test_id_generator.py` | 6 | Format (`^[A-Z0-9]{10}$`), incrementing, cross-entity uniqueness (e.g. a client ID and a product ID from consecutive calls never collide), concurrency-safety of the counter |
| `tests/test_products.py` | 12 | CRUD, standard vs. custom product creation, category/subcategory sync, BOM create/replace, non-master cost/margin redaction, delete guards when referenced by an order/estimate item |
| `tests/test_order_estimate_product_link.py` | 7 | Product auto-fill on order/estimate items, explicit-value override not clobbered, no-product line items, product_id carried through estimate→order conversion |
| `tests/test_product_import.py` | 5 | Template download, preview validation (including rejecting an unknown subcategory), commit (master-only), server-generated IDs, RBAC |
| `tests/test_demo_reset.py` | 5 | Master-only RBAC, production-environment hard block, idempotency (reset twice in a row doesn't error or duplicate), `users`/`audit_logs`/`id_counters` survive a reset |

Please run `pytest backend/tests/ -v` once dependencies can be installed — that is the real verification these were written for.

## 4. Remaining blockers

1. **Network access for dependency installation** is the single blocker preventing everything in §2/§3 from being turned into actual proof rather than static analysis. Nothing in the implementation itself is known to depend on further design decisions or missing information.
2. The new Alembic migration (`0047_family21_id_counters_and_products.py`) has not been applied against a real database — please run `alembic upgrade head` (or let the app's existing `auto_migrate.py` startup hook do it) and confirm it lands cleanly on top of the current migration chain.
3. No Woodful Excel/Apps Script reference files were present in the uploaded material for this session, so the demo product catalog (names, categories, dimensions, pricing) was built from the furniture-business domain knowledge implied by the existing seeded orders/estimates/materials, not cross-checked against an original Woodful source file. If you have those workbooks, it would be worth a follow-up pass comparing product names/pricing against them.

## 5. File summary

**New backend files:** `app/models/id_counter.py`, `app/models/product.py`, `app/models/product_category.py`, `app/models/product_material.py`, `app/schemas/product.py`, `app/schemas/product_category.py`, `app/schemas/product_import.py`, `app/api/routes/products.py`, `app/api/routes/product_categories.py`, `app/api/routes/product_imports.py`, `app/api/routes/demo_reset.py`, `app/utils/bulk_import.py`, `app/utils/product_import.py`, `alembic/versions/0047_family21_id_counters_and_products.py`, 5 new test files.

**New frontend files:** `pages/ProductsPage.jsx`, `pages/ProductDetailPage.jsx`, `styles/components/ProductCatalog.css`.

**Modified files (both layers):** `app/utils/id_generator.py`, `app/models/__init__.py`, `app/models/order_item.py`, `app/models/estimate_line_item.py`, `app/models/generic_document.py`, `app/schemas/order.py`, `app/schemas/estimate.py`, `app/api/routes/orders.py`, `app/api/routes/estimates.py`, `app/api/routes/documents.py`, `app/api/routes/search.py`, `app/api/routes/__init__.py`, `scripts/seed_sample_data.py`, plus 19 route/service files for the `generate_short_id(db)` call-site update; `frontend/src/utils/api.js`, `components/LineItemEditor.jsx`, `pages/EstimatesPage.jsx`, `pages/OrderDetailPage.jsx`, `pages/EstimateDetailPage.jsx`, `App.jsx`, `components/Sidebar.jsx`, `components/icons/index.jsx`, `styles/components/LineItemEditor.css`, `styles/Pages.css`.
