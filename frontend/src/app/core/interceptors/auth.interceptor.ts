import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

/**
 * Attaches `withCredentials: true` to every request so HttpOnly cookies are
 * sent automatically. Redirects to /login on 401 responses (except the
 * login/register endpoints themselves to avoid redirect loops).
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);

  const withCreds = req.clone({ withCredentials: true });

  return next(withCreds).pipe(
    catchError(error => {
      const isAuthEndpoint =
        req.url.includes('/login') || req.url.includes('/register');
      if (error.status === 401 && !isAuthEndpoint) {
        router.navigate(['/login']);
      }
      return throwError(() => error);
    }),
  );
};
