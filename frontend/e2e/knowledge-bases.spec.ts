/**
 * E2E: Knowledge Base API endpoints
 *
 * Tests KB CRUD endpoints and the /lessons sub-resource that was previously
 * broken (404) and is now fixed.
 */
import { test, expect } from '@playwright/test';

const API = 'http://localhost:8080';

test.describe('Knowledge Base API endpoints', () => {
  test('GET /api/knowledge-bases returns 401 when unauthenticated', async ({ request }) => {
    const res = await request.get(`${API}/api/knowledge-bases`);
    expect(res.status()).toBe(401);
  });

  test('GET /api/knowledge-bases/:id/lessons returns 401 when unauthenticated', async ({ request }) => {
    const res = await request.get(`${API}/api/knowledge-bases/00000000-0000-0000-0000-000000000000/lessons`);
    // Before the fix this returned 404; after the fix it must return 401 (route exists, auth required)
    expect(res.status()).toBe(401);
  });

  test('GET /api/knowledge-bases/:id/lessons route exists (not 404)', async ({ request }) => {
    const res = await request.get(`${API}/api/knowledge-bases/00000000-0000-0000-0000-000000000000/lessons`);
    // Any response other than 404 means the route is registered
    expect(res.status()).not.toBe(404);
  });
});
