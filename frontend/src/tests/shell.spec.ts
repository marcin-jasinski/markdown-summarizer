/**
 * Shell Component Tests (Group 6)
 * Tests for SidebarComponent, ShellComponent, and ToolbarComponent.
 */
import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { BehaviorSubject, of } from 'rxjs';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { signal, computed } from '@angular/core';
import { BreakpointObserver } from '@angular/cdk/layout';

import { SidebarComponent } from '../app/shell/sidebar/sidebar.component';
import { ShellComponent } from '../app/shell/shell';
import { ToolbarComponent } from '../app/shell/toolbar/toolbar.component';
import { ThemeService } from '../app/core/services/theme.service';
import { AuthService } from '../app/core/services/auth.service';
import { ApiService } from '../app/core/services/api.service';

// ---------------------------------------------------------------------------
// SidebarComponent
// ---------------------------------------------------------------------------

describe('SidebarComponent', () => {
  let getItemSpy: ReturnType<typeof vi.spyOn>;
  let setItemSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    getItemSpy = vi.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);
    setItemSpy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {});

    TestBed.configureTestingModule({
      imports: [SidebarComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting(),
        {
          provide: ApiService,
          useValue: { getMyStats: () => of({ streak_days: 0, due_today: 0 }) },
        },
      ],
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    TestBed.resetTestingModule();
  });

  it('Test 1: sidebarCollapsed starts false; after toggle button click becomes true', () => {
    const fixture = TestBed.createComponent(SidebarComponent);
    fixture.detectChanges();

    expect(fixture.componentInstance.sidebarCollapsed()).toBe(false);

    const toggleBtn = fixture.debugElement.query(By.css('.mf-sidebar-toggle'));
    toggleBtn.nativeElement.click();
    fixture.detectChanges();

    expect(fixture.componentInstance.sidebarCollapsed()).toBe(true);
  });

  it('Test 2: collapseToggle calls localStorage.setItem("mf-sidebar-collapsed", "true")', () => {
    const fixture = TestBed.createComponent(SidebarComponent);
    fixture.detectChanges();
    setItemSpy.mockClear();

    fixture.componentInstance.collapseToggle();
    fixture.detectChanges();

    expect(setItemSpy).toHaveBeenCalledWith('mf-sidebar-collapsed', 'true');
  });

  it('Test 3: init reads localStorage.getItem and sets sidebarCollapsed accordingly', () => {
    getItemSpy.mockReturnValue('true');

    const fixture = TestBed.createComponent(SidebarComponent);
    fixture.detectChanges();

    expect(fixture.componentInstance.sidebarCollapsed()).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// ShellComponent
// ---------------------------------------------------------------------------

describe('ShellComponent', () => {
  let bpSubject: BehaviorSubject<{ matches: boolean }>;

  beforeEach(() => {
    vi.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {});

    bpSubject = new BehaviorSubject<{ matches: boolean }>({ matches: false });

    TestBed.configureTestingModule({
      imports: [ShellComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        provideHttpClient(),
        provideHttpClientTesting(),
        {
          provide: BreakpointObserver,
          useValue: { observe: () => bpSubject.asObservable() },
        },
        {
          provide: AuthService,
          useValue: {
            user: signal(null),
            isAuthenticated: computed(() => false),
            logout: () => of(null),
          },
        },
        {
          provide: ApiService,
          useValue: { getMyStats: () => of({ streak_days: 0, due_today: 0 }) },
        },
        {
          provide: ThemeService,
          useValue: { isDark: signal(false), toggle: vi.fn() },
        },
      ],
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    TestBed.resetTestingModule();
  });

  it('Test 4: with BreakpointObserver matching sets isMobile to true', () => {
    bpSubject.next({ matches: true });

    const fixture = TestBed.createComponent(ShellComponent);
    fixture.detectChanges();

    expect(fixture.componentInstance.isMobile()).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// ToolbarComponent
// ---------------------------------------------------------------------------

describe('ToolbarComponent', () => {
  let mockToggle: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    mockToggle = vi.fn();

    TestBed.configureTestingModule({
      imports: [ToolbarComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        {
          provide: ThemeService,
          useValue: { isDark: signal(false), toggle: mockToggle },
        },
        {
          provide: AuthService,
          useValue: {
            user: signal(null),
            isAuthenticated: computed(() => false),
            logout: () => of(null),
          },
        },
      ],
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    TestBed.resetTestingModule();
  });

  it('Test 5: theme toggle button click calls ThemeService.toggle()', () => {
    const fixture = TestBed.createComponent(ToolbarComponent);
    fixture.detectChanges();

    const themeBtn = fixture.debugElement.query(By.css('.mf-toolbar-icon-btn'));
    themeBtn.nativeElement.click();
    fixture.detectChanges();

    expect(mockToggle).toHaveBeenCalledTimes(1);
  });
});
