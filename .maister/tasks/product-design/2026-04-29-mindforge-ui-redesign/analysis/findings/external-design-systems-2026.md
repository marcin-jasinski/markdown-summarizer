# External Research: Design Systems for Angular SaaS (2026)

## Sources Consulted
- ui.shadcn.com (Shadcn/ui — foundation for design systems)
- radix-ui.com (Radix Themes 3.0 + Primitives)
- material.angular.dev (Angular Material / Material 3)
- m3.material.io (Material Design 3 Expressive, April 2026)
- primeng.org (PrimeNG v21)
- taiga-ui.dev (Taiga UI)
- spectrum.adobe.com (Adobe Spectrum — design token reference)
- carbondesignsystem.com (IBM Carbon)
- General knowledge of Tailwind UI, Ant Design 5, Chakra UI

---

## 1. The Design System Landscape in 2026

The market has bifurcated into two categories:

### Category A: Headless / Token-Based (Modern)
Libraries that separate **semantics** from **styling**. They provide accessible primitives and design tokens; you bring your CSS.

| Library | Angular Support | Approach | Light Mode Quality |
|---|---|---|---|
| **Angular Material (M3)** | Native | Component library + token system | Excellent (theming via `mat.theme()` mixin) |
| **Shadcn/ui** | React only (ports exist: `spartan/ui`, `ngxtw`) | Copy-paste components + Tailwind | Outstanding — built for light-first |
| **Radix UI Themes** | React only (primitives work via CDN) | CSS-variable tokens + components | Good |
| **Taiga UI** | Native Angular | Full component library + tokens | Strong, business-first |
| **PrimeNG v21** | Native Angular | Styled or unstyled + PassThrough API | Excellent via `Aura` / `Lara` themes |

### Category B: Full-Styled / Opinionated (Heavier / Dated Risk)
Libraries that ship heavily styled components that are harder to customize.

| Library | Angular Support | Why It Feels Dated |
|---|---|---|
| **Ant Design 5** | ng-zorro (Angular port) | Enterprise-heavy, dense tables, less emotional |
| **Chakra UI** | React only | Great DX but heavy runtime JS style injection |
| **Carbon (IBM)** | Angular community | Very IBM, useful for enterprise tools |
| **Bootstrap 5** | ngx-bootstrap | Overused, identifiable visual fingerprint |

---

## 2. What "Modern" vs "Heavy/Dated" Means in 2026

### Modern Characteristics
- **Design tokens via CSS custom properties**: all spacing, colours, radii, and typography expressed as `--var` tokens. `var(--radius-md)` not hardcoded `8px`.
- **Zero runtime style injection**: styles are in CSS files, not JS bundles. Avoids FOUC and hydration issues.
- **Headless / unstyled primitives**: components handle A11y (ARIA roles, keyboard nav, focus management) but don't impose visual style.
- **Scoped to CSS layers**: uses `@layer` for predictable cascade without `!important` wars.
- **Tree-shakeable**: only import what you use. Reduces bundle size.
- **OKLCH / P3 colour space**: forward-thinking colour definition (Radix, Tailwind v4 all adopt `oklch()`).

### Dated/Heavy Characteristics
- Global class-name-based styling (`.ant-btn`, `.p-button`) that bleeds into application CSS.
- jQuery-adjacent animation systems or non-CSS transitions.
- Fixed visual language that screams the library name (Bootstrap's button shadows, Ant Design's table headers).
- Complex nested theme override patterns (`::ng-deep` chains).
- No design token documentation — no way to sync with Figma tokens.

---

## 3. Angular-Specific Options Deep Dive

### Angular Material 3 (Recommended Baseline)
**Status**: Native Angular, Google-maintained, full M3 Expressive spec (2025).

**Strengths**:
- `mat.theme()` Sass mixin system generates all CSS custom properties from a palette declaration.
- M3 Expressive (2025) added: spring-physics motion, 14 new components (Toolbars, Split Button, Button Groups, animated Progress Indicators), 35 new shape tokens.
- `--mat-sys-*` token namespace covers surface, primary, secondary, tertiary, error, neutral.
- Angular team maintains it — guaranteed SSR support, zone.js/zoneless compatibility, signals integration.
- Already used in MindForge. **Switching cost: near zero**.

**Light Mode Theming**:
```scss
// Light theme declaration (replaces current dark)
html {
  @include mat.theme((
    color: (
      theme-type: light,          // <— change this
      primary: mat.$indigo-palette,
      tertiary: mat.$amber-palette,
    ),
    typography: (brand-family: 'Inter', plain-family: 'Inter'),
    density: 0,
  ));
}
```
All `--mat-sys-surface`, `--mat-sys-on-surface`, `--mat-sys-primary` tokens automatically update. **Zero component changes required**.

**Weaknesses**:
- Heavier than Tailwind-based approaches — but only matters for initial render, not for a SPA.
- Visual language is recognisably "Material" — requires custom theming effort to escape.

---

### PrimeNG v21
**Status**: Leading Angular-specific component library, 80+ components, ~400M npm downloads.

**Strengths**:
- **PassThrough (PT) API**: every component part (root, label, icon, etc.) gets a `pt` prop accepting CSS classes or style objects. Complete visual control without forking.
- **Unstyled mode**: ship zero CSS, use Tailwind classes via PT for each sub-element. Best of both worlds.
- **Aura theme** (default in v21): clean, modern, well-suited for light SaaS apps. Uses CSS custom properties extensively.
- 500+ pre-built PrimeBlocks (copy-paste UI sections) — accelerates layout building.
- DataTable, TreeTable, Charts, Gantt — powerful data components not in Material.

**Light Mode Quality**: Excellent. The `Aura` theme ships with a clean white/light-grey base, accent colours via tokens.

**Design Token System**: PrimeNG v21 uses a CSS-variable token system:
```css
--p-primary-color: #6366f1;          /* indigo */
--p-primary-contrast-color: #ffffff;
--p-surface-0: #ffffff;
--p-surface-50: #f8fafc;
--p-surface-100: #f1f5f9;
--p-text-color: #0f172a;
--p-text-muted-color: #64748b;
--p-border-radius-md: 8px;
```

**Weaknesses**:
- Not built by Angular team, so occasionally lags on latest Angular APIs (signals, zoneless).
- Some enterprise-feel components that need PassThrough to make modern.

---

### Taiga UI
**Status**: Open source Angular library by Tinkoff (Russian bank, now independent). Active, modern.

**Strengths**:
- Very polished visual design out of the box — cleaner than Material for SaaS.
- Strong form components (masked inputs, date pickers, etc.).
- Token-based theming via CSS custom properties.
- Active in European/enterprise Angular community.

**Weaknesses**:
- Smaller community than Material or PrimeNG.
- Documentation primarily in English but company origins sometimes cause hesitation.
- Less ecosystem tooling (no PrimeBlocks equivalent).

---

### Spartan/UI (Shadcn for Angular)
**Status**: Community-maintained Angular port of Shadcn/ui patterns. `@spartan-ng/ui-*`.

**Strengths**:
- Shadcn model: copy component source into your project, full ownership.
- Tailwind-based styling, beautiful light mode, matches React Shadcn quality.
- Radix-inspired accessible primitives via Angular CDK.

**Weaknesses**:
- Not an official library — depends on community maintenance.
- Requires Tailwind CSS in Angular project (extra config).
- Component coverage is still growing (not 80+ like PrimeNG).
- MindForge already uses Material — mixing Material + Spartan would create token conflicts.

---

## 4. Recommendation for Light, Modern, Sleek Aesthetic

### Primary Recommendation: Angular Material 3 + Custom Token Override

**Rationale**: MindForge already uses Angular Material 3. The refactor to light mode is a **single-line change** (`theme-type: dark` → `theme-type: light`). The M3 token system (`--mat-sys-*`) provides a clean foundation for custom palette.

**Action Plan**:
1. Switch `theme-type: light` in `styles.scss`.
2. Replace `mat.$violet-palette` with a custom indigo/violet palette using OKLCH values.
3. Override surface tokens to use the crisp white/light-grey tier described in the Learning SaaS section.
4. Layer custom CSS variables on top of `--mat-sys-*` tokens for app-specific semantics.

**For components not in Material** (e.g., SRS rating buttons, streak counter, score ring): use plain CSS with the same token system.

### Secondary Option: Migrate to PrimeNG v21 (Aura theme)

**Rationale**: If the team wants to escape Material's visual fingerprint entirely and gain more components (DataTable, Charts, Timeline).

**Cost**: Medium-high migration. All `mat-*` components replaced with `p-*` equivalents.

**When to choose this**: If the redesign also includes new complex components (gradable tables, analytics dashboards, calendar view for study scheduling).

---

## 5. Design Token Approach

### Three-Tier Token Architecture (Industry Best Practice)

Based on Adobe Spectrum's model and Material 3 conventions:

```
Tier 1 — Global Tokens (raw values)
  --color-indigo-500: oklch(58% .22 264);
  --color-amber-400:  oklch(78% .17  80);
  --radius-sm: 6px;  --radius-md: 10px;  --radius-lg: 16px;

Tier 2 — Semantic/Alias Tokens (intent, not value)
  --color-primary:          var(--color-indigo-500);
  --color-surface:          #ffffff;
  --color-surface-subtle:   #f8f9fa;
  --color-text:             #111827;
  --color-text-muted:       #6b7280;
  --color-border:           #e5e7eb;
  --color-correct:          var(--color-emerald-500);
  --color-incorrect:        var(--color-red-400);

Tier 3 — Component Tokens (scoped)
  --flashcard-radius:       var(--radius-lg);
  --flashcard-min-height:   280px;
  --quiz-question-font-size: 20px;
  --srs-btn-correct-bg:     var(--color-emerald-500);
  --srs-btn-hard-bg:        var(--color-amber-400);
```

### CSS Custom Properties Best Practices
- Declare all tokens on `:root` for global access.
- Use `@layer base` to set tokens below component styles in the cascade.
- Angular Material's `--mat-sys-*` properties are auto-generated from `mat.theme()` — map your Tier 2 tokens to these where possible.
- For dark mode override (future): swap Tier 2 tokens inside `@media (prefers-color-scheme: dark)` or `.dark` class — no component changes needed.

### Figma–Code Token Sync
- Name Figma styles to match CSS variable names exactly (e.g., Figma colour `surface/primary` = CSS `--color-surface`).
- Use the Figma Tokens plugin or Figma Variables (native as of 2024) to export as JSON → transform to CSS via Style Dictionary.
- M3's Figma Design Kit is available (community file, updated for M3 Expressive 2025) — provides a starting Figma token set aligned to `--mat-sys-*`.

---

## 6. Specific Component Patterns to Adopt

### Progress/Gamification Components
- **Streak badge**: `<mat-icon>local_fire_department</mat-icon> + number`, styled as a pill chip.
- **XP progress bar**: `<mat-progress-bar>` with custom `--mdc-linear-progress-active-indicator-color`.
- **Score ring**: SVG circle with `stroke-dasharray` animation — not in Material, build custom.
- **Completion checkmark**: Material's `<mat-icon>check_circle</mat-icon>` with animation scale-in.

### SRS Rating Buttons (Anki-style)
```html
<div class="srs-actions">
  <button class="srs-btn srs-btn--again">Again</button>
  <button class="srs-btn srs-btn--hard">Hard</button>
  <button class="srs-btn srs-btn--good">Good</button>
  <button class="srs-btn srs-btn--easy">Easy</button>
</div>
```
```css
.srs-btn--again { --srs-color: var(--color-incorrect); }
.srs-btn--hard  { --srs-color: var(--color-amber-400); }
.srs-btn--good  { --srs-color: var(--color-primary); }
.srs-btn--easy  { --srs-color: var(--color-correct); }

.srs-btn {
  background: color-mix(in oklch, var(--srs-color) 12%, transparent);
  color: var(--srs-color);
  border: 1.5px solid color-mix(in oklch, var(--srs-color) 30%, transparent);
  border-radius: var(--radius-md);
  font-weight: 600;
  padding: 10px 24px;
  transition: background 150ms;
}
```

### Sidebar Navigation
- Use `<mat-sidenav-container>` with custom styling.
- Icon + label mode: `mat-list-item` with `mat-icon` + text, width `240px`.
- Collapsed mode: icon-only, width `64px`. Transition with `width` CSS animation.
- Active state: primary colour background at `12%` opacity, left border `3px solid var(--color-primary)`.
