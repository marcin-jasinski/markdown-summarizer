import { Injectable, inject, signal } from '@angular/core';
import { DOCUMENT } from '@angular/common';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  private readonly document = inject(DOCUMENT);

  // Dark mode temporarily disabled — set to true to re-enable
  private readonly DARK_MODE_ENABLED = false;

  isDark = signal(false);

  constructor() {
    if (!this.DARK_MODE_ENABLED) {
      this.isDark.set(false);
      this.applyTheme();
      return;
    }
    const stored = localStorage.getItem('mf-theme');
    if (stored !== null) {
      this.isDark.set(stored === 'dark');
    } else {
      const win = this.document.defaultView;
      const prefersDark = win?.matchMedia('(prefers-color-scheme: dark)').matches ?? false;
      this.isDark.set(prefersDark);
    }
    this.applyTheme();
  }

  toggle(): void {
    if (!this.DARK_MODE_ENABLED) return;
    this.isDark.update(v => !v);
    this.applyTheme();
  }

  private applyTheme(): void {
    this.document.documentElement.setAttribute(
      'data-theme',
      this.isDark() ? 'dark' : 'light',
    );
    localStorage.setItem('mf-theme', this.isDark() ? 'dark' : 'light');
  }
}
