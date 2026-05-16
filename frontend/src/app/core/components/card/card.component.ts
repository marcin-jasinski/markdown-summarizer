import { ChangeDetectionStrategy, Component, input } from '@angular/core';

@Component({
  selector: 'mf-card',
  standalone: true,
  template: '<ng-content />',
  styleUrls: ['./card.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '[class.mf-card-elevated]': 'variant() === "elevated"',
    '[class.mf-card-flat]': 'variant() === "flat"',
    '[class.mf-card-hoverable]': 'hoverable()',
    '[class.mf-card-pad-sm]': 'padding() === "sm"',
    '[class.mf-card-pad-md]': 'padding() === "md"',
    '[class.mf-card-pad-lg]': 'padding() === "lg"',
  },
})
export class CardComponent {
  readonly variant = input<'default' | 'elevated' | 'flat'>('default');
  readonly hoverable = input(false);
  readonly padding = input<'sm' | 'md' | 'lg'>('md');
}
