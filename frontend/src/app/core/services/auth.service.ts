import { Injectable, inject, signal, computed } from '@angular/core';
import { Router } from '@angular/router';
import { tap, catchError, of } from 'rxjs';
import { ApiService } from './api.service';
import type { RegisterRequest, LoginRequest, TokenResponse, UserResponse } from '../models/api.models';

/** Manages authentication state using Angular signals. Auth is cookie-based (HttpOnly JWT). */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);

  private readonly _user = signal<UserResponse | null>(null);
  readonly user = this._user.asReadonly();
  readonly isAuthenticated = computed(() => this._user() !== null);

  /** Attempt to load the current user from the API. Silently clears state on 401. */
  loadCurrentUser() {
    return this.api.get<UserResponse>('/api/auth/me').pipe(
      tap(user => this._user.set(user)),
      catchError(() => {
        this._user.set(null);
        return of(null);
      }),
    );
  }

  register(req: RegisterRequest) {
    return this.api.post<TokenResponse>('/api/auth/register', req).pipe(
      tap(() => this.loadCurrentUser().subscribe()),
    );
  }

  login(req: LoginRequest) {
    return this.api.post<TokenResponse>('/api/auth/login', req).pipe(
      tap(() => this.loadCurrentUser().subscribe()),
    );
  }

  /** Redirect to OAuth provider login page. */
  loginWithProvider(provider: string) {
    window.location.href = `/api/auth/login/${provider}`;
  }

  logout() {
    return this.api.post<void>('/api/auth/logout', {}).pipe(
      tap(() => {
        this._user.set(null);
        this.router.navigate(['/login']);
      }),
    );
  }
}
