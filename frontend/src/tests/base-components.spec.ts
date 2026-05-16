/**
 * Base Component Tests — mf-button, mf-card, mf-input
 *
 * Verifies host bindings, template rendering, and two-way binding behavior
 * for the core mf-* presentational components.
 */
import { TestBed, ComponentFixture } from '@angular/core/testing';
import { ButtonComponent } from '../app/core/components/button/button.component';
import { CardComponent } from '../app/core/components/card/card.component';
import { InputComponent } from '../app/core/components/input/input.component';

// ---------------------------------------------------------------------------
// mf-button
// ---------------------------------------------------------------------------

describe('ButtonComponent (mf-button)', () => {
  let fixture: ComponentFixture<ButtonComponent>;
  let host: HTMLElement;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [ButtonComponent] });
    fixture = TestBed.createComponent(ButtonComponent);
    host = fixture.nativeElement as HTMLElement;
  });

  it('Test 1: variant="primary" adds mf-btn-primary class on host', () => {
    fixture.componentRef.setInput('variant', 'primary');
    fixture.detectChanges();
    expect(host.classList.contains('mf-btn-primary')).toBe(true);
  });

  it('Test 2: [loading]="true" renders a spinner element in the template', () => {
    fixture.componentRef.setInput('loading', true);
    fixture.detectChanges();
    const spinner = host.querySelector('.mf-btn-spinner');
    expect(spinner).not.toBeNull();
  });

  it('Test 3: [disabled]="true" sets aria-disabled="true" on host', () => {
    fixture.componentRef.setInput('disabled', true);
    fixture.detectChanges();
    expect(host.getAttribute('aria-disabled')).toBe('true');
  });
});

// ---------------------------------------------------------------------------
// mf-card
// ---------------------------------------------------------------------------

describe('CardComponent (mf-card)', () => {
  let fixture: ComponentFixture<CardComponent>;
  let host: HTMLElement;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [CardComponent] });
    fixture = TestBed.createComponent(CardComponent);
    host = fixture.nativeElement as HTMLElement;
  });

  it('Test 4: [hoverable]="true" adds mf-card-hoverable class on host', () => {
    fixture.componentRef.setInput('hoverable', true);
    fixture.detectChanges();
    expect(host.classList.contains('mf-card-hoverable')).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// mf-input
// ---------------------------------------------------------------------------

describe('InputComponent (mf-input)', () => {
  let fixture: ComponentFixture<InputComponent>;
  let host: HTMLElement;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [InputComponent] });
    fixture = TestBed.createComponent(InputComponent);
    host = fixture.nativeElement as HTMLElement;
  });

  it('Test 5: setting value model renders the value in the native input element', () => {
    fixture.componentInstance.value.set('hello');
    fixture.detectChanges();
    const input = host.querySelector<HTMLInputElement>('input.mf-input-field');
    expect(input).not.toBeNull();
    expect(input!.value).toBe('hello');
  });

  it('Test 6: [error]="Required" renders error text in DOM', () => {
    fixture.componentRef.setInput('error', 'Required');
    fixture.detectChanges();
    const errorEl = host.querySelector('.mf-input-error-text');
    expect(errorEl).not.toBeNull();
    expect(errorEl!.textContent?.trim()).toBe('Required');
  });
});
