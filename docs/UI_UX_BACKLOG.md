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

## MEDIUM PRIORITY

### 5. Material creation form has no "intelligent defaults" from typed text
**Severity:** Medium
**Component:** `MaterialsPage.jsx` create flow (`MaterialAttributesEditor` + `Form`)
**Issue:** Section 8 of the UX brief wants typing "HDHMR 6mm" into the
Name field to auto-infer Category/Subcategory/Thickness, pre-filling the
rest of the form. Not implemented.
**Why not attempted this turn:** `MaterialAttributesEditor` (renders the
Category/Subcategory/Specifications pickers) and `Form` (renders Name/
Unit/etc., including the Name field this feature would read from) are
sibling components with no shared reactive state today -
`MaterialAttributesEditor` only reports its OWN selections upward via
`onChange`, it has no visibility into what's typed into `Form`'s
internal `formData`. Building this properly means either lifting the
Name field's value out of `Form` into the parent page (so both
components can react to it), or moving name-based inference into
`MaterialAttributesEditor` itself with its own text input feeding both
the inference AND the eventual submitted name - a real architectural
change, not a small addition. Attempting a rushed version risked a
half-working feature that appears to work for the brief's own example
("HDHMR 6mm") but breaks for anything slightly different, which is worse
than being explicit that it doesn't exist yet.
**Planned resolution:** Lift the material name into `MaterialsPage`'s own
state, pass it to `MaterialAttributesEditor` as a prop, and reuse the
same regex-extraction approach already built and tested for the chatbot's
`parse_add_material_command` (backend) - or expose that logic via a
small `/api/materials/interpret?text=...` endpoint the frontend can call
as the user types, so the inference logic isn't duplicated between chat
and the form. **Not started.**

---

### 2. Chatbot's initial-greeting suggestion doesn't update on navigation
**Severity:** Medium — cosmetic staleness, not a functional bug.
**Component:** `ChatWidget.jsx`
**Issue:** The contextual suggestion chip shown in the assistant's very
first greeting message is computed once via a lazy `useState` initializer
at mount time. If a user opens the widget on a Material page (sees "Tell
me about this material"), then navigates to a Supplier page without
closing the panel, that already-rendered greeting's suggestion chip still
says "Tell me about this material" instead of updating to "Compare this
supplier".
**Important distinction:** this does NOT affect actual chatbot
functionality - every message send already rebuilds `context` fresh from
current route params (see `send()`), so the backend always understands
the current page correctly. This only affects one already-rendered
suggestion chip's label.
**Expected behavior:** The suggestion chip in the greeting should reflect
the page the user is CURRENTLY on, live, not just the page at first mount.
**Planned resolution:** Either regenerate the greeting's suggestions
reactively (a `useEffect` keyed on `location.pathname` that
appends/replaces a "current page" suggestion chip without wiping chat
history), or accept this as permanent minor polish given low user impact.
**Not started.**

### 3. "Why is this project over budget?" not offered as a context suggestion
**Severity:** Medium
**Component:** `ChatWidget.jsx` (order/project context)
**Issue:** Requested example: on a Project (Order) page, offer "Why is
this project over budget?" as a contextual suggestion, alongside Material
→ "Tell me about this material" and Supplier → "Compare this supplier".
**Why not implemented as literally requested:** showing "Why is this
project over budget?" unconditionally on every order - including ones
that are on-budget or under-budget - would be presumptuous and
potentially misleading, which conflicts with this project's standing
principle against fabricating or implying information not backed by real
data. A order that's actually under budget being asked "why is it over
budget" is a real, avoidable UX flaw.
**Expected behavior:** Only offer this specific suggestion when the
order's actual profitability data (`OrderService.profitability()`,
already computed backend-side) shows a real variance - i.e., check
`current_projected_cost > estimated_cost` (or the equivalent real field)
before offering the suggestion, and phrase it neutrally ("How is this
project's budget tracking?") when there's no variance.
**Planned resolution:** Fetch profitability data on the order detail page
(already available via existing `OrderService`), pass a computed
`isOverBudget` flag into `ChatWidget` context, and make the suggestion
conditional on that flag rather than universal. **Not started.**

---

## RESOLVED

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
suggestion chip is still only computed once at mount (see item 2 below -
this pre-existing limitation wasn't fixed here), so simply passing
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
