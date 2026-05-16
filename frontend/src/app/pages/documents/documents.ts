import {
  Component,
  ElementRef,
  OnInit,
  OnDestroy,
  ChangeDetectionStrategy,
  inject,
  signal,
  ViewChild,
} from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { DatePipe } from '@angular/common';
import { Subscription } from 'rxjs';
import { MfSnackbarService } from '../../core/services/mf-snackbar.service';
import { DocumentService } from '../../core/services/document.service';
import { EventService } from '../../core/services/event.service';
import type { DocumentResponse } from '../../core/models/api.models';

@Component({
  selector: 'app-documents',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe],
  templateUrl: './documents.html',
  styleUrl: './documents.scss',
})
export class DocumentsComponent implements OnInit, OnDestroy {
  @ViewChild('fileInput') private fileInput?: ElementRef<HTMLInputElement>;

  private readonly route = inject(ActivatedRoute);
  private readonly docService = inject(DocumentService);
  private readonly eventService = inject(EventService);
  private readonly snackbarService = inject(MfSnackbarService);

  readonly kbId = signal('');
  readonly documents = signal<DocumentResponse[]>([]);
  readonly isLoading = signal(true);
  readonly uploading = signal(false);
  readonly isDragOver = signal(false);

  private eventSub?: Subscription;

  ngOnInit() {
    const kbId = this.route.snapshot.paramMap.get('kbId') ?? '';
    this.kbId.set(kbId);
    this.loadDocuments();
    this.subscribeToEvents();
  }

  ngOnDestroy() {
    this.eventSub?.unsubscribe();
  }

  loadDocuments() {
    this.isLoading.set(true);
    this.docService.list(this.kbId()).subscribe({
      next: docs => { this.documents.set(docs); this.isLoading.set(false); },
      error: () => this.isLoading.set(false),
    });
  }

  private subscribeToEvents() {
    this.eventSub = this.eventService.connect(this.kbId()).subscribe(evt => {
      if (['PipelineStepCompleted', 'ProcessingCompleted', 'ProcessingFailed'].includes(evt.event_type)) {
        this.loadDocuments();
      }
    });
  }

  onDragOver(event: DragEvent) {
    event.preventDefault();
    this.isDragOver.set(true);
  }

  onDragLeave() {
    this.isDragOver.set(false);
  }

  onDrop(event: DragEvent) {
    event.preventDefault();
    this.isDragOver.set(false);
    const files = event.dataTransfer?.files;
    if (files?.length) {
      this.uploadFiles(Array.from(files));
    }
  }

  onFileInput(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files?.length) {
      this.uploadFiles(Array.from(input.files));
      input.value = '';
    }
  }

  openUpload() {
    this.fileInput?.nativeElement.click();
  }

  onFileSelect(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files?.length) {
      this.uploadFiles(Array.from(input.files));
      input.value = '';
    }
  }

  private uploadFiles(files: File[]) {
    this.uploading.set(true);
    let completed = 0;
    for (const file of files) {
      this.docService.upload(this.kbId(), file).subscribe({
        next: resp => {
          this.snackbarService.show(`"${file.name}" queued for processing (task: ${resp.task_id.slice(0, 8)}…)`, 'success');
          completed++;
          if (completed === files.length) {
            this.uploading.set(false);
            this.loadDocuments();
          }
        },
        error: (err: Error) => {
          this.snackbarService.show(err.message, 'error');
          completed++;
          if (completed === files.length) this.uploading.set(false);
        },
      });
    }
  }

  reprocess(docId: string) {
    this.docService.reprocess(this.kbId(), docId, { force: true }).subscribe({
      next: () => { this.snackbarService.show('Reprocessing queued', 'info'); this.loadDocuments(); },
      error: (err: Error) => this.snackbarService.show(err.message, 'error'),
    });
  }

  deleteDocument(docId: string) {
    this.docService.delete(this.kbId(), docId).subscribe({
      next: () => { this.snackbarService.show('Dokument usunięty', 'success'); this.loadDocuments(); },
      error: (err: Error) => this.snackbarService.show(err.message, 'error'),
    });
  }
}
