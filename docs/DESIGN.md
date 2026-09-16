# Woodful Creations — Design System

This document is the persistent source of truth for Woodful's visual
identity and interaction philosophy. It describes the current,
implemented design system — not aspirations, not history. When the
design system changes, update this file in the same change.

## Identity

Woodful should feel **polished, calm, premium, practical, and
business-focused** — never generic SaaS, never decorative for its own
sake. Editorial, minimal, high-contrast typography over dashboard
clichés. The palette is a warm, restrained ink/gold family: near-black,
charcoal, warm ivory, deep wood brown, muted tan, caramel-gold accent —
not a cool, corporate blue-and-gray system.

Anti-generic rules:

- No decoration added purely for visual richness.
- No generic AI gradients, glowing purple/blue effects, or robot
  iconography anywhere the chatbot appears.
- No "five KPI cards on top of a table" dashboards — compose screens
  with genuine visual hierarchy, open sections, and typography, not
  a uniform grid of identical boxes.
- Prefer improving an existing shared component over creating a
  second, slightly-different one (no `ButtonV2`, `CardModern`, etc.).

## Typography

- **Display** (headings): Fraunces — a serif with real character,
  used for `h1`–`h6` and any editorial/hero numeral.
- **Body**: Inter — for everything else (paragraphs, labels, form
  controls, tables).
- Headings are weight 600 with a slight negative letter-spacing
  (`-0.01em`) for a tighter, more editorial feel than default browser
  heading spacing.

## Theme

Woodful is a two-theme system — dark and light — implemented as a
single semantic token layer that gets re-pointed by a `data-theme`
attribute on `<html>`, not two parallel stylesheets. Component CSS
should always read the semantic tokens (`--background`, `--surface`,
`--text-primary`, `--border`, …), never the raw palette
(`--color-ink`, `--color-ivory`, …) directly — that raw palette is
reserved for the fixed brand chrome described below.

**Theme selection rule:**

- **Before authentication** (login, forgot-password, reset-password):
  follows the system/browser `prefers-color-scheme` preference.
- **After authentication**: defaults to Dark, regardless of system
  preference — the authenticated application has its own identity,
  distinct from the login screen.
- **An explicit saved choice always wins**, on every page, once the
  user has manually switched themes at least once.
- The user can switch Dark ↔ Light at any time from the Navbar; the
  choice persists across sessions.

**Fixed brand chrome** — deliberately does *not* change with theme,
using the raw `--color-*` palette directly rather than the semantic
layer: the Navbar, Sidebar, Footer, the ChatWidget's own header bar
(its message body below is theme-adaptive), the login screen's brand
panel (left-hand side), and any "inverse fill" control (a gold/ivory
button always paired with dark ink text, e.g. `.btn-primary`). These
are Woodful's permanent brand presentation, not page content.

**Status colors** are re-tuned per theme, not simply reused — the
same hue family, but deepened for light-theme (AA contrast on a pale
background) versus lightened for dark-theme (contrast on a dark
surface). `--danger-text` similarly flips between themes, since a
single fixed text color cannot hit AA contrast against both a light
and a saturated-red danger fill.

Reduced motion (`prefers-reduced-motion: reduce`) is honored globally
via one rule collapsing every animation/transition duration to
effectively zero — individual components don't need their own
reduced-motion handling.

## Spacing

An 8-point-derived scale: `--space-1` (4px) through `--space-8`
(64px), doubling roughly every two steps. Use the scale tokens, not
arbitrary pixel values, for margin/padding/gap.

## Surfaces, Radius, Shadow

Three surface levels: `--background` (page), `--surface` (card/panel),
`--surface-elevated` (modals, popovers, hover state) — plus
`--surface-secondary` for an intermediate step. Radius is restrained,
not bubbly: `--radius-sm` (3px) for controls, `--radius-md` (6px) for
cards, `--radius-lg` (10px) for larger surfaces. Shadows are subtle by
default (`--shadow-sm/md/lg`), re-tuned lighter in light theme.

## Buttons

Five variants, one clear hierarchy — never more than one
`.btn-primary` per view:

- **`.btn-primary`** — gold fill, ink text. The one consequential
  action per screen (Save, Create, Confirm).
- **`.btn-secondary`** — transparent with a border, gold border on
  hover. Alternative/cancel actions.
- **`.btn-tertiary`** — fully transparent, no border. Low-emphasis
  actions.
- **`.btn-danger`** — solid fill in the theme's danger color.
  Destructive actions only.
- **`.btn-link`** — looks like a text link, behaves like a button.

Every variant has a defined `:hover`, `:focus-visible` (using the
shared `--focus-ring`), and `:disabled` (`--disabled-opacity`) state.
Icon-only buttons maintain a 44px minimum touch target.

## Inputs & Forms

Inputs share one focus treatment (`--focus-ring`) with buttons, a
defined error state (red border), and a `readonly` state (dimmed,
`not-allowed` cursor). iOS Safari's auto-zoom-on-focus is explicitly
prevented.

The shared `Form` component supports **progressive disclosure**: a
field can be marked `advanced` to sit behind a collapsed "show
advanced" toggle rather than cluttering the primary form, and
auto-expands only if a validation error lands inside it. A form
becomes a multi-step wizard *only* when a field carries a genuine
`section` grouping — a plain form with many fields stays a single flat
form; steps are for real, meaningful decision boundaries, not created
merely because a form has many database columns.

## Tables

The shared `Table` component owns: sortable/plain columns, optional
right-alignment for numeric/currency columns (`align: 'right'` per
column), row click-through, a real shimmer-based loading skeleton (not
a spinner), a calm dashed-border empty state with an optional action
button, and a distinct error state with a `Retry` action wired to the
caller's own reload function. Financial and quantity columns should
use `align: 'right'`.

## Badges

`.status-badge`: pill-shaped, uppercase, letter-spaced, theme-adaptive
semantic variants (success/warning/danger/neutral/gold/info/muted) —
never a raw hex color inline.

## Dialogs & Drawers

`Modal` (and `ConfirmDialog`, built on it) uses `motion`/
`AnimatePresence` for both entrance *and* exit — a fade + slight
scale/translate on the panel, a plain fade on the overlay — so closing
a dialog is never an instant, jarring disappearance. Full keyboard
support: focus trap while open, focus restored to the triggering
element on close, `Escape` to close.

## Motion

Global tokens: `--transition` (160ms, `cubic-bezier(0.4,0,0.2,1)`) for
ordinary hover/press/state changes; `--transition-spring` (220ms,
gentle overshoot) reserved for confirmation/entrance feedback only —
never for hover, press, or anything continuous/looping. Every page's
shared `.page` root class fades and slides in slightly on mount
(220ms), which naturally re-triggers on every route change since React
Router remounts the page component on navigation — no separate
route-transition machinery needed.

## Accessibility

- One shared `:focus-visible` treatment (box-shadow ring, not
  `outline`, so it isn't clipped by `overflow: hidden` containers) is
  applied by default to every button/link, with more specific
  component rules allowed to override it.
- `color-scheme: dark`/`light` is set to match the active theme so
  browser-native controls (date pickers, `<select>` popups, checkboxes,
  scrollbars) render in the correct native palette rather than
  defaulting to light-on-dark or dark-on-light mismatches.
- Reduced-motion is honored globally (see Theme, above).
- Minimum 44px touch targets on icon buttons and other small
  interactive controls.

## Form Philosophy

Ask for what's needed, when it's needed. Prefer a flat form with
progressive disclosure for optional/advanced fields over either (a) a
long form showing every field at once, or (b) an unnecessary multi-step
wizard. Never silently guess a value the user hasn't provided or
confirmed — if a possible match is ambiguous, present it and require
an explicit choice (e.g. "Use Existing" vs "Create New") rather than
resolving it automatically.

## AI Interaction Philosophy

Woodful's chatbot is one authoritative assistant — not a second,
competing entry point. The floating chat widget is the single, primary
AI interaction surface (a persistent top-of-app command bar was tried
and deliberately reverted for competing with this).

For any consequential (write) action, the flow is strictly:

```
user message → interpretation → ProposedAction (shown to the user for
confirmation) → user confirms → existing authenticated API →
backend authorization → business service → database
```

The assistant never writes directly to the database — every write
goes through the same authenticated, authorized endpoint a human user
would use. A response that would require executing more than one
action at once is declined outright with a plain-language explanation,
rather than silently acting on only the first and discarding the rest.

Sensitive financial values (payment amounts, prices, costs, balances,
margins, salary, and similar) never reach the external AI provider —
they are extracted and held locally, the provider receives a sanitized
message with a neutral placeholder in their place, and the real value
is restored locally once the provider's structured response returns.
The same sanitization applies to prior assistant responses carried in
conversation history, not just the current user message.
