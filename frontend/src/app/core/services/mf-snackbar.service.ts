import { Injectable, inject } from '@angular/core';
import { DOCUMENT } from '@angular/common';

@Injectable({ providedIn: 'root' })
export class MfSnackbarService {
  private readonly document = inject(DOCUMENT);
  private container: HTMLElement | null = null;

  private ensureContainer(): void {
    if (this.container) {
      return;
    }
    const div = this.document.createElement('div');
    div.className = 'mf-toast-container';
    div.style.cssText = [
      'position:fixed',
      'bottom:24px',
      'right:24px',
      'z-index:9999',
      'display:flex',
      'flex-direction:column-reverse',
      'gap:8px',
      'pointer-events:none',
    ].join(';');
    this.document.body.appendChild(div);
    this.container = div;
  }

  show(message: string, type: 'success' | 'error' | 'info' = 'info'): void {
    this.ensureContainer();
    const toast = this.document.createElement('div');
    toast.className = `mf-toast mf-toast-${type}`;
    toast.textContent = message;
    toast.style.pointerEvents = 'auto';
    this.container!.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
  }
}
