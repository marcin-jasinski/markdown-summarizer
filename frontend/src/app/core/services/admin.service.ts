import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import type { InteractionResponse, SystemMetricsResponse } from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class AdminService {
  private readonly api = inject(ApiService);

  getMetrics(): Observable<SystemMetricsResponse> {
    return this.api.get<SystemMetricsResponse>('/api/admin/metrics');
  }

  getInteractions(): Observable<InteractionResponse[]> {
    return this.api.get<InteractionResponse[]>('/api/admin/interactions');
  }
}
