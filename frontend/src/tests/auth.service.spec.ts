import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { AuthService } from '../app/core/services/auth.service';

describe('AuthService', () => {
  let service: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        AuthService,
      ],
    });
    service = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('should start unauthenticated', () => {
    expect(service.isAuthenticated()).toBe(false);
    expect(service.user()).toBeNull();
  });

  it('should set user on successful loadCurrentUser()', () => {
    const mockUser = { user_id: 'u1', display_name: 'Alice', email: 'alice@test.com', avatar_url: null, created_at: '' };
    service.loadCurrentUser().subscribe();
    http.expectOne('/api/auth/me').flush(mockUser);
    expect(service.user()?.display_name).toBe('Alice');
    expect(service.isAuthenticated()).toBe(true);
  });

  it('should clear user on 401', () => {
    service.loadCurrentUser().subscribe();
    http.expectOne('/api/auth/me').flush(null, { status: 401, statusText: 'Unauthorized' });
    expect(service.user()).toBeNull();
    expect(service.isAuthenticated()).toBe(false);
  });
});
