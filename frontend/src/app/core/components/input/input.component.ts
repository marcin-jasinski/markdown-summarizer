import { ChangeDetectionStrategy, Component, input, model } from '@angular/core';

@Component({
  selector: 'mf-input',
  standalone: true,
  templateUrl: './input.component.html',
  styleUrls: ['./input.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InputComponent {
  readonly label = input('');
  readonly placeholder = input('');
  readonly type = input('text');
  readonly disabled = input(false);
  readonly error = input('');
  readonly helperText = input('');
  readonly value = model<string>('');
}
