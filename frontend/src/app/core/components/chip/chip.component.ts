import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  input,
  output,
  signal,
} from '@angular/core';

@Component({
  selector: 'mf-chip',
  standalone: true,
  template: `
    <ng-content />
    @if (variant() === 'removable') {
      <button class="mf-chip-remove" (click)="removed.emit()" aria-label="Remove" tabindex="-1">×</button>
    }
  `,
  styleUrls: ['./chip.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '[attr.tabindex]': '0',
    '[attr.aria-pressed]': 'variant() === "active" ? isActive() : null',
    '[class.mf-chip-active]': 'isActive()',
    '[class.mf-chip-removable]': 'variant() === "removable"',
    '[class.mf-chip-subtle]': 'variant() === "subtle"',
    '[class.mf-chip-status]': 'variant() === "status"',
    '[class.mf-chip-sm]': 'size() === "sm"',
    '[class.mf-chip-correct]': 'color() === "correct"',
    '[class.mf-chip-incorrect]': 'color() === "incorrect"',
    '[class.mf-chip-pending]': 'color() === "pending"',
    '[class.mf-chip-processing]': 'color() === "processing"',
  },
})
export class ChipComponent {
  readonly variant = input<'default' | 'active' | 'removable' | 'subtle' | 'status'>('default');
  readonly size = input<'sm' | 'md'>('md');
  readonly color = input<'correct' | 'incorrect' | 'pending' | 'processing' | ''>('');
  readonly removed = output<void>();

  readonly isActive = signal(false);

  @HostListener('keydown', ['$event'])
  onKeydown(event: KeyboardEvent): void {
    if ((event.key === 'Enter' || event.key === ' ') && this.variant() === 'active') {
      this.isActive.update(v => !v);
    }
    if ((event.key === 'Delete' || event.key === 'Backspace') && this.variant() === 'removable') {
      this.removed.emit();
    }
  }
}
