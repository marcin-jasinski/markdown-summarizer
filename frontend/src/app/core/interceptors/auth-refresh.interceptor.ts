import { HttpClient, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError } from 'rxjs';

const SKIP_REFRESH_URLS = ['/api/auth/refresh', '/api/auth/login', '/api/auth/register'];

/**
 * Catches 401 responses, attempts a token refresh via POST /api/auth/refresh,
 * then retries the original request once. If the refresh fails, re-throws the
 * original error so authInterceptor can redirect to /login.
 */
export const authRefreshInterceptor: HttpInterceptorFn = (req, next) => {
  const shouldSkip = SKIP_REFRESH_URLS.some(url => req.url.includes(url));

  return next(req).pipe(
    catchError(err => {
      if (err.status !== 401 || shouldSkip) {
        return throwError(() => err);
      }
      const http = inject(HttpClient);
      return http.post('/api/auth/refresh', {}, { withCredentials: true }).pipe(
        switchMap(() => next(req)),
        catchError(() => throwError(() => err)),
      );
    }),
  );
};
