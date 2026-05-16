import { Component, ChangeDetectionStrategy, inject, signal, computed } from '@angular/core';
import { DialogRef, DIALOG_DATA } from '@angular/cdk/dialog';
import { KnowledgeBaseService } from '../../core/services/knowledge-base.service';
import { MfSnackbarService } from '../../core/services/mf-snackbar.service';
import { DialogComponent } from '../../core/components/dialog/dialog.component';
import { InputComponent } from '../../core/components/input/input.component';

@Component({
  selector: 'app-kb-create-dialog',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DialogComponent, InputComponent],
  template: `
    <mf-dialog title="New Knowledge Base">
      <div class="dialog-form">
        <mf-input label="Name" [(value)]="name" />
        <label class="mf-input-label">Description</label>
        <textarea
          class="dialog-textarea"
          [value]="description()"
          (input)="description.set($any($event.target).value)"
          rows="3"
          maxlength="2000"
        ></textarea>
        <label class="mf-input-label">Prompt Language</label>
        <select
          class="dialog-select"
          (change)="promptLocale.set($any($event.target).value)"
        >
          <option value="pl" [selected]="promptLocale() === 'pl'">Polish</option>
          <option value="en" [selected]="promptLocale() === 'en'">English</option>
        </select>
      </div>
      <div slot="actions">
        <button class="mf-btn-ghost" type="button" (click)="dialogRef.close()">Cancel</button>
        <button class="mf-btn-primary" type="button" (click)="create()" [disabled]="!isValid()">Create</button>
      </div>
    </mf-dialog>
  `,
  styles: [`
    .dialog-form { display: flex; flex-direction: column; gap: 12px; min-width: 360px; padding-top: 8px; }
    .dialog-textarea { width: 100%; padding: 8px; border: 1px solid var(--mf-border, #334155); border-radius: 6px; background: var(--mf-surface, #1e293b); color: var(--mf-text, #f1f5f9); font-size: 14px; resize: vertical; box-sizing: border-box; }
    .dialog-select { width: 100%; padding: 8px; border: 1px solid var(--mf-border, #334155); border-radius: 6px; background: var(--mf-surface, #1e293b); color: var(--mf-text, #f1f5f9); font-size: 14px; }
    .mf-btn-ghost, .mf-btn-primary { padding: 8px 16px; border-radius: 6px; border: none; cursor: pointer; font-size: 14px; }
    .mf-btn-ghost { background: transparent; color: var(--mf-text, #f1f5f9); }
    .mf-btn-primary { background: var(--mf-primary, #7c3aed); color: #fff; }
    .mf-btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
  `],
})
export class KbCreateDialogComponent {
  private readonly kbService = inject(KnowledgeBaseService);
  readonly dialogRef = inject(DialogRef);
  private readonly snackbarService = inject(MfSnackbarService);
  readonly data = inject(DIALOG_DATA, { optional: true });

  readonly name = signal('');
  readonly description = signal('');
  readonly promptLocale = signal('pl');

  readonly isValid = computed(() =>
    this.name().trim().length > 0 &&
    this.name().length <= 200 &&
    this.description().length <= 2000,
  );

  create() {
    if (!this.isValid()) return;
    this.kbService.create({
      name: this.name(),
      description: this.description(),
      prompt_locale: this.promptLocale(),
    }).subscribe({
      next: kb => this.dialogRef.close(kb),
      error: (err: Error) => this.snackbarService.show(err.message, 'error'),
    });
  }
}
