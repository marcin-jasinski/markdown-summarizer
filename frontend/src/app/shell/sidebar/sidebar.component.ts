import {
  Component,
  OnInit,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
  input,
  output,
  effect,
  DestroyRef,
} from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import {
  LucideAngularModule,
  LUCIDE_ICONS,
  LucideIconProvider,
  ChevronsLeft,
  ChevronsRight,
  LayoutDashboard,
  Library,
  ArrowLeft,
} from 'lucide-angular';

import { ApiService } from '../../core/services/api.service';
import type { UserStatsResponse } from '../../core/models/api.models';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterLink,
    LucideAngularModule,
  ],
  providers: [
    { provide: LUCIDE_ICONS, multi: true, useValue: new LucideIconProvider({ ChevronsLeft, ChevronsRight, LayoutDashboard, Library, ArrowLeft }) },
  ],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.scss',
})
export class SidebarComponent implements OnInit {
  private readonly router = inject(Router);
  private readonly apiService = inject(ApiService);
  private readonly destroyRef = inject(DestroyRef);

  isMobile = input(false);
  currentKbId = input<string | null>(null);
  toggle = output<void>();

  sidebarCollapsed = signal(localStorage.getItem('mf-sidebar-collapsed') === 'true');
  stats = signal<UserStatsResponse | null>(null);
  statsLoading = signal(true);

  readonly navItems = computed(() => {
    const kbId = this.currentKbId();

    if (!kbId) {
      return [
        { label: 'Pulpit', icon: 'layout-dashboard', route: '/', isBack: false, isSeparator: false },
        { label: 'Bazy wiedzy', icon: 'library', route: '/knowledge-bases', isBack: false, isSeparator: false },
      ];
    }

    return [
      { label: 'Powrót', icon: 'arrow-left', route: '/knowledge-bases', isBack: true, isSeparator: false },
      { label: '', icon: '', route: '', isBack: false, isSeparator: true },
      { label: 'Dokumenty', icon: 'library', route: `/kb/${kbId}/documents`, isBack: false, isSeparator: false },
      { label: 'Concept map', icon: 'library', route: `/kb/${kbId}/concepts`, isBack: false, isSeparator: false },
      { label: 'Quiz', icon: 'library', route: `/kb/${kbId}/quiz`, isBack: false, isSeparator: false },
      { label: 'Flashcards', icon: 'library', route: `/kb/${kbId}/flashcards`, isBack: false, isSeparator: false },
    ];
  });

  constructor() {
    effect(() => {
      localStorage.setItem('mf-sidebar-collapsed', String(this.sidebarCollapsed()));
    });
  }

  ngOnInit(): void {
    this.apiService
      .getMyStats()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: s => { this.stats.set(s); this.statsLoading.set(false); },
        error: () => this.statsLoading.set(false),
      });
  }

  collapseToggle(): void {
    this.sidebarCollapsed.update(v => !v);
    this.toggle.emit();
  }

  isActive(route: string): boolean {
    return this.router.url === route || (route !== '/' && this.router.url.startsWith(route));
  }
}
