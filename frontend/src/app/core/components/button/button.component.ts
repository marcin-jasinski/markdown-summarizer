import { ChangeDetectionStrategy, Component, input } from '@angular/core';

@Component({
  selector: 'mf-button',
  standalone: true,
  templateUrl: './button.component.html',
  styleUrls: ['./button.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '[class.mf-btn-primary]': 'variant() === "primary"',
    '[class.mf-btn-secondary]': 'variant() === "secondary"',
    '[class.mf-btn-ghost]': 'variant() === "ghost"',
    '[class.mf-btn-danger]': 'variant() === "danger"',
    '[class.mf-btn-icon]': 'variant() === "icon"',
    '[class.mf-btn-sm]': 'size() === "sm"',
    '[class.mf-btn-md]': 'size() === "md"',
    '[class.mf-btn-lg]': 'size() === "lg"',
    '[class.mf-btn-loading]': 'loading()',
    '[attr.aria-disabled]': 'disabled() || loading() ? true : null',
  },
})
export class ButtonComponent {
  readonly variant = input<'primary' | 'secondary' | 'ghost' | 'danger' | 'icon'>('primary');
  readonly size = input<'sm' | 'md' | 'lg'>('md');
  readonly disabled = input(false);
  readonly loading = input(false);
}
