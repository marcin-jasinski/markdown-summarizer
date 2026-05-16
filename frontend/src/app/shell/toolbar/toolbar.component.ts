import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  input,
  output,
} from '@angular/core';
import { Router } from '@angular/router';
import {
  LucideAngularModule,
  LUCIDE_ICONS,
  LucideIconProvider,
  PanelLeftClose,
  PanelLeftOpen,
  Sun,
  Moon,
} from 'lucide-angular';

import { ThemeService } from '../../core/services/theme.service';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-toolbar',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    LucideAngularModule,
  ],
  providers: [
    { provide: LUCIDE_ICONS, multi: true, useValue: new LucideIconProvider({ PanelLeftClose, PanelLeftOpen, Sun, Moon }) },
  ],
  templateUrl: './toolbar.component.html',
  styleUrl: './toolbar.component.scss',
})
export class ToolbarComponent {
  protected readonly themeService = inject(ThemeService);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  sidebarCollapsed = input(false);
  userDisplayName = input('');
  sidebarToggle = output<void>();

  dropdownOpen = signal(false);

  onToggleSidebar(): void {
    this.sidebarToggle.emit();
  }

  onToggleTheme(): void {
    this.themeService.toggle();
  }

  onLogout(): void {
    this.authService.logout().subscribe();
    this.router.navigate(['/login']);
  }

  getInitials(): string {
    const name = this.userDisplayName();
    return name.length > 0 ? name.charAt(0).toUpperCase() : 'U';
  }
}
