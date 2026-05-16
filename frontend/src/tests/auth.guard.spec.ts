import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { authGuard } from '../app/core/guards/auth.guard';
import { AuthService } from '../app/core/services/auth.service';

@Component({ template: '', standalone: true })
class DummyComponent {}

describe('authGuard', () => {
  let router: Router;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([
          { path: 'protected', canActivate: [authGuard], children: [] },
          { path: 'login', component: DummyComponent },
        ]),
        AuthService,
      ],
    });
    router = TestBed.inject(Router);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('should allow navigation when user is loaded', async () => {
    const auth = TestBed.inject(AuthService);
    auth.loadCurrentUser().subscribe();
    http.expectOne('/api/auth/me').flush({
      user_id: 'u1', display_name: 'Bob', email: null, avatar_url: null, created_at: '',
    });
    const result = await router.navigate(['/protected']);
    expect(result).toBe(true);
  });

  it('should redirect to /login when unauthenticated', async () => {
    const navPromise = router.navigate(['/protected']);
    // Yield so the router/guard can issue the /api/auth/me request
    await new Promise(r => setTimeout(r, 0));
    http.expectOne('/api/auth/me').flush(null, { status: 401, statusText: 'Unauthorized' });
    await navPromise;
    await new Promise(r => setTimeout(r, 0));
    expect(router.url).toBe('/login');
  });
});
