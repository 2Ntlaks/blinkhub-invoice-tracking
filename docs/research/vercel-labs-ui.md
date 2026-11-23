# Research: can vercel-labs/ui help this project?

Checked on 2026-11-22 from the GitHub repo, its docs source and the npm registry.

## 1. What it is

The repo is public and active. It is **UI SDK**, described as "a library of behaviors for agents
to build the next generation of user interfaces". It is not a styled component kit.

- It handles the hard, invisible parts of UI: keyboard navigation, focus, selection, closing
  popups, drag and drop, and the ARIA attributes screen readers need.
- Packages: `@ui-sdk/core` (the behaviours) plus adapters `@ui-sdk/react`, `vue`, `svelte`,
  `solid` and `web`. It also ships an agent "skill" so coding agents can write components with it.
- Components are **unstyled** (also called headless). You add every look yourself with CSS or
  Tailwind, or import an optional starter stylesheet `@ui-sdk/core/web.css`.
- React components include Button, Dialog, Alert Dialog, Field, Input, Select, Tabs, Toast,
  Tooltip, Timeline, Pagination, Date Picker, Number Input and more. There is **no Table, Card,
  Badge or Chart**.
- Maturity: created 26 October 2026 (under four weeks old), about 716 commits, about 6,500 stars,
  last push today. Version `0.1.0-beta.14` (npm `latest` is `beta.13`). The README says APIs
  "may change before general availability". Recent commits are mostly focus and popup bug fixes.

## 2. Compatibility with our stack

- **React**: needs React 19 and React DOM 19 or newer, plus `@types/react` 19.2.10 or newer.
  A fresh Vite React template uses React 19, so this is fine if we start clean.
- **Vite**: supported directly. The install guide shows the Vite setup (import the CSS in
  `main.tsx`). It does **not** require Next.js or React Server Components.
- **TypeScript**: fully typed.
- **Tailwind**: works with it through `data-slot` and state attributes (for example
  `data-copied:bg-neutral-900`). The docs use Tailwind v4 syntax (`@import "tailwindcss"` and
  CSS layers). With Tailwind v3 the variants would need extra configuration.

## 3. Mapping to our screens

| Screen | Useful UI SDK part | Effect |
|---|---|---|
| Role switcher | Select or Segmented Control | Replaces a shadcn Select. No time saved. |
| Invoice list with badges | Pagination only | Table and badges are still plain Tailwind. |
| Invoice detail, audit timeline | **Timeline** | The one real gain: an accessible event list with arrow keys. But a styled `<ol>` takes 15 minutes. |
| Supplier submit form errors | Field, Input, Number Input, Date Picker | Wires labels and error messages to inputs for screen readers. Same job as shadcn Form. |
| Approve / reject / pay | Alert Dialog, Toast | Confirm before reject or pay, toast on success. Same as shadcn. |
| Flag review | Dialog, Textarea | Same as shadcn. |
| Dashboard | Nothing | KPI tiles and charts stay Tailwind and Recharts. |

## 4. Compared with plain Tailwind and established libraries for a time-boxed prototype

- **Setup time**: UI SDK gives behaviour only, so every component still needs styling by hand
  (or the generic `web.css`), which adds overhead to a short prototype build.
- **Risk**: UI SDK is a four-week-old beta with daily fixes and a changing API. Hand-built
  Tailwind components (or mature libraries built on Radix/Base UI) are predictable and carry
  less demo risk.
- **What it adds**: strong accessibility, a ready Timeline and an "agent-friendly" story.
  None is a case-study requirement.

## 5. Licence

Apache License 2.0. Free to use commercially. If we copy its source code into our repo we must
keep the licence text and mark our changes. Using it from npm needs no attribution in the app.
The beta terms also apply while it is in beta. There is no NOTICE file.

## Decision

**Not adopted for the prototype; kept as a future accessibility option.** The prototype uses
small hand-built Tailwind components in [`frontend/src/components/ui.tsx`](../../frontend/src/components/ui.tsx)
with Recharts for charts and a simple styled list for the audit timeline. Once UI SDK leaves beta,
its Timeline, Field, and Alert Dialog behaviours could replace the hand-built versions to improve
keyboard and screen-reader accessibility for suppliers and finance staff.
