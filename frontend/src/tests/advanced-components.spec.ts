/**
 * Advanced Component Tests — mf-chip, mf-dialog, mf-progress
 *
 * Verifies keyboard interaction, CDK Dialog integration, and progress
 * rendering for the advanced mf-* presentational components.
 */
import { TestBed, ComponentFixture } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { DialogRef, DIALOG_DATA } from '@angular/cdk/dialog';
import { ChipComponent } from '../app/core/components/chip/chip.component';
import { DialogComponent } from '../app/core/components/dialog/dialog.component';
import { ProgressComponent } from '../app/core/components/progress/progress.component';

// ---------------------------------------------------------------------------
// mf-chip
// ---------------------------------------------------------------------------

describe('ChipComponent (mf-chip)', () => {
  let fixture: ComponentFixture<ChipComponent>;
  let host: HTMLElement;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [ChipComponent] });
    fixture = TestBed.createComponent(ChipComponent);
    host = fixture.nativeElement as HTMLElement;
  });

  it('Test 1: variant="active" — pressing Enter toggles isActive (aria-pressed)', () => {
    fixture.componentRef.setInput('variant', 'active');
    fixture.detectChanges();
    expect(host.getAttribute('aria-pressed')).toBe('false');

    host.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    fixture.detectChanges();
    expect(host.getAttribute('aria-pressed')).toBe('true');
  });

  it('Test 2: variant="removable" — pressing Delete emits removed output', () => {
    fixture.componentRef.setInput('variant', 'removable');
    fixture.detectChanges();

    let removed = false;
    fixture.componentInstance.removed.subscribe(() => { removed = true; });

    host.dispatchEvent(new KeyboardEvent('keydown', { key: 'Delete', bubbles: true }));
    fixture.detectChanges();
    expect(removed).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// mf-dialog
// ---------------------------------------------------------------------------

describe('DialogComponent (mf-dialog)', () => {
  let fixture: ComponentFixture<DialogComponent>;
  let host: HTMLElement;
  let mockDialogRef: { close: () => void };

  beforeEach(() => {
    mockDialogRef = { close: vi.fn() };
    TestBed.configureTestingModule({
      imports: [DialogComponent],
      providers: [
        provideNoopAnimations(),
        { provide: DialogRef, useValue: mockDialogRef },
        { provide: DIALOG_DATA, useValue: null },
      ],
    });
    fixture = TestBed.createComponent(DialogComponent);
    host = fixture.nativeElement as HTMLElement;
  });

  it('Test 3: renders the title input in the dialog header', () => {
    fixture.componentRef.setInput('title', 'Confirm action');
    fixture.detectChanges();
    const titleEl = host.querySelector('.mf-dialog-title');
    expect(titleEl?.textContent?.trim()).toBe('Confirm action');
  });

  it('Test 4: close button click calls DialogRef.close()', () => {
    fixture.detectChanges();
    const closeBtn = host.querySelector<HTMLElement>('.mf-dialog-close');
    expect(closeBtn).not.toBeNull();
    closeBtn!.click();
    expect(mockDialogRef.close).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// mf-progress
// ---------------------------------------------------------------------------

describe('ProgressComponent (mf-progress)', () => {
  let fixture: ComponentFixture<ProgressComponent>;
  let host: HTMLElement;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [ProgressComponent] });
    fixture = TestBed.createComponent(ProgressComponent);
    host = fixture.nativeElement as HTMLElement;
  });

  it('Test 5: [value]="75" — inner fill bar has width: 75%', () => {
    fixture.componentRef.setInput('value', 75);
    fixture.detectChanges();
    const fill = host.querySelector<HTMLElement>('.mf-progress-fill');
    expect(fill).not.toBeNull();
    expect(fill!.style.width).toBe('75%');
  });

  it('Test 6: [indeterminate]="true" — host has mf-progress-indeterminate class', () => {
    fixture.componentRef.setInput('indeterminate', true);
    fixture.detectChanges();
    expect(host.classList.contains('mf-progress-indeterminate')).toBe(true);
  });
});
