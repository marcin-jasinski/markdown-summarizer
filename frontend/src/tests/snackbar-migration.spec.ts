/**
 * Snackbar Migration Tests — MfSnackbarService DOM behaviour + kb-create-dialog purity check
 */
import { TestBed } from '@angular/core/testing';
import { DOCUMENT } from '@angular/common';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { MfSnackbarService } from '../app/core/services/mf-snackbar.service';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

describe('MfSnackbarService migration', () => {
  let service: MfSnackbarService;
  let doc: Document;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [MfSnackbarService],
    });
    service = TestBed.inject(MfSnackbarService);
    doc = TestBed.inject(DOCUMENT);
  });

  afterEach(() => {
    vi.useRealTimers();
    doc.querySelector('.mf-toast-container')?.remove();
    // Reset cached container on the service instance so next test starts fresh
    (service as unknown as { container: HTMLElement | null }).container = null;
  });

  it('Test 1: show("Saved", "success") creates element with class mf-toast-success', () => {
    service.show('Saved', 'success');
    const toast = doc.querySelector('.mf-toast-success');
    expect(toast).not.toBeNull();
    expect(toast?.textContent).toBe('Saved');
  });

  it('Test 2: show("Error", "error") toast auto-removes after 4000ms', () => {
    vi.useFakeTimers();
    service.show('Error', 'error');
    const toast = doc.querySelector('.mf-toast-error');
    expect(toast).not.toBeNull();
    vi.runAllTimers();
    expect(doc.querySelector('.mf-toast-error')).toBeNull();
  });

  it('Test 3: show("Info", "info") creates element with class mf-toast-info', () => {
    service.show('Info', 'info');
    const toast = doc.querySelector('.mf-toast-info');
    expect(toast).not.toBeNull();
    expect(toast?.textContent).toBe('Info');
  });

  it('Test 4: kb-create-dialog.ts does not contain MatDialog', () => {
    const filePath = resolve(__dirname, '../app/pages/dashboard/kb-create-dialog.ts');
    const content = readFileSync(filePath, 'utf-8');
    expect(content).not.toContain('MatDialog');
  });
});
