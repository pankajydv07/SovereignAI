---
trigger: glob
globs: apps/desktop/src/**/*.ts,apps/desktop/src/**/*.tsx
description: TypeScript and React standards for the desktop UI.
---

# TypeScript / React — `apps/desktop/src/`

`strict: true`, `tsc --noEmit` clean. Function components with hooks.

## `any` is banned

❌ **Bad**
```tsx
function ToolCard({ call }: { call: any }) {
  return <div>{call.name}</div>;
}
```

✅ **Good** — types come from the generated protocol
```tsx
import type { ToolCall } from "@/protocol";

function ToolCard({ call }: { call: ToolCall }) {
  return <div className="font-mono text-[11px]">{call.name}</div>;
}
```

Use `unknown` and narrow when a type is genuinely unknown. Every `as` cast carries a comment justifying it.

## Validate at the IPC seam

The core is trusted, but a schema mismatch must fail loudly at the boundary rather than corrupting state three renders later.

✅
```tsx
const parsed = SessionUpdateSchema.safeParse(rawEvent);
if (!parsed.success) {
  logProtocolError("session_update", parsed.error);
  return;
}
applyUpdate(parsed.data);
```

## No business logic in components

❌ **Bad** — a policy decision living in the UI
```tsx
const needsApproval = call.name === "terminal_exec" || call.name.startsWith("fs_write");
```

✅ **Good** — the core decided; the UI renders the decision
```tsx
const needsApproval = call.permission === "ask";
```

## No `useEffect` for data fetching

❌ `useEffect(() => { fetchSessions().then(setSessions); }, []);`
✅ `const { data: sessions } = useQuery({ queryKey: ["sessions", projectId], queryFn: fetchSessions });`

State: Zustand for app state, TanStack Query for async.

## Styling: tokens only

❌ **Bad** — arbitrary values defeat the design system
```tsx
<div className="text-[13.5px] rounded-[7px] p-[18px] shadow-lg">
```

✅ **Good**
```tsx
<div className="text-body rounded-sm p-4 border border-border">
```

If a token does not exist, extend `packages/design-tokens` — do not inline a one-off value.

## Component size

One component per file. Over ~150 lines, decompose. A component rendering a list, its empty state, its loading state and its row internals is four components.

## Every interactive surface implements five states

Default, empty, loading (**with a named stage**), error (**with a working remedy button**), degraded. A component that only renders the happy path is not done.

❌ `{isLoading && <Spinner />}`
✅ `{isLoading && <StageIndicator label={stage} elapsedMs={elapsed} />}`
