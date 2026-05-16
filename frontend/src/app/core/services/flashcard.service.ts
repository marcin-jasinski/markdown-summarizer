import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import type {
  FlashcardResponse,
  ReviewRequest,
  DueCountResponse,
} from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class FlashcardService {
  private readonly api = inject(ApiService);

  getDueCards(kbId: string): Observable<FlashcardResponse[]> {
    return this.api.get<FlashcardResponse[]>(`/api/knowledge-bases/${kbId}/flashcards/due`);
  }

  getAllCards(kbId: string, lessonId?: string): Observable<FlashcardResponse[]> {
    const url = lessonId
      ? `/api/knowledge-bases/${kbId}/flashcards?lesson_id=${lessonId}`
      : `/api/knowledge-bases/${kbId}/flashcards`;
    return this.api.get<FlashcardResponse[]>(url);
  }

  reviewCard(kbId: string, req: ReviewRequest): Observable<void> {
    return this.api.post<void>(`/api/knowledge-bases/${kbId}/flashcards/${req.card_id}/review`, req);
  }

  getDueCount(kbId: string): Observable<DueCountResponse> {
    return this.api.get<DueCountResponse>(`/api/knowledge-bases/${kbId}/flashcards/due/count`);
  }
}
