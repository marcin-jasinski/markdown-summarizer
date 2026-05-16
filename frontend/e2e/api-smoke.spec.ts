/**
 * E2E: Core API endpoint reachability
 *
 * Smoke tests that verify all major API endpoints respond (auth/404 vs truly
 * missing). Covers: interactions, admin, search, quiz, chat, concepts, health.
 */
import { test, expect } from '@playwright/test';

const API = 'http://localhost:8080';
const KB_ID = '00000000-0000-0000-0000-000000000000';

test.describe('API endpoint reachability', () => {
  test('GET /api/health returns 200', async ({ request }) => {
    const res = await request.get(`${API}/api/health`);
    expect(res.status()).toBe(200);
  });

  test('GET /api/interactions requires auth (not 404)', async ({ request }) => {
    const res = await request.get(`${API}/api/interactions`);
    expect(res.status()).not.toBe(404);
    expect(res.status()).toBe(401);
  });

  test('GET /api/admin/metrics requires auth (not 404)', async ({ request }) => {
    const res = await request.get(`${API}/api/admin/metrics`);
    expect(res.status()).not.toBe(404);
    expect([401, 403]).toContain(res.status());
  });

  test('GET /api/admin/interactions requires auth (not 404)', async ({ request }) => {
    const res = await request.get(`${API}/api/admin/interactions`);
    expect(res.status()).not.toBe(404);
    expect([401, 403]).toContain(res.status());
  });

  test('POST /api/auth/refresh returns 401 without refresh cookie', async ({ request }) => {
    const res = await request.post(`${API}/api/auth/refresh`);
    expect([401, 403]).toContain(res.status());
  });

  test('GET /api/knowledge-bases/:id/concepts requires auth (not 404)', async ({ request }) => {
    const res = await request.get(`${API}/api/knowledge-bases/${KB_ID}/concepts`);
    expect(res.status()).not.toBe(404);
  });

  test('POST /api/knowledge-bases/:id/quiz/start requires auth (not 404)', async ({ request }) => {
    const res = await request.post(`${API}/api/knowledge-bases/${KB_ID}/quiz/start`, { data: {} });
    expect(res.status()).not.toBe(404);
  });

  test('POST /api/knowledge-bases/:id/search requires auth (not 404)', async ({ request }) => {
    const res = await request.post(`${API}/api/knowledge-bases/${KB_ID}/search`, { data: { query: 'test' } });
    expect(res.status()).not.toBe(404);
  });
});
