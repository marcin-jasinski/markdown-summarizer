import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

@Component({
  selector: 'mf-skeleton',
  standalone: true,
  template: '',
  styleUrls: ['./skeleton.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '[class.mf-skeleton]': 'true',
    '[class.mf-skeleton-circle]': 'variant() === "circle"',
    '[class.mf-skeleton-text]': 'variant() === "text"',
    '[style.height]': 'heightStyle()',
    '[style.width]': 'widthStyle()',
  },
})
export class SkeletonComponent {
  readonly height = input<string | number>('1rem');
  readonly width = input<string | number>('100%');
  readonly variant = input<'rect' | 'circle' | 'text'>('rect');

  readonly heightStyle = computed(() => {
    const h = this.height();
    return typeof h === 'number' ? `${h}px` : h;
  });

  readonly widthStyle = computed(() => {
    const w = this.width();
    return typeof w === 'number' ? `${w}px` : w;
  });
}
