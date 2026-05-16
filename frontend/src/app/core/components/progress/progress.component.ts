import { ChangeDetectionStrategy, Component, input } from '@angular/core';

@Component({
  selector: 'mf-progress',
  standalone: true,
  template: `
    <div class="mf-progress-track">
      @if (!indeterminate()) {
        <div class="mf-progress-fill" [style.width.%]="value()"></div>
      }
      @if (indeterminate()) {
        <div class="mf-progress-sweep"></div>
      }
    </div>
  `,
  styleUrls: ['./progress.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '[class.mf-progress-indeterminate]': 'indeterminate()',
    '[class.mf-progress-primary]': 'color() === "primary"',
    '[class.mf-progress-success]': 'color() === "success"',
    '[class.mf-progress-danger]': 'color() === "danger"',
  },
})
export class ProgressComponent {
  readonly value = input(0);
  readonly indeterminate = input(false);
  readonly color = input<'primary' | 'success' | 'danger'>('primary');
}
