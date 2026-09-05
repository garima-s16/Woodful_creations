# Product / Feature Strategy

This is an analysis document, not a code change. It reflects the actual
state of Woodful Creations as verified directly in the code, not
aspirational or generic advice.

## 1. Current Strengths

- **A real operational spine, not a demo.** Lead → Estimate → Order →
  Production Tasks → Payment is fully wired end-to-end with actual
  database persistence, not just UI screens.
- **Stock is genuinely authoritative.** `StockService` enforces real
  quantity/location validation on every issue, transfer, and
  adjustment, with an immutable ledger — this is not a spreadsheet
  replaced by a form, it is a real inventory system.
- **A chatbot that is actually useful for the two things that matter
  most in this business** — inventory and tasks — with 30 distinct
  operations (14 read, 16 write), all reusing existing services rather
  than duplicating business logic.
- **The chatbot works without any AI provider at all.** The
  deterministic keyword/pattern layer already answers stock, task,
  order, and client questions in English and Hinglish before Gemini is
  ever consulted — this is a genuine differentiator, not a fallback
  added for show.
- **Dual storage and dual authentication are already built for the
  future**, not retrofitted: local/Drive storage is a real abstraction
  behind one interface, and the login flow already has a separate
  token-based path for a native mobile app that doesn't exist yet.
- **Excel is treated as a real interface, not a side door** — header
  resolution is name-based (not column-position), supports aliases,
  and rejects ambiguous files rather than guessing.

## 2. Genuine Missing Capabilities

- **No independent backup/recovery path.** Drive is storage, not a
  backup strategy — if
  the Neon database or a Drive folder is lost, there is currently no
  separate recovery mechanism. This is a real production gap, not a
  nice-to-have.
- **No per-payment or per-purchase detail page.** Both are managed
  entirely through flat list tables with row actions. This was
  workable when I wired "Send Receipt" and "Documents" as row-level
  modal actions, but it is a genuine ceiling — a payment with a long
  history of related documents/emails has nowhere to show that
  history in one place.
- **The learning-candidate approval queue has no UI yet** — only the
  three backend endpoints (list/approve/reject) exist. A master
  currently has no way to review candidates except a raw API call.
- **No live-verified Drive or Gmail path.** Both are complete,
  correct implementations against the real documented APIs, but
  neither has ever actually run against live credentials in any
  session — this is a real, standing gap, not a design flaw.

## 3. High-Value Improvements

- **A minimal learning-candidate review screen** (a filtered table +
  approve/reject buttons on the existing Analytics or Settings page)
  — the backend is already done; this is a small, high-leverage
  addition that makes Section 21's entire "Gemini usage decreases over
  time" goal actually usable by a real person instead of only an API
  consumer.
- **Extend the learning-candidate consumption path beyond the two
  no-argument tools.** Currently only `get_upcoming_holidays` and
  `get_low_stock_materials` can be served from an approved candidate,
  because the candidate never stored the arguments Gemini extracted.
  A safe next step: store a *small, explicitly non-sensitive* argument
  shape for candidates whose tool schema only takes a single
  free-text lookup field (e.g. `material_name`), so "18 ply kitna
  bacha" can eventually resolve without Gemini too.
- **A payment detail page**, even a simple one, once documents/email
  history on a single payment grows past what a modal can reasonably
  show.

## 4. Capabilities That Should NOT Be Added

- **A second chatbot, AI persona, or "Gemini mode."** The one-chatbot
  principle is correct and should not be
  relaxed for a "power user AI mode" — that would fragment the product
  and reintroduce the exact provider-dependency risk this session
  worked to avoid.
- **A general-purpose document Q&A / "ask your files" feature.**
  Tempting given Drive storage exists, but it would mean feeding
  document *content* to an external AI provider — directly against
  this system's hard data boundary on what external AI providers may
  see. Not worth the exposure for a
  furniture ERP's actual use cases.
- **Full accounting/GST filing.** Woodful already tracks the
  financial data a furniture business needs operationally; becoming a
  compliance/filing platform is a different, much larger product than
  what this business needs from its ERP.

## 5. Simplicity Improvements

- **The chatbot's "I didn't quite catch that" fallback message names
  five categories** (stock, orders, clients, payments, staff) — accurate
  today, but this string will silently go stale as more tool coverage
  is added (holidays, documents, purchases already exist and aren't
  mentioned). Worth revisiting as a living list rather than a
  hardcoded string.
- **Mobile bottom navigation exists and is wired in**, but only a
  fraction of the 26+ page routes are reachable from it — worth an
  audit of which 4-5 destinations a carpenter/helper actually needs on
  a phone, versus what a founder needs on a laptop.

## 6. Founder Experience

Already strong: the Dashboard answers "what's happening / what's
pending / what needs attention" directly (follow-ups, delayed
production, pending purchases, upcoming deliveries all surface
without navigating anywhere). The chatbot adds a genuine shortcut on
top of this, not a replacement for it — exactly the right relationship
per Section 13.

## 7. Employee Experience

Task assignment, status, and due dates are all real and enforced
through `StockService`/task services, not just displayed. The
`MobileBottomNav` and 16px-input iOS fix suggest real attention was
paid to a carpenter or helper using this on a phone, not just a
founder on a laptop — this is worth preserving as new features are
added, since it is easy to regress by defaulting new UI to
desktop-only patterns.

## 8. Competitive Position

Woodful's actual advantage over "founder uses ChatGPT + WhatsApp +
Excel" is structural, not conversational: permissions
(`require_role("master")` enforced server-side on every sensitive
write), an audit trail, and a real stock ledger a spreadsheet cannot
give. The chatbot is additive convenience on top of that structure —
correctly scoped per Section 3 ("do not compete by merely adding AI").

## 9. Future-Ready Capabilities

The dual-auth architecture (cookie for web, bearer token for a future
native app) and the storage abstraction (local/Drive behind one
interface) mean a future mobile app or a future storage provider
would not require touching business logic — this was verified
directly in code this session, not assumed.

## 10. Recommended Priority

1. Independent backup/recovery strategy for Neon + Drive (real
   production risk today)
2. Learning-candidate review UI (small effort, unlocks a mostly-built
   backend capability)
3. Live Drive/Gmail credential verification (correctness risk, not
   effort — this needs a real environment, not more code)
4. Payment detail page (only once document/email volume on a single
   payment genuinely outgrows the current modal)
