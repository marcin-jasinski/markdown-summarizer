import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs';
import { AuthService } from '../services/auth.service';

/**
 * Protects routes that require authentication.
 * Attempts to load the current user (via the /api/me cookie check) before
 * allowing or blocking navigation.
 */
export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (auth.isAuthenticated()) {
    return true;
  }

  return auth.loadCurrentUser().pipe(
    map(() => auth.isAuthenticated() ? true : router.createUrlTree(['/login'])),
  );
};
