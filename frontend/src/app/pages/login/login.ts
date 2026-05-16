import { Component, ChangeDetectionStrategy, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { MfSnackbarService } from '../../core/services/mf-snackbar.service';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CommonModule, FormsModule],
  templateUrl: './login.html',
  styleUrl: './login.scss',
})
export class LoginComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly snackbarService = inject(MfSnackbarService);

  readonly isLogin = signal(true);
  readonly email = signal('');
  readonly password = signal('');
  readonly isLoading = signal(false);
  readonly discordEnabled = signal(true);
  readonly discordOauthUrl = signal('/api/auth/login/discord');

  onSubmit() {
    if (!this.email() || !this.password()) return;
    this.isLoading.set(true);

    const action = this.isLogin()
      ? this.auth.login({ email: this.email(), password: this.password() })
      : this.auth.register({
          email: this.email(),
          password: this.password(),
          display_name: this.email().split('@')[0],
        });

    action.subscribe({
      next: () => this.router.navigate(['/dashboard']),
      error: (err: Error) => {
        this.snackbarService.show(err.message, 'error');
        this.isLoading.set(false);
      },
    });
  }
}
