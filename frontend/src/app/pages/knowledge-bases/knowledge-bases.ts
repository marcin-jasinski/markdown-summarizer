import {
  Component,
  OnInit,
  ChangeDetectionStrategy,
  inject,
  signal,
} from '@angular/core';
import { Router } from '@angular/router';
import { Dialog } from '@angular/cdk/dialog';
import { MfSnackbarService } from '../../core/services/mf-snackbar.service';
import { KnowledgeBaseService } from '../../core/services/knowledge-base.service';
import { KbCreateDialogComponent } from '../dashboard/kb-create-dialog';
import type { KnowledgeBaseResponse } from '../../core/models/api.models';

@Component({
  selector: 'app-knowledge-bases',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [],
  templateUrl: './knowledge-bases.html',
  styleUrl: './knowledge-bases.scss',
})
export class KnowledgeBasesComponent implements OnInit {
  private readonly kbService = inject(KnowledgeBaseService);
  private readonly dialog = inject(Dialog);
  private readonly snackbarService = inject(MfSnackbarService);
  readonly router = inject(Router);

  readonly kbs = signal<KnowledgeBaseResponse[]>([]);
  readonly isLoading = signal(true);

  ngOnInit() {
    this.load();
  }

  load() {
    this.isLoading.set(true);
    this.kbService.list().subscribe({
      next: kbs => { this.kbs.set(kbs); this.isLoading.set(false); },
      error: () => this.isLoading.set(false),
    });
  }

  openCreateDialog() {
    this.dialog.open(KbCreateDialogComponent, { width: '440px' })
      .closed.subscribe(res => { if (res) this.load(); });
  }

  navigateToKb(id: string) {
    this.router.navigate(['/kb', id, 'documents']);
  }

  deleteKb(kb: KnowledgeBaseResponse, event: MouseEvent) {
    event.stopPropagation();
    if (!confirm(`Delete "${kb.name}"? This cannot be undone.`)) return;
    this.kbService.delete(kb.kb_id).subscribe({
      next: () => { this.snackbarService.show('Knowledge base deleted', 'success'); this.load(); },
      error: (err: Error) => this.snackbarService.show(err.message, 'error'),
    });
  }
}
