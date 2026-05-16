import { animate, style, transition, trigger } from '@angular/animations';
import { ChangeDetectionStrategy, Component, inject, input } from '@angular/core';
import { DialogRef, DIALOG_DATA } from '@angular/cdk/dialog';

@Component({
  selector: 'mf-dialog',
  standalone: true,
  template: `
    <div class="mf-dialog-header">
      <span class="mf-dialog-title">{{ title() }}</span>
      @if (!disableClose()) {
        <button class="mf-dialog-close" (click)="close()" aria-label="Zamknij">
          <ng-content select="[slot=closeIcon]">×</ng-content>
        </button>
      }
    </div>
    <div class="mf-dialog-content">
      <ng-content />
    </div>
    <div class="mf-dialog-actions">
      <ng-content select="[slot=actions]" />
    </div>
  `,
  styleUrls: ['./dialog.component.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
  animations: [
    trigger('dialogEnter', [
      transition(':enter', [
        style({ opacity: 0, transform: 'scale(0.95)' }),
        animate('200ms ease-out', style({ opacity: 1, transform: 'scale(1)' })),
      ]),
    ]),
  ],
  host: {
    '[@dialogEnter]': '""',
  },
})
export class DialogComponent {
  readonly title = input('');
  readonly disableClose = input(false);

  private readonly dialogRef = inject(DialogRef);
  readonly data = inject(DIALOG_DATA, { optional: true });

  close(): void {
    this.dialogRef.close();
  }
}
