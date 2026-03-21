---
name: frontend-development
description: >
  Use when writing, modifying, or reviewing any code in the frontend/ directory.
  Covers React components, TypeScript types, Plotly chart rendering, API client,
  Tailwind styling, accessibility (WCAG 2.1 AA), responsive design, error handling,
  and Vitest testing. Enforces the project's component patterns, type safety, and
  correctness. Always use alongside the testing-discipline skill. Note: visual
  design decisions (colors, spacing, layout aesthetics) are handled by a separate
  frontend-design skill if present — this skill covers architecture, patterns, and
  correctness.
version: 1.0.0
languages: [typescript]
---

# Frontend Development — Dry Data

## Before You Write Any Code

1. Read `CLAUDE.md` at the project root for conventions.
2. Read the `testing-discipline` skill. Apply TDD for new components.
3. Run existing checks: `cd frontend && npm run typecheck && npm run lint`
4. Check `types/api.ts` — understand the contract with the backend.

---

## Project Structure

```
frontend/src/
├── main.tsx              # Entry point (don't touch unless adding providers)
├── App.tsx               # Shell: header, tab nav, route to views
├── index.css             # Tailwind directives only
├── types/
│   ├── api.ts            # Types matching backend Pydantic models
│   └── plotly.d.ts       # Plotly type declarations
├── api/
│   └── client.ts         # Typed fetch wrapper (queryData, listDatasets, etc.)
├── components/           # UI components
│   ├── ChatInterface.tsx
│   ├── ChartRenderer.tsx
│   └── DatasetBrowser.tsx
├── hooks/                # Custom React hooks
├── lib/                  # Pure utility functions (no React, no DOM)
└── test/                 # Test setup, MSW handlers, shared helpers
    ├── setup.ts
    └── mocks/
        └── handlers.ts
```

---

## Type Safety

**No implicit `any`. Ever.**

### Strict Mode Is On

`tsconfig.json` has `strict: true` and `noUncheckedIndexedAccess: true`.
This means:

- No implicit `any`
- Array indexing returns `T | undefined` — you must null-check
- All function parameters need types

### No `any`

```typescript
// BAD
function processData(data: any) { ... }

// GOOD
function processData(data: QueryResponse) { ... }

// GOOD — when the shape genuinely varies, use unknown and narrow
function processData(data: unknown) {
  if (isQueryResponse(data)) { ... }
}
```

### API Types Are the Contract

The interfaces in `types/api.ts` must exactly match the backend Pydantic models
in `backend/src/dry_data/models/`. When the backend changes a model, update
`types/api.ts` in the same commit.

Key types:

- `QueryRequest` / `QueryResponse` — chat interaction
- `PlotlySpec` — chart data from the LLM (`Plotly.Data[]` + `Partial<Plotly.Layout>`)
- `ChatMessage` — frontend chat history
- `DatasetInfo` / `ColumnInfo` — dataset browser

### `ApiError` Is a Class

`ApiError` must be a class extending `Error` so that `instanceof` checks work
at runtime. Never use `interface` + object literal for errors.

---

## Component Conventions

### Functional Components Only

No class components. No `React.FC` — just named function exports:

```typescript
// GOOD
export function ChatInterface() { ... }
export function MessageBubble({ message }: MessageBubbleProps) { ... }

// BAD
const ChatInterface: React.FC = () => { ... }
```

### Props

Define props as a named interface directly above the component. Provide
defaults for optional props via destructuring:

```typescript
interface MessageBubbleProps {
  message: ChatMessage;
  isLoading?: boolean;
}

export function MessageBubble({ message, isLoading = false }: MessageBubbleProps) {
  ...
}
```

### Component Size

If a component exceeds ~150 lines, extract sub-components or a custom hook.
Signs you need to split:

- Multiple `useState` calls managing related but distinct concerns
- Conditional rendering with complex branches
- A return statement longer than 60 lines of JSX

### File Organization

Each component file should follow this order:

1. Imports
2. Types/interfaces
3. Constants
4. Helper functions (if small; otherwise extract to `lib/`)
5. Component function
6. Sub-components (if small and only used by the parent)

---

## Error Handling

Three levels. Don't mix them.

| Level      | Mechanism                | Use for                                    |
| ---------- | ------------------------ | ------------------------------------------ |
| Global     | Error boundary component | Unexpected crashes, render errors          |
| Component  | `try/catch` + state      | Async operations (API calls, data loading) |
| Form input | Inline validation state  | Field-level validation feedback            |

### The Standard Async Pattern

**Every component that fetches data must follow this shape.** Claude: do not
skip the loading or error states. All three states (loading, error, data) are
required.

```typescript
export function DatasetBrowser() {
  const [data, setData] = useState<DatasetInfo[] | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setIsLoading(true);
      setError(null);
      try {
        const result = await listDatasets();
        if (!cancelled) setData(result);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load data");
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, []);

  if (isLoading) return <LoadingSpinner />;
  if (error) return <div role="alert">{error}</div>;
  if (!data || data.length === 0) return <p>No datasets available.</p>;

  return (/* render data */);
}
```

**Key rules:**

- `cancelled` flag prevents state updates on unmounted components.
- Loading state is true by default (not false then flipped).
- Error messages are user-friendly, never raw exception text.
- Empty state is handled explicitly (`data.length === 0`).

### Error Handling in Chat

Chat errors should appear as assistant messages, not crash the UI:

```typescript
} catch {
  setMessages(prev => [...prev, {
    id: crypto.randomUUID(),
    role: "assistant",
    content: "Sorry, something went wrong. Try rephrasing your question.",
    chart: null,
    sql: null,
    timestamp: new Date(),
  }]);
}
```

---

## API Client

### All API Calls Go Through `api/client.ts`

Never use `fetch()` directly in components. The client handles:

- Base URL (proxied in dev via Vite config)
- Content-Type headers
- Error wrapping (`ApiError` class with status code)
- Type-safe return values

### `ApiError` for Error Typing

```typescript
class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
```

Use `instanceof ApiError` in catch blocks to distinguish network errors
from API errors and show appropriate messages.

---

## State Management

### React State Only (v1)

Use `useState` and `useReducer`. No external state libraries for v1.

If state logic gets complex, extract into a custom hook:

```typescript
// hooks/useChat.ts
export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  async function sendQuestion(question: string) { ... }

  return { messages, isLoading, sendQuestion };
}
```

### Decision guide

- **Only used in this component?** → `useState` in the component
- **Shared across components?** → Lift state to common parent or use context
- **Complex state transitions?** → `useReducer`
- **Fetch data on mount?** → `useEffect` with the cancelled flag pattern above

### No localStorage

Chat history lives in memory only. If persistence is needed later, discuss
first — this is an alcohol-related topic and there are privacy considerations.

---

## Styling with Tailwind

### Tailwind Only

No CSS modules, no styled-components, no inline `style` objects (except where
Plotly requires them). All styling via Tailwind utility classes in JSX.

```typescript
// GOOD
<div className="rounded-xl border border-gray-200 bg-white px-5 py-3">

// BAD
<div style={{ borderRadius: 12, border: '1px solid #e5e7eb' }}>
```

### The Brand Color Scale

Defined in `tailwind.config.js` as `brand-50` through `brand-900`. Use for
primary actions, links, and active states. Gray for neutral UI.

### Dark Mode

Not required for v1, but write classes that won't fight it. Avoid hardcoding
`text-gray-900` on elements that also have hardcoded `bg-white`.

---

## Responsive Design (Mobile-First)

Test at **375px, 768px, 1440px**. No horizontal overflow at any width.

### Rules

- Start with mobile layout, add breakpoints for larger screens (`sm:`, `md:`, `lg:`)
- Use `flex flex-col sm:flex-row` for layouts that stack on mobile
- Never use fixed widths (`w-[1200px]`). Use `w-full max-w-full`
- Container padding: `px-4 sm:px-6 lg:px-8`
- Minimum font size: 14px on mobile (`text-sm`), 16px on tablet+
- The chat interface must be fully usable at 375px — starter cards stack
  to a single column, input area stays anchored at bottom

### Breakpoint reference

| Breakpoint | Width   | Typical device             |
| ---------- | ------- | -------------------------- |
| Default    | 0-639px | Phone                      |
| `sm:`      | 640px+  | Large phone / small tablet |
| `md:`      | 768px+  | Tablet                     |
| `lg:`      | 1024px+ | Desktop                    |

---

## Accessibility (WCAG 2.1 AA)

These are not optional. Every component, every time.

### Non-negotiable rules

- **Semantic HTML:** Use `<nav>`, `<main>`, `<section>`, `<button>` — not
  `<div>` with `onClick`. A clickable `<div>` is never acceptable when
  `<button>` exists.
- **Labels:** Every `<input>` has a `<label htmlFor="...">` or `aria-label`.
  Icon-only buttons must have `aria-label`.
- **Focus indicators:** Never `outline-none` without a visible replacement.
  Use `focus-visible:ring-2 focus-visible:ring-brand-400`.
- **Touch targets:** 44×44px minimum on all interactive elements. This
  includes buttons, links, clickable cards, and form inputs. Use `min-h-11
min-w-11` (44px) as a baseline.
- **Color contrast:** 4.5:1 for normal text, 3:1 for large text (18px+).
  Test with browser dev tools.
- **Dynamic content:** `role="alert"` + `aria-live="polite"` on messages
  that appear or change (error messages, loading→content transitions).
- **Expandable content:** `aria-expanded` + `aria-controls` on toggles.
- **Loading states:** `aria-busy="true"` on the container, `role="status"`
  on the spinner. Screen readers should announce "loading" and "loaded."
- **Keyboard navigation:** All interactive elements reachable via Tab,
  activated via Enter/Space. Tab order matches visual order.

### Specific to This App

- Chat input: `aria-label="Ask a question about alcohol trends"`
- Send button: `aria-label="Send"` (icon-only)
- Charts: wrap in a `div` with `role="img"` and `aria-label` describing
  the chart type and title (e.g., "Bar chart: Alcohol consumption by country")
- SQL disclosure: use `<details>/<summary>` (already done)
- Starter question cards: keyboard-focusable `<button>` elements, not `<div>`
- Dataset browser expand/collapse: `aria-expanded` on the trigger

---

## Transitions & Animations

### When to use

CSS transitions for hover/focus effects and state changes. React for
mount/unmount transitions (conditional rendering with fade).

### Duration guidelines

| Type                 | Duration      | Example                   |
| -------------------- | ------------- | ------------------------- |
| Hover/focus feedback | 150ms         | Button hover color change |
| Content entering     | 200ms         | Chat message appearing    |
| Content exiting      | 100-150ms     | Error dismissal           |
| Chart rendering      | No transition | Plotly handles its own    |

Never exceed 300ms. Sluggish transitions feel broken, not polished.

### Respect reduced motion

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

Add this to `index.css`. Users who've set this preference get instant
state changes instead of animations.

---

## Plotly Integration

### ChartRenderer Is the Single Rendering Point

All Plotly charts go through `components/ChartRenderer.tsx`. Never import
`react-plotly.js` directly in other components.

### The LLM Returns the Spec

The backend returns a complete Plotly figure spec (`data` + `layout`).
`ChartRenderer` merges the LLM's layout with `BASE_LAYOUT` defaults (fonts,
margins, transparent background, gridline color, color palette).

### Adding Chart Type Support

Plotly handles all trace types natively — `choropleth`, `histogram`, `box`,
`heatmap`, etc. No frontend changes needed for new chart types. Just ensure
`BASE_LAYOUT` has sensible defaults for any new layout properties.

### Chart Accessibility

Wrap every rendered chart in:

```typescript
<div
  role="img"
  aria-label={`${spec.data[0]?.type ?? "Chart"}: ${spec.layout?.title ?? "Data visualization"}`}
>
  <Plot ... />
</div>
```

### Handling Large Data

Backend should aggregate before sending. The Plotly spec in the API response
should contain pre-aggregated data, not raw rows.

---

## Security

- **No `dangerouslySetInnerHTML` without sanitization.** If you must render
  HTML (e.g., from markdown in narrative responses), use DOMPurify.
  `dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(content) }}`.
  Better yet, use a markdown renderer that doesn't use `innerHTML`.
- **No secrets in frontend code.** API keys stay in the backend. Only
  `VITE_` prefixed env vars are available in the frontend bundle.
- **API client uses relative URLs only** (`/api/query`, not
  `https://myserver.com/api/query`). The Vite proxy handles routing in dev.

---

## Testing

Follow the **testing-discipline** skill for philosophy. Frontend-specific:

### Setup

- **Vitest** as test runner
- **@testing-library/react** for component tests
- **jsdom** as DOM environment
- **msw** (Mock Service Worker) for API mocking

### Vitest Config

```typescript
// vitest.config.ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
```

### Test Setup

```typescript
// src/test/setup.ts
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});
```

### MSW for API Mocking

```typescript
// src/test/mocks/handlers.ts
import { http, HttpResponse } from "msw";
import type { QueryResponse } from "@/types/api";

const mockQueryResponse: QueryResponse = {
  question: "test",
  narrative: "Here are the results.",
  sql: "SELECT 1",
  chart: null,
  error: null,
};

export const handlers = [
  http.post("/api/query", () => HttpResponse.json(mockQueryResponse)),
  http.get("/api/datasets", () => HttpResponse.json([])),
  http.get("/api/health", () => HttpResponse.json({ status: "ok" })),
];
```

### Test File Location

Co-locate test files with the code they test:

```
components/
├── ChatInterface.tsx
├── ChatInterface.test.tsx
├── ChartRenderer.tsx
├── ChartRenderer.test.tsx
```

### What to Test

- **Components:** Render, interact, assert on DOM. Use `getByRole`,
  `getByLabelText`, `getByText` — not `getByTestId`.
- **Hooks:** Test via a wrapper component or `renderHook`.
- **API client:** Mock fetch via MSW, test error handling and type safety.
- **Utils/lib:** No mocks, just input → output.
- **No snapshot tests** on components. Test specific behaviors.
- **Every test** must have a `// CATCHES:` comment per the testing-discipline skill.

---

## Checklist: Every Frontend Change

- [ ] All types explicit (no implicit `any`)
- [ ] Props typed with interface + destructuring defaults
- [ ] Error handling at appropriate level (global/component/form)
- [ ] Loading states on all async operations (with `aria-busy`)
- [ ] Empty states handled explicitly
- [ ] Semantic HTML with ARIA attributes
- [ ] Touch targets ≥ 44×44px on all interactive elements
- [ ] Focus indicators visible on keyboard navigation
- [ ] Tested at 375px with no horizontal overflow
- [ ] `dangerouslySetInnerHTML` sanitized with DOMPurify (or avoided)
- [ ] API types match backend Pydantic models
- [ ] `// CATCHES:` comment on every test

---

## After Every Change

```bash
cd frontend
npm run typecheck
npm run lint
npx vitest run
```

All three must pass before considering the work done.
