import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import type { SearchRequest, SearchResponse } from '../models/api.models';

@Injectable({ providedIn: 'root' })
export class SearchService {
  private readonly api = inject(ApiService);

  search(kbId: string, req: SearchRequest): Observable<SearchResponse> {
    return this.api.post<SearchResponse>(`/api/knowledge-bases/${kbId}/search`, req);
  }
}
