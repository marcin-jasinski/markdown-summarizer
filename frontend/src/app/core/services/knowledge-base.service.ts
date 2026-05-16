import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import type {
  KnowledgeBaseCreate,
  KnowledgeBaseUpdate,
  KnowledgeBaseResponse,
  LessonResponse,
} from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class KnowledgeBaseService {
  private readonly api = inject(ApiService);

  list(): Observable<KnowledgeBaseResponse[]> {
    return this.api.get<KnowledgeBaseResponse[]>('/api/knowledge-bases');
  }

  get(kbId: string): Observable<KnowledgeBaseResponse> {
    return this.api.get<KnowledgeBaseResponse>(`/api/knowledge-bases/${kbId}`);
  }

  create(req: KnowledgeBaseCreate): Observable<KnowledgeBaseResponse> {
    return this.api.post<KnowledgeBaseResponse>('/api/knowledge-bases', req);
  }

  update(kbId: string, req: KnowledgeBaseUpdate): Observable<KnowledgeBaseResponse> {
    return this.api.patch<KnowledgeBaseResponse>(`/api/knowledge-bases/${kbId}`, req);
  }

  delete(kbId: string): Observable<void> {
    return this.api.delete<void>(`/api/knowledge-bases/${kbId}`);
  }

  listLessons(kbId: string): Observable<LessonResponse[]> {
    return this.api.get<LessonResponse[]>(`/api/knowledge-bases/${kbId}/lessons`);
  }
}
