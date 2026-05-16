import {
  Component,
  OnInit,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
  DestroyRef,
} from '@angular/core';
import {
  Router,
  RouterOutlet,
  NavigationEnd,
} from '@angular/router';
import { BreakpointObserver } from '@angular/cdk/layout';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { filter } from 'rxjs/operators';
import { AuthService } from '../core/services/auth.service';
import { ToolbarComponent } from './toolbar/toolbar.component';
import { SidebarComponent } from './sidebar/sidebar.component';

@Component({
  selector: 'app-shell',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    RouterOutlet,
    ToolbarComponent, SidebarComponent,
  ],
  templateUrl: './shell.html',
  styleUrl: './shell.scss',
})
export class ShellComponent implements OnInit {
  protected readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly bp = inject(BreakpointObserver);
  private readonly destroyRef = inject(DestroyRef);

  readonly isMobile = signal(false);
  readonly sidebarCollapsed = signal(false);
  readonly currentKbId = signal<string | null>(null);
  readonly userName = computed(() => this.auth.user()?.display_name ?? '');

  constructor() {
    this.router.events
      .pipe(
        filter(e => e instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe(e => {
        const url = (e as NavigationEnd).urlAfterRedirects;
        const match = url.match(/\/kb\/([^/?#]+)/);
        this.currentKbId.set(match ? match[1] : null);
        if (this.isMobile()) {
          this.sidebarCollapsed.set(true);
        }
      });
  }

  ngOnInit(): void {
    this.bp
      .observe(['(max-width: 768px)'])
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(state => {
        this.isMobile.set(state.matches);
      });

    const match = this.router.url.match(/\/kb\/([^/?#]+)/);
    this.currentKbId.set(match ? match[1] : null);
  }

  onSidebarToggle(): void {
    this.sidebarCollapsed.update(v => !v);
  }

  logout(): void {
    this.auth.logout().subscribe();
  }
}
