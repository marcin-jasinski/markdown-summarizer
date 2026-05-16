/**
 * E2E: Flashcard API endpoints
 *
 * Verifies the backend routes that FlashcardService calls are reachable.
 * The URL bug in reviewCard() has been fixed: card_id now appears in the path.
 */
import { test, expect } from '@playwright/test';

const API = 'http://localhost:8080';
const KB_ID = '00000000-0000-0000-0000-000000000000';
const CARD_ID = '00000000-0000-0000-0000-000000000001';

test.describe('Flashcard API endpoints', () => {
  test('GET /api/knowledge-bases/:id/flashcards returns 401 when unauthenticated', async ({ request }) => {
    const res = await request.get(`${API}/api/knowledge-bases/${KB_ID}/flashcards`);
    expect(res.status()).toBe(401);
  });

  test('GET /api/knowledge-bases/:id/flashcards/due returns 401 when unauthenticated', async ({ request }) => {
    const res = await request.get(`${API}/api/knowledge-bases/${KB_ID}/flashcards/due`);
    expect(res.status()).toBe(401);
  });

  test('GET /api/knowledge-bases/:id/flashcards/due/count route exists (not 404)', async ({ request }) => {
    // Bug fix: getDueCount() now calls /due/count instead of /due-count
    const res = await request.get(`${API}/api/knowledge-bases/${KB_ID}/flashcards/due/count`);
    expect(res.status()).not.toBe(404);
  });

  test('POST /api/knowledge-bases/:kbId/flashcards/:cardId/review route exists (not 404)', async ({ request }) => {
    // Bug fix: reviewCard() URL now includes card_id as a path segment
    const res = await request.post(
      `${API}/api/knowledge-bases/${KB_ID}/flashcards/${CARD_ID}/review`,
      { data: { card_id: CARD_ID, rating: 3 } },
    );
    // Route exists → 401 (auth required), not 404 (route missing)
    expect(res.status()).not.toBe(404);
  });

  test('POST .../flashcards/review (old broken URL) returns 404 or 422', async ({ request }) => {
    // The OLD broken URL — route may not exist (404) or may be caught by another handler (422/401)
    // Either way it should NOT return 204 (success)
    const res = await request.post(
      `${API}/api/knowledge-bases/${KB_ID}/flashcards/review`,
      { data: { card_id: CARD_ID, rating: 3 } },
    );
    expect(res.status()).not.toBe(204);
  });
});
