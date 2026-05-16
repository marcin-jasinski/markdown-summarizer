import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { ApiService } from '../app/core/services/api.service';

describe('ApiService', () => {
  let service: ApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), ApiService],
    });
    service = TestBed.inject(ApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('should issue a GET request', () => {
    service.get<{ ok: boolean }>('/api/health').subscribe((res: { ok: boolean }) => expect(res.ok).toBe(true));
    const req = http.expectOne('/api/health');
    expect(req.request.method).toBe('GET');
    req.flush({ ok: true });
  });

  it('should issue a POST request', () => {
    service.post<{ id: string }>('/api/knowledge-bases', { name: 'Test' }).subscribe();
    const req = http.expectOne('/api/knowledge-bases');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ name: 'Test' });
    req.flush({ id: 'abc' });
  });

  it('should surface a human-readable error message on failure', () => {
    return new Promise<void>(resolve => {
      service.get('/api/fail').subscribe({
        error: (err: Error) => {
          expect(err.message).toContain('not found');
          resolve();
        },
      });
      http.expectOne('/api/fail').flush({ detail: 'not found' }, { status: 404, statusText: 'Not Found' });
    });
  });
});
