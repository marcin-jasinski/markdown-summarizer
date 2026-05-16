import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import type { ConceptGraphResponse } from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class ConceptService {
  private readonly api = inject(ApiService);

  getGraph(kbId: string): Observable<ConceptGraphResponse> {
    return this.api.get<ConceptGraphResponse>(`/api/knowledge-bases/${kbId}/concepts`);
  }
}
