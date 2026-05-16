import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import type {
  ChatSessionResponse,
  ChatMessageRequest,
  ChatMessageResponse,
} from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class ChatService {
  private readonly api = inject(ApiService);

  startSession(kbId: string): Observable<ChatSessionResponse> {
    return this.api.post<ChatSessionResponse>('/api/chat/sessions', {
      knowledge_base_id: kbId,
    });
  }

  sendMessage(sessionId: string, req: ChatMessageRequest): Observable<ChatMessageResponse> {
    return this.api.post<ChatMessageResponse>(`/api/chat/sessions/${sessionId}/messages`, req);
  }

  listSessions(kbId: string): Observable<ChatSessionResponse[]> {
    return this.api.get<ChatSessionResponse[]>(`/api/chat/sessions?kb_id=${kbId}`);
  }

  getSession(sessionId: string): Observable<ChatSessionResponse> {
    return this.api.get<ChatSessionResponse>(`/api/chat/sessions/${sessionId}`);
  }
}
