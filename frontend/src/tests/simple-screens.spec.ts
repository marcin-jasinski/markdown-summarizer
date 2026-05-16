/**
 * Simple Screens Tests — LoginComponent + KnowledgeBasesComponent
 * Group 8 — Phase 4 Screen Redesigns
 */
import { TestBed, ComponentFixture } from '@angular/core/testing';
import { DOCUMENT } from '@angular/common';
import { provideRouter } from '@angular/router';
import { Dialog } from '@angular/cdk/dialog';
import { of } from 'rxjs';

import { LoginComponent } from '../app/pages/login/login';
import { KnowledgeBasesComponent } from '../app/pages/knowledge-bases/knowledge-bases';
import { AuthService } from '../app/core/services/auth.service';
import { ThemeService } from '../app/core/services/theme.service';
import { KnowledgeBaseService } from '../app/core/services/knowledge-base.service';
import { MfSnackbarService } from '../app/core/services/mf-snackbar.service';
import type { KnowledgeBaseResponse } from '../app/core/models/api.models';

// Mock window.matchMedia (required for ThemeService constructor)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  configurable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// ---------------------------------------------------------------------------
// LoginComponent
// ---------------------------------------------------------------------------

describe('LoginComponent', () => {
  let fixture: ComponentFixture<LoginComponent>;
  let el: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [LoginComponent],
      providers: [
        provideRouter([]),
        {
          provide: AuthService,
          useValue: {
            login: () => of({}),
            register: () => of({}),
            loginWithProvider: vi.fn(),
            loadCurrentUser: () => of(null),
          },
        },
        {
          provide: MfSnackbarService,
          useValue: { show: vi.fn() },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(LoginComponent);
    el = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
  });

  it('Test 1: renders Polish text — contains MindForge or Logowanie', () => {
    const text = el.textContent ?? '';
    expect(text.includes('MindForge') || text.includes('Logowanie')).toBe(true);
  });

  it('Test 2: submit button has loading class when isLoading() is true', () => {
    fixture.componentInstance.isLoading.set(true);
    fixture.detectChanges();
    const btn = el.querySelector('button[type="submit"]') as HTMLButtonElement;
    expect(btn).not.toBeNull();
    expect(btn.classList.contains('loading')).toBe(true);
  });

  it('Test 3: ThemeService — isDark() true sets data-theme="dark"', () => {
    const theme = TestBed.inject(ThemeService);
    const doc = TestBed.inject(DOCUMENT);
    if (!theme.isDark()) {
      theme.toggle();
    }
    expect(doc.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  afterEach(() => {
    // Reset theme after Test 3 to avoid leaking state
    localStorage.removeItem('mf-theme');
  });
});

// ---------------------------------------------------------------------------
// KnowledgeBasesComponent
// ---------------------------------------------------------------------------

describe('KnowledgeBasesComponent', () => {
  let fixture: ComponentFixture<KnowledgeBasesComponent>;
  let el: HTMLElement;
  let mockDialog: { open: ReturnType<typeof vi.fn> };

  const sampleKb: KnowledgeBaseResponse = {
    kb_id: 'kb-1',
    name: 'Test KB',
    description: 'A test knowledge base',
    owner_id: 'user-1',
    created_at: '2024-01-01T00:00:00Z',
    document_count: 3,
    prompt_locale: 'pl',
  };

  beforeEach(async () => {
    mockDialog = { open: vi.fn().mockReturnValue({ closed: of(null) }) };

    await TestBed.configureTestingModule({
      imports: [KnowledgeBasesComponent],
      providers: [
        provideRouter([]),
        {
          provide: KnowledgeBaseService,
          useValue: { list: () => of([]), delete: () => of(undefined) },
        },
        {
          provide: Dialog,
          useValue: mockDialog,
        },
        {
          provide: MfSnackbarService,
          useValue: { show: vi.fn() },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(KnowledgeBasesComponent);
    el = fixture.nativeElement as HTMLElement;
  });

  it('Test 4: renders grid container with mf-kb-grid class when kbs has items', () => {
    fixture.detectChanges(); // triggers ngOnInit → kbs=[], isLoading=false
    fixture.componentInstance.kbs.set([sampleKb]);
    fixture.detectChanges(); // re-render with populated kbs
    const grid = el.querySelector('.mf-kb-grid');
    expect(grid).not.toBeNull();
  });

  it('Test 5: openCreateDialog() invokes CDK Dialog.open()', () => {
    fixture.detectChanges();
    fixture.componentInstance.openCreateDialog();
    expect(mockDialog.open).toHaveBeenCalled();
  });

  it('Test 6: empty state is rendered when kbs signal is empty array', () => {
    fixture.detectChanges(); // ngOnInit → kbs=[], isLoading=false → empty state
    const emptyState = el.querySelector('.mf-kb-empty');
    expect(emptyState).not.toBeNull();
  });
});
