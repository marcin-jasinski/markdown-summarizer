import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import type {
  StartQuizRequest,
  QuizQuestionResponse,
  SubmitAnswerRequest,
  AnswerEvaluationResponse,
} from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class QuizService {
  private readonly api = inject(ApiService);

  startSession(kbId: string, req: StartQuizRequest = {}): Observable<QuizQuestionResponse> {
    return this.api.post<QuizQuestionResponse>(`/api/knowledge-bases/${kbId}/quiz/start`, req);
  }

  submitAnswer(kbId: string, sessionId: string, req: SubmitAnswerRequest): Observable<AnswerEvaluationResponse> {
    return this.api.post<AnswerEvaluationResponse>(
      `/api/knowledge-bases/${kbId}/quiz/${sessionId}/answer`,
      req,
    );
  }
}
