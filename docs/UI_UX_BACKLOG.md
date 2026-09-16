# Woodful Creations — UI/UX Backlog

Tracks known issues in existing features found during implementation, so
deferred work is never silently forgotten. Each entry: severity,
affected component, the issue, expected behavior, and planned resolution.

Priority is not the same as sequence — this list is reordered as new
information changes what's actually highest-value, not worked top-to-bottom
mechanically.

---

## HIGH PRIORITY

### 1. Material.location_id is single-valued - no true multi-location stock
**Severity:** High - architectural gap, not a UI polish item.
**Component:** `Material` model, Location UI (about to be built)
**Issue:** The brief's Section 10 example shows one material's stock
split across multiple locations simultaneously ("HDHMR 18mm: Rack A2 -
12, Rack B1 - 6, Total 18"). The current schema only supports
`Material.location_id` - ONE location per material, not a real
stock-by-location breakdown. This is the same class of limitation as
`current_stock` being a directly-mutated column rather than a ledger
(tracked separately, not yet resolved either) - true location-aware
inventory needs a `StockByLocation` (material_id, location_id, quantity)
table, or better, needs to fall out of the transaction ledger once that's
built (each stock movement records its location; current-stock-per-
location is then a derived sum, the same way `current_stock` itself
should be derived).
**Expected behavior:** A material's stock should be queryable per
location, and the total should always equal the sum across locations
(single source of truth, per the standing project principle - no second,
independently-maintained stock number).
**Planned resolution:** Depends on the stock ledger work (still not
started - see the standing note in prior turns' summaries about
`current_stock` remaining a mutated column). Do not build a parallel
location-quantity table ahead of the ledger; that would create two
divergent stock-tracking mechanisms. Build the Location UI now for what
genuinely exists (browsing/managing the location tree, assigning a
material's one primary location) without fabricating a per-location
breakdown the backend can't actually support yet. **Not started - this is
the correct dependency order, not a decision to defer arbitrarily.**

---

## RESOLVED

### R7. Material creation form's "intelligent defaults" from typed text
**Component:** `app/modules/inventory/services.py` (new function, following the current flat-file-per-domain convention - not a separate imports/ subdirectory), `GET
/api/materials/interpret-name` (new route), `MaterialsPage.jsx`
**Issue:** Section 8 of the UX brief wanted typing "HDHMR 6mm" into the
Name field to auto-infer Category/Subcategory/Thickness. The blocker
noted when this was first deferred - `MaterialAttributesEditor` and
`Form` had no shared reactive state to build this on - was real at the
time.
**What was fixed:** Built exactly the planned resolution: a shared
backend `interpret_material_name()` matches the typed name against
Subcategories/Materials the business has already created (two-tier
confidence - "high" for a direct existing-Subcategory-name match,
"medium" for a similar existing Material's own subcategory), never
hard-coding a category (Category/Subcategory names are entirely
user-defined per this project's standing principle) and never returning
a guess dressed up as a fact (confidence "none" means show nothing).
Exposed via `GET /api/materials/interpret-name`, called from
`MaterialsPage.jsx`'s create form with a 400ms debounce and a
request-id guard against a stale, out-of-order response overwriting a
newer one. The suggestion is never auto-applied - `applyNameSuggestion`
only runs on an explicit user click, matching this project's standing
"never silently mutate/decide for the user" principle.
**A real gap found and fixed in this pass:** the new backend component
had zero test coverage anywhere - genuinely different from other
recently-resolved chat items, which were pure frontend logic layered on
an already-tested endpoint. Added coverage in
`tests/modules/inventory/test_purchases_and_reporting.py`'s material-interpreter section
(6 tests: no-match returns "none" not a guess, thickness extraction is
independent of category matching, high-confidence via a real
Subcategory match, medium-confidence via a real similar Material -
deliberately using a shared word that is NOT the subcategory name
itself, to prove it's genuinely exercising the medium path and not
accidentally hitting the high one - the confidence field's presence,
and the required `name` param's validation). Also directly executed
the pure, DB-independent `extract_thickness`/`_base_tokens` functions
(10 assertions, all passing) as a faster, additional check on the
matching logic itself. A first draft of the test file used a guessed
material-creation field name (`current_stock`) that didn't match this
project's actual schema (`opening_stock`, confirmed against
`test_stock_operations.py`'s own working example) - caught and fixed
before treating the test as correct.

### R6. Chatbot's initial-greeting suggestion didn't update on navigation, and the budget/profitability suggestion was missing
**Component:** `ChatWidget.jsx`
**Issue (two related, previously-tracked gaps):** (1) The contextual
suggestion chip in the assistant's first greeting was computed once at
mount via a `useState` lazy initializer, so navigating to a different
page without closing the panel left it showing the old page's
suggestion. (2) No suggestion existed for asking about a project's
budget/profitability on an order page - the brief's requested "Why is
this project over budget?" was never offered.
**What was fixed:** A `useEffect` keyed on `location.pathname`/`params`/
`cartOpen`/`budgetSuggestion` now regenerates the greeting's suggestions
reactively, guarded to only touch the still-untouched initial greeting
(`prev.length !== 1 || prev[0].role !== 'assistant'` bails out) so an
actual in-progress conversation is never rewritten. For the budget
suggestion specifically: rather than showing "over budget" unconditionally
(which would be misleading for an on-budget or under-budget order,
against this project's standing principle against implying information
not backed by real data), it fetches the same `OrderService.profitability()`
figures the order detail page's own panel already displays - never a
separately re-derived calculation - and only offers a suggestion once that
real data resolves, phrased in terms of profitability rather than "budget"
(`estimated_gross_profit < 0` → "Why is this project running at a loss?",
otherwise the neutral "How is this project's profitability tracking?").
A 403 (non-master viewer, matching the endpoint's existing permission) or
any other failure just omits the suggestion, leaving the underlying
financial data exactly as restricted as it already was.
**Verified via:** careful reading of the full implementation (both
`useEffect`s and `buildContextualSuggestions`) confirming the guard
against overwriting a real conversation is correct, and that the
profitability determination never happens client-side or duplicates the
backend calculation. No dedicated test exists for this specific feature -
it's frontend-only logic layered on an already-tested backend endpoint,
so nothing new needed backend-side coverage.

### R4. Purchase Cart leaked between different users on the same browser
**Component:** `cartSlice.js`, `App.jsx`
**Issue:** The cart's localStorage key was a single global string
(`woodful_purchase_cart_v1`), not scoped to who was logged in. Logging
out and a different person logging in on the same browser would show
them the previous person's cart contents.
**What was fixed:** Storage key is now per-user
(`woodful_purchase_cart_v1_user_<id>`). State starts empty at module
load (before any user is known) and `loadCartForUser(userId)` is
dispatched reactively in `AppLayout` whenever `state.auth.user` changes
- covering both session restore and fresh login the same way, since
both just update that same piece of state, and correctly requiring no
separate hook for future auth flows. Logging out loads with `userId:
null`, which clears the in-memory view without touching any stored
data - the same user logging back in still finds their cart exactly as
they left it, which was already working correctly and remains so.
**Verified via:** confirmed `/login` and `/me` both include `id` in
their response (the previous turn's chat-context work already
established this pattern) before relying on it here.

### R5. Chatbot had no profit/margin handling, and RBAC audited more broadly
**Component:** `chat_service.py`
**Issue:** No keyword handling existed for "profit"/"margin" at all -
asking about profitability fell through to the generic "I didn't quite
catch that" fallback for every role, master included. Separately
audited whether task/leave name-based lookups needed similar RBAC
gating, given they let any user ask about a colleague's records with
no role check.
**What was fixed:** Added real profit/margin handling
(`_profitability_summary`), reusing `OrderService.profitability()` -
the exact calculation the dashboard's own "Gross Margin" figure already
uses, not a separately re-derived one - gated to master/manager only,
matching the existing pattern for payments/purchases exactly (a real
"master/manager accounts only" denial, never silence or a generic
non-answer).
**What was deliberately NOT changed:** task/leave name-based lookups
were checked against the real Leaves API (`list_leaves` in
`leaves.py`) and found to already allow any authenticated user to view
any colleague's leave records via the `employee_id` filter - only
*approving* a leave is master/manager-restricted. The chatbot matching
that existing policy is correct, not a gap; restricting it further
would have made the assistant less capable than the actual page for no
real reason, so this was intentionally left as-is.
**Verified via:** 5 backend tests, including one confirming the exact
figures the chatbot reports match `OrderService.profitability()`'s
output via the dashboard endpoint character-for-character, not just
that *a* number is returned.

### R3. Purchase Cart chatbot context ("Optimize this purchase")
**Component:** `cartSlice.js`, `ChatWidget.jsx`, `chat_service.py`
**What was fixed:** Both real halves of the two-part gap. (1) Lifted
cart-drawer open/closed state from `App.jsx`'s local `useState` into
`cartSlice.isOpen` - `App.jsx` now dispatches `openCart()`/`closeCart()`
instead of managing its own state, so there's one source of truth both
it and `ChatWidget` read. (2) Since the cart has no backend
representation at all, `ChatWidget` now sends its contents as
`context.cart_items` (material_id + quantity) on every message while
the cart is open - a genuinely different kind of context than
`record_type`/`record_id` (data the server has no other way to see, not
"what record is open"), documented as such in `ChatContext`'s
docstring. `_optimize_cart()` groups the cart by the real cheapest
available `SupplierMaterial` price per item, falling back to the
material's `average_rate` when no supplier is linked, and reports
genuine savings (cheapest total vs. worst-case total) - a material with
only one price source contributes zero to the savings figure rather
than a fabricated one.
**A real bug caught mid-implementation:** the initial-greeting
suggestion chip was still only computed once at mount at the time (see
R6, resolved later - this pre-existing limitation wasn't fixed here), so simply passing
`cartOpen` to that function alone wouldn't make "optimize this purchase"
actually work if the cart is opened after the widget is already mounted
(the common case). The suggestion greeting was extended as a minor
improvement for the fresh-mount case, but the functional fix is that
`context.cart_items` is rebuilt fresh from Redux on every `send()` call,
independent of the suggestion chip - asking works correctly regardless
of whether the chip text happens to be stale.
**Verified via:** 4 backend tests, including one that hand-traces exact
savings numbers (two suppliers at 100/120 for one item, a single
fallback price for another) and confirms the reported savings figure
matches precisely - not just that a number appears.

### R2. Seed data's MaterialCategory rows were flat and orphaned
**Component:** `scripts/seed_sample_data.py`
**Found during:** explicit verification pass on the seed script, not
during original implementation - a fresh, careful re-read surfaced it.
**What was wrong:** `LOOKUPS[MaterialCategory]` created 16 top-level
`MaterialCategory` rows (Plywood, HDHMR, MDF, ...) with zero
`MaterialSubcategory` children - directly contradicting the two-level
Category->Subcategory hierarchy the rest of this project uses. Worse,
`seed_materials` never referenced these rows at all (materials only set
the legacy flat `category` string), so they were completely disconnected
data that misrepresented the real model to anyone browsing categories.
**What was fixed:** Removed the flat entry from `LOOKUPS`. Added
`seed_material_hierarchy()` building a real 2-level structure matching
Section 26's own categorization (Board & Wood Materials -> Plywood/
HDHMR/MDF/...; Surface Materials -> Laminate/Acrylic/...; Hardware ->
Hinges/Drawer Channels/Handles; etc.), and wired each seeded material's
real `subcategory_id` to match, so the Material Catalog's dynamic
filters (built two turns ago) will actually have real subcategory data
to filter by once this seed runs.
**Also fixed in the same pass:** a second instance of this session's
recurring `str_replace`-deletes-a-`def`-line mistake (this is the third
occurrence) - caught immediately via `py_compile` plus an exhaustive
AST-based expected-vs-actual function name comparison, not just eyeballing
the diff.


### R0. Material Catalog filters were generic, not category-aware
**Component:** `MaterialsPage.jsx`, `list_materials` (backend)
**What was fixed:** Selecting a Category/Subcategory now loads that
subcategory's real `MaterialAttributeDefinition` set and renders filter
controls dynamically from it (text/number/select per the attribute's real
type), instead of two hard-coded `brand_grade`/`thickness_size` filters
shown for every material regardless of category. Required building the
backend query first (`attribute_filters` JSON param on `GET
/api/materials/`, AND-narrowing across multiple attribute filters,
verified by test) and the Material creation form using the real hierarchy
(so there's something real to filter). Legacy Brand/Thickness filters
kept as a fallback, but only shown when no subcategory filter is active,
so they don't visually compete with the new dynamic ones.
**Verified via:** 10 backend tests across the two related test files,
including one reproducing the exact combined `subcategory_id` +
`attribute_filters` request shape the UI now actually sends, with a decoy
record proving the two filters correctly AND together rather than
matching either independently.


### R1. Persistent top-of-app AI command bar (reverted)
**Component:** `Navbar.jsx`
**What happened:** Initially built a second, always-visible AI input in
the navbar per an earlier UI brief's literal Section 6 wording ("a command
bar at the top... as a primary interaction"). This was explicitly
corrected: the floating bottom-right chatbot must remain the single,
primary AI entry point - no second persistent AI interface. Removed the
navbar input, its handler, and its CSS entirely (not just hidden).
**What was kept:** the `chatUiSlice` Redux slice (`openWithMessage`/
`clearPendingMessage`) - this is reusable, non-duplicating plumbing for
future *scoped* "Ask AI" trigger buttons (e.g. an empty state's "[Ask AI]"
button opening the one floating widget with a prefilled message), which
is different from a second always-visible command surface.
