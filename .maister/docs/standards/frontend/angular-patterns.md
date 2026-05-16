# Angular Patterns

MindForge uses Angular 21 with standalone components and modern reactive patterns.

## Standalone Components

All components must use `standalone: true`. No NgModules.

```typescript
@Component({
  selector: 'app-quiz',
  standalone: true,
  imports: [CommonModule, MatButtonModule, ...],
  templateUrl: './quiz.html',
  styleUrl: './quiz.scss',
})
export class QuizComponent { ... }
```

## Dependency Injection

Use Angular's `inject()` function — not constructor injection:

```typescript
// CORRECT
export class QuizComponent {
  private readonly quizSvc = inject(QuizService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
}

// AVOID: constructor injection (legacy pattern)
constructor(private quizSvc: QuizService) {}  // ❌
```

## Signals for State

Use `signal()` and `computed()` for component state. Do not use class properties or `BehaviorSubject` for local UI state:

```typescript
// CORRECT
readonly loading = signal(true);
readonly cards = signal<Flashcard[]>([]);
readonly currentIndex = signal(0);
readonly currentCard = computed(() => this.cards()[this.currentIndex()] ?? null);
readonly progress = computed(() => `${this.currentIndex() + 1} / ${this.cards().length}`);

// AVOID
loading = true;                         // ❌ plain property
loading$ = new BehaviorSubject(true);  // ❌ BehaviorSubject for local state
```

For service-level shared state, expose signals as `asReadonly()`:

```typescript
// In AuthService
private readonly _user = signal<User | null>(null);
readonly user = this._user.asReadonly();
readonly isAuthenticated = computed(() => this._user() !== null);
```

## HTTP Integration

**All HTTP calls must flow through `ApiService`** (`core/services/api.service.ts`). Never inject `HttpClient` directly in components or feature services.

```typescript
// CORRECT: feature service uses ApiService
export class QuizService {
  private readonly api = inject(ApiService);

  startSession(kbId: string): Observable<QuizQuestionResponse> {
    return this.api.post<QuizQuestionResponse>('/quiz/sessions', { kb_id: kbId });
  }
}

// NEVER: direct HttpClient in component or feature service
export class SomeComponent {
  private readonly http = inject(HttpClient);  // ❌
}
```

## Observable Naming

The `$` suffix convention for observables is **not used** in this codebase. Don't add it:

```typescript
// CORRECT
startSession(kbId: string): Observable<QuizQuestionResponse>

// NOT USED
startSession$(kbId: string): Observable<QuizQuestionResponse>  // ❌ no $ suffix
```

## API Type Generation

API types are generated from the backend's OpenAPI spec. Never write or edit API types by hand:

```bash
# After any backend schema change:
npm run openapi:generate
```

The canonical output is `src/app/core/models/api.generated.ts`. Do not manually edit this file.

## TypeScript Style

- Single quotes for strings (enforced by `.editorconfig` and Prettier)
- 2-space indentation (enforced by `.editorconfig`)
- Print width: 100 characters (matches backend ruff line-length)
- ES2022 target: class fields, top-level await, and other ES2022 features are safe to use

## SCSS

All component styles use `.scss`. Never use `.css` or `.less` for component styles.
