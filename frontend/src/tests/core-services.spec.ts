import { TestBed } from '@angular/core/testing';
import { DOCUMENT } from '@angular/common';
import { ThemeService } from '../app/core/services/theme.service';
import { MfSnackbarService } from '../app/core/services/mf-snackbar.service';

// ---------------------------------------------------------------------------
// ThemeService
// ---------------------------------------------------------------------------

describe('ThemeService', () => {
  afterEach(() => {
    TestBed.resetTestingModule();
    vi.restoreAllMocks();
    localStorage.clear();
  });

  function setup(prefersDark: boolean, storedTheme: string | null = null) {
    localStorage.clear();
    if (storedTheme !== null) {
      localStorage.setItem('mf-theme', storedTheme);
    }

    const setAttributeSpy = vi.fn();
    const mockDoc = {
      defaultView: {
        matchMedia: (_q: string) => ({ matches: prefersDark }),
      },
      documentElement: { setAttribute: setAttributeSpy },
    };

    TestBed.configureTestingModule({
      providers: [
        ThemeService,
        { provide: DOCUMENT, useValue: mockDoc },
      ],
    });

    const service = TestBed.inject(ThemeService);
    return { service, setAttributeSpy };
  }

  it('Test 1: isDark() is true when OS prefers-color-scheme is dark and no localStorage value', () => {
    const { service } = setup(true, null);
    expect(service.isDark()).toBe(true);
  });

  it('Test 2: toggle() flips isDark() and writes mf-theme to localStorage', () => {
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem');
    const { service } = setup(false, null);
    expect(service.isDark()).toBe(false);
    service.toggle();
    expect(service.isDark()).toBe(true);
    expect(setItemSpy).toHaveBeenCalledWith('mf-theme', 'dark');
  });

  it('Test 3: constructor sets data-theme attribute on document.documentElement', () => {
    const { setAttributeSpy } = setup(true, null);
    expect(setAttributeSpy).toHaveBeenCalledWith('data-theme', 'dark');
  });
});

// ---------------------------------------------------------------------------
// MfSnackbarService
// ---------------------------------------------------------------------------

describe('MfSnackbarService', () => {
  let service: MfSnackbarService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [MfSnackbarService],
    });
    service = TestBed.inject(MfSnackbarService);
  });

  afterEach(() => {
    TestBed.resetTestingModule();
    document.querySelectorAll('.mf-toast-container').forEach(el => el.remove());
  });

  it('Test 4: show() appends toast element to DOM with success class', () => {
    service.show('Operation successful', 'success');
    const toast = document.querySelector('.mf-toast-success');
    expect(toast).not.toBeNull();
    expect(toast!.textContent).toBe('Operation successful');
  });
});
