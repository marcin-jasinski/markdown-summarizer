import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import type { TaskStatusResponse } from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class TaskService {
  private readonly api = inject(ApiService);

  getStatus(taskId: string): Observable<TaskStatusResponse> {
    return this.api.get<TaskStatusResponse>(`/api/tasks/${taskId}`);
  }
}
