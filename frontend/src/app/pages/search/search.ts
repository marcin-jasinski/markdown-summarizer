import {
  Component,
  OnInit,
  ChangeDetectionStrategy,
  inject,
  signal,
} from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { MfSnackbarService } from '../../core/services/mf-snackbar.service';
import { SearchService } from '../../core/services/search.service';
import type { SearchResultItem } from '../../core/models/api.models';

@Component({
  selector: 'app-search',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [],
  templateUrl: './search.html',
  styleUrl: './search.scss',
})
export class SearchComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly searchService = inject(SearchService);
  private readonly snackbarService = inject(MfSnackbarService);

  readonly kbId = signal('');
  readonly query = signal('');
  readonly results = signal<SearchResultItem[]>([]);
  readonly isLoading = signal(false);
  readonly activeFilters = signal<string[]>([]);
  readonly hasSearched = signal(false);

  ngOnInit() {
    this.kbId.set(this.route.snapshot.paramMap.get('kbId') ?? '');
  }

  search() {
    const q = this.query().trim();
    if (!q) return;
    this.isLoading.set(true);
    this.hasSearched.set(true);
    this.searchService.search(this.kbId(), { query: q, top_k: 10 }).subscribe({
      next: resp => { this.results.set(resp.results); this.isLoading.set(false); },
      error: (err: Error) => { this.snackbarService.show(err.message, 'error'); this.isLoading.set(false); },
    });
  }

  removeFilter(filter: string) {
    this.activeFilters.update(filters => filters.filter(f => f !== filter));
  }
}
