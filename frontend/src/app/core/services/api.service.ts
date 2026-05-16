import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { UserStatsResponse } from '../models/api.models';

/** Base HTTP client. All HTTP integration in MindForge flows through this service. */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);

  get<T>(path: string): Observable<T> {
    return this.http.get<T>(path).pipe(catchError(this.handleError));
  }

  post<T>(path: string, body: unknown): Observable<T> {
    return this.http.post<T>(path, body).pipe(catchError(this.handleError));
  }

  put<T>(path: string, body: unknown): Observable<T> {
    return this.http.put<T>(path, body).pipe(catchError(this.handleError));
  }

  patch<T>(path: string, body: unknown): Observable<T> {
    return this.http.patch<T>(path, body).pipe(catchError(this.handleError));
  }

  delete<T>(path: string): Observable<T> {
    return this.http.delete<T>(path).pipe(catchError(this.handleError));
  }

  uploadFile<T>(path: string, formData: FormData): Observable<T> {
    return this.http.post<T>(path, formData).pipe(catchError(this.handleError));
  }

  getMyStats(): Observable<UserStatsResponse> {
    return this.http.get<UserStatsResponse>('/api/v1/users/me/stats');
  }

  private handleError(error: HttpErrorResponse): Observable<never> {
    let message = 'An unexpected error occurred';
    if (error.status === 0) {
      message = 'Network error — unable to connect to server';
    } else if (error.error?.detail) {
      message = Array.isArray(error.error.detail)
        ? error.error.detail.map((d: { msg: string }) => d.msg).join(', ')
        : String(error.error.detail);
    } else if (error.message) {
      message = error.message;
    }
    return throwError(() => new Error(message));
  }
}
