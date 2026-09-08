# CVLab frontend migration: Vue 3 → React + Next.js

Status doc. Updated as phases land.

## Decisions

| Area | Choice | Why |
|---|---|---|
| Framework | Next.js App Router, TypeScript | Chosen by the project owner. |
| Output | `output: 'export'` — static build | The app is local-only and single-user, and the existing container serves static files against a FastAPI backend. A Node server would be new infrastructure for no gain. This keeps deployment identical to today. |
| Backend | Unchanged FastAPI on `/api` | Out of scope. Pandoc/LaTeX export and Bedrock calls stay where they are. |
| Styling | Port the existing Tailwind token system as-is | `tailwind.config.js` and `style.css` were rewritten around the CVLab navy/teal system; they move across nearly verbatim. This is the one part of the frontend that does not need redoing. |
| State | Zustand | Closest thing to Pinia's ergonomics; the `cv` store maps over with little reshaping. |
| Server state | TanStack Query | Replaces the hand-rolled loading/error/refetch flags spread through the Vue store. |
| Drag & drop | dnd-kit | Replaces `vuedraggable` (section reorder, kanban). |
| Tests | Vitest + React Testing Library | Keeps the existing runner and config knowledge; only the component-level assertions get rewritten. |
| Routing | Static routes plus a `?id=` search param for the editor | Static export cannot serve dynamic routes without `generateStaticParams`, and CV ids only exist at runtime (confirmed in Next 16's shipped docs, `static-exports.md`). So `/cv/<uuid>` becomes `/cv/?id=<uuid>`. Deep links still work; the URL shape changes. |
| Dark mode | One re-pointing of the CSS variables under `.dark` | The Vue app scattered `dark:` variants across every element. Tokens invert in one place instead, so components carry no dark-mode markup at all. |
| Location | `frontend-next/`, alongside `frontend/` | The working app keeps running until parity. Nothing is deleted until the swap in Phase 7. |

## What ports cheaply

- `src/types/cv.ts` and `src/types/applicationTracker.ts` are already TypeScript — they move as-is.
- `src/services/sectionService.ts` and `applicationTrackerService.ts` are already TypeScript and framework-free.
- The Tailwind design system (tokens, `.btn`, `.card`, `.input`, `.chip`, rail labels).
- All backend contracts: `cvAPI`, `exportAPI`, `templateAPI`, `llmAPI`, `typographyAPI`.

## What has to be rewritten

- 55 `.vue` components → React function components.
- 8 composables → hooks.
- The Pinia `cv` store (~900 lines) → Zustand slices.
- 23 test files (~11.6k lines).

## Fixing the thing that started this

The Vue `CVEditor.vue` renders the desktop and narrow layouts as **two separate trees** hidden by CSS — duplicate component instances, duplicate API calls, duplicate state, and the missing `min-h-0` that made the page bottom unreachable below 1024px. The React editor is built as **one tree** with responsive layout, so that class of bug cannot recur. This is a hard requirement of Phase 3, not a nice-to-have.

Two other known issues to resolve while rebuilding, not to reproduce:

1. Section editing is inline on desktop but a modal on narrow — two interaction models for one task. Pick one.
2. Field styles were duplicated privately in 17 components, overriding the design system. In React they come from shared primitives.

## Phases

Each phase is independently reviewable and leaves both apps working.

- [x] **Phase 0 — Foundation.** Scaffold, Tailwind system port, typed API client, shared types.
- [x] **Phase 1 — App shell.** Routing, top bar, theme (light/dark/auto, no-flash), toasts.
- [x] **Phase 2 — CV list.** Landing screen, create, delete, Markdown import, live against the backend.
- [x] **Phase 3 — CV editor.** Rail with dnd-kit reorder, six section editors, live preview, single responsive tree.
- [x] **Phase 4 — Tool panels.** Export (formats, history, download), Styling (typography templates), Job Match (suitability analysis).
- [x] **Phase 5 — Application tracker.** Kanban with dnd-kit, optimistic stage moves, detail dialog, create and delete.
- [x] **Phase 6 — Remaining screens.** Backup/restore (typed-filename confirm on restore), LLM settings with consent.
- [~] **Phase 7 — Cutover.** Tests ported, parity part-verified, cutover NOT executed (see below).

## Trap found in Phase 3

`.gitignore` carried an unanchored `cv/` (intended for a root folder of personal
files). It matched **any** directory named `cv`, including
`frontend-next/src/app/cv/` — so the editor route was invisible to git *and* to
Tailwind v4's source scanner, which respects `.gitignore`. The symptom was
`lg:flex`, `xl:flex`, `w-rail` and `h-topbar` silently never being generated, so
the rail and preview panes never appeared. Both rules are now anchored (`/cv/`,
`/archive/`).

## Wrong request body found while porting

`PATCH /api/applications/{id}/stage` takes `{ new_stage }`, not `{ stage }` —
sending the wrong field returns 422. The ported `StageChangeRequest` type had it
right all along, so the call now uses `satisfies StageChangeRequest` and the
compiler enforces the contract.

## Wrong routes found while porting

The Vue client called `GET /templates` and `POST /export` with a JSON body.
Neither exists: the backend serves `GET /api/export/templates` and
`POST /api/export/{cv_id}/{format}`. Routes were re-derived from the running
service's OpenAPI document rather than ported from the old client, so the React
export panel talks to endpoints that are actually there.

## Dev servers

The backend container allows CORS from `localhost:3000` and `:5173` only
(`backend/app/main.py`), so the Next dev server runs on **3000**. Running both
frontends at once needs `http://localhost:3001` added to that allowlist and the
container restarted — not done, since it is a dev-only convenience.

## Test port: what moved and what did not

The Vue suite was 23 files / ~11.6k lines. It was not ported line for line,
because a large part of it asserted Vue-specific implementation rather than
product behaviour. Current React suite: 6 files, 49 tests, 1.3s.

**Ported as behaviour** (the logic was worth keeping, the axios coupling was not):

- `sectionService.ts` utils -> `lib/sections.ts` — default titles, custom title
  validation, order validation, sorting, visibility, core-section rules.
- The two near-identical `formatErrorMessage`/`retryRequest` helpers ->
  `lib/errors.ts`, now reading `ApiError` instead of `error.response`. One
  deliberate change: client errors (4xx) are no longer retried, since repeating
  a request the server already rejected as invalid just wastes time.
- Draft/live-preview behaviour -> `useSectionForm` tests, which cover what the
  Vue app had no tests for at all.

**Deliberately not ported:**

- `NavigationStatePreservation` (686 lines), `NavigationGuards`, `Navigation`,
  `App.test` — these test vue-router internals and Vue lifecycle. The equivalent
  behaviour is now the App Router's, and testing a framework's own routing is
  not this project's job.
- `responsiveBehavior.test.ts` (825 lines) — asserts specific Tailwind class
  strings per breakpoint. It would have passed happily while the editor's bottom
  was unreachable below 1024px, which is exactly the bug it should have caught.
  Layout is verified in a real browser at real widths instead.
- Component tests tied to the old markup (`sectionList`, `addSectionModal`,
  `kanbanBoard`, ...). The components were redesigned; asserting the old DOM
  would be asserting the thing we replaced.

**Still owed:** RTL coverage for `SectionRail`, `KanbanBoard` and the editor
page, and a port of the two fast-check property suites
(`applicationCard.property`, `kanbanStageOrganization.property`) — those test
real invariants and deserve to survive.

Note: the Vue suite has had **16 failing tests across 6 files** for the whole of
this work — that was its state before any of it started, not a regression.

## Cutover: image done and verified, `frontend/` still in place

Done and proven by building and running the real image:

- `Dockerfile` and `Dockerfile.minimal`: `node:18-slim` -> `node:20-slim`
  (Next 16 needs >= 20.9), build paths `frontend/` -> `frontend-next/`,
  and the artefact copy `dist` -> `out`.
- `.dockerignore`: added `.next` and `out` so build caches stay out of context.
- `backend/app/main.py`: the static serving assumed Vite's layout and broke on
  Next's in two ways. It mounted `/assets` unconditionally — a directory that
  does not exist in a Next export, and `StaticFiles` raises at startup on a
  missing directory, so the backend would not have booted. And the SPA catch-all
  did not exclude `_next`, so every JavaScript chunk request was answered with
  `index.html` and the app would never have started. Both fixed, and written to
  work with either layout so the Vue build still serves correctly.
- The catch-all now prefers a per-route document (`cv/index.html`) when the
  static export provides one, falling back to the root document.

Verified in a container built from this Dockerfile: `/`, `/cv/`, `/applications/`
and `/api/cvs` all 200; `/cv/` and `/applications/` are distinct documents;
JS chunks return `text/javascript`; unknown routes fall back to the root
document for the client router; `no-store` still set on documents.

**Not done:** `frontend/` is still present and untouched. It must not be deleted
while this work is uncommitted — the design-system changes made to the Vue app
earlier in this effort are not in git yet. The compose `dev` profile and
`quick-rebuild.sh` also still point at `frontend/`, deliberately: during the
transition that is the way to run the old app for comparison.

## Parity checklist for cutover

Do not retire `frontend/` until all of these hold:

- [x] Create, edit, save, delete a CV
- [x] Markdown import produces the same sections as today (verified: identical section shape, 4 roles, 18 skills, 8 achievements on the first role)
- [ ] All six section editor types round-trip content unchanged — experience verified, five to go
- [x] Section reorder, visibility toggle, add and remove
- [x] Live preview tracks typing
- [ ] Export to PDF, DOCX and TXT produces byte-comparable files — NOT verified, writes files
- [ ] Typography templates apply and persist — NOT verified, mutates CV styling
- [ ] Job match and ATS scoring — NOT verified, costs a provider call and AI is currently disabled
- [x] Application tracker board, cards and detail modal (create, drag between stages, edit, delete)
- [x] Backup create/list/download/delete verified; **restore NOT verified** — it overwrites live data
- [x] The editor is usable at narrow widths with the bottom of every form reachable (verified at 900x800: 3504px of content scrolling in a 708px pane, Save reachable)
