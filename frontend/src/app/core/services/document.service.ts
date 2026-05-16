import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import type {
  DocumentResponse,
  UploadResponse,
  ReprocessRequest,
  TaskStatusResponse,
} from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class DocumentService {
  private readonly api = inject(ApiService);

  list(kbId: string): Observable<DocumentResponse[]> {
    return this.api.get<DocumentResponse[]>(`/api/knowledge-bases/${kbId}/documents`);
  }

  get(kbId: string, documentId: string): Observable<DocumentResponse> {
    return this.api.get<DocumentResponse>(`/api/knowledge-bases/${kbId}/documents/${documentId}`);
  }

  upload(kbId: string, file: File): Observable<UploadResponse> {
    const form = new FormData();
    form.append('file', file, file.name);
    return this.api.uploadFile<UploadResponse>(`/api/knowledge-bases/${kbId}/documents`, form);
  }

  reprocess(kbId: string, documentId: string, req: ReprocessRequest): Observable<TaskStatusResponse> {
    return this.api.post<TaskStatusResponse>(
      `/api/knowledge-bases/${kbId}/documents/${documentId}/reprocess`,
      req,
    );
  }

  delete(kbId: string, documentId: string): Observable<void> {
    return this.api.delete<void>(`/api/knowledge-bases/${kbId}/documents/${documentId}`);
  }
}
