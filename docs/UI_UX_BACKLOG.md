# Woodful Creations — UI/UX Backlog

Tracks known issues in existing features found during implementation, so
deferred work is never silently forgotten. Each entry: severity,
affected component, the issue, expected behavior, and planned resolution.

Priority is not the same as sequence — this list is reordered as new
information changes what's actually highest-value, not worked top-to-bottom
mechanically.

---

## HIGH PRIORITY

### 1. Material Catalog filters are generic, not category-aware
**Severity:** High — explicitly named a required fix, not optional polish.
**Component:** `MaterialsPage.jsx` (Material Catalog / Inventory list)
**Issue:** Filters are hard-coded to the legacy flat fields `brand_grade`
and `thickness_size`, shown identically for every material regardless of
category. A Paint material shows a "Thickness" filter (meaningless for
paint); a Laminate material has no "Finish" or "Design" filter at all,
even though `MaterialAttributeDefinition` (built earlier) already supports
exactly this per-subcategory customization.
**Expected behavior:** Filters must be dynamically derived from the
selected category/subcategory's actual `MaterialAttributeDefinition` set.
Example: Plywood → Brand, Grade, Thickness, Sheet Size. Laminate → Brand,
Finish, Colour, Thickness, Design. Drawer Channel → Brand, Length, Load
Capacity, Mechanism. Paint → Brand, Type, Colour, Finish, Pack Size. Never
show a filter that isn't relevant to the selected category.
**Planned resolution:** When a category/subcategory filter is selected,
fetch that subcategory's `MaterialAttributeDefinition` list
(`GET /api/material-categories/subcategories/{id}`, already returns
`attribute_definitions`) and render filter controls from it instead of the
two hard-coded fields. Filter materials by `MaterialAttributeValue` rather
than the legacy string columns. Requires: a materials-by-attribute-value
query on the backend (doesn't exist yet - `list_materials` doesn't
currently accept attribute-value filters), plus real seed/demo materials
that actually use the new hierarchy (most existing materials still only
have the legacy flat `category` string, so this filter would have little
to show until adoption grows). **Not started.**
**Status:** Deliberately not fixed yet - correctly deprioritized in favor
of the Founder Command Center (higher product value, was completely
unbuilt), per explicit instruction. Material Catalog is NOT considered
complete until this is resolved.

---

## MEDIUM PRIORITY

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

### 4. No Purchase Cart-specific chatbot context ("Optimize this purchase")
**Severity:** Medium
**Component:** `ChatWidget.jsx` + `CartDrawer.jsx`
**Issue:** Requested example: while the Purchase Cart is open, offer
"Optimize this purchase" as a contextual suggestion. Unlike Material/
Supplier/Order, the cart isn't a routed page - it's a drawer, and its
open/closed state currently lives as local state in whatever parent
renders `CartDrawer`, not in Redux, so `ChatWidget` (a sibling component)
has no way to know "the cart is open right now."
**Expected behavior:** When the cart drawer is open, the chat widget
should recognize this and offer "Optimize this purchase" (matching the
already-real cart shortage-math and supplier-price-comparison data now
available via `SupplierMaterial`).
**Planned resolution:** Lift cart-drawer open/closed state into a small
Redux slice (or extend the existing `chatUi` coordination slice) so
`ChatWidget` can read it the same way it already reads route params. The
actual "optimize" logic itself (grouping cart items by cheapest available
supplier using real `SupplierMaterial` price data) also does not exist
yet on the backend and would need its own implementation - this is a
two-part gap, not just a UI wiring gap. **Not started.**

---

## RESOLVED

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
