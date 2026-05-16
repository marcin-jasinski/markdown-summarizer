## Components

### Single Responsibility
Each component should do one thing well.

### Reusability
Design components to work across different contexts with configurable props.

### Composability
Build complex UIs by combining smaller components rather than creating monoliths.

### Clear Interface
Define explicit, documented props with sensible defaults.

### Encapsulation
Keep implementation details private; expose only what's necessary.

### Consistent Naming
Use descriptive names that indicate purpose and follow team conventions.

### Local State
Keep state as close to where it's used as possible; lift only when needed.

### Minimal Props
If a component needs many props, consider composition or splitting it.

### Documentation
Document usage, props, and examples to help team adoption.

---

## Angular-Specific Component Rules

- **Always `standalone: true`** — no NgModule declarations
- **Use `inject()` not constructor** for dependency injection
- **Prefer `signal()`/`computed()`** for local state over class properties
- **Lazy-load pages** via `loadComponent()` in `app.routes.ts`
- **Keep component SCSS lean** — production build enforces 4kB warning / 8kB hard error per component style
- **Initial bundle budget**: 500kB warning / 1MB error — avoid importing heavy libraries in eagerly-loaded code
