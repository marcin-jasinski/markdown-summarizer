import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import type { InteractionResponse } from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class InteractionsService {
  private readonly api = inject(ApiService);

  list(): Observable<InteractionResponse[]> {
    return this.api.get<InteractionResponse[]>('/api/interactions');
  }
}
