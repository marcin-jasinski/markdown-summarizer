/**
 * E2E: Auth flow
 *
 * Tests authentication endpoints through the Angular frontend.
 * Credentials are loaded from environment variables:
 *   E2E_USER_EMAIL    — test account email
 *   E2E_USER_PASSWORD — test account password
 *
 * These tests can run against the dev stack (frontend :4200, API :8080).
 */
import { test, expect } from '@playwright/test';

const EMAIL = process.env['E2E_USER_EMAIL'] ?? '';
const PASSWORD = process.env['E2E_USER_PASSWORD'] ?? '';

test.describe('Auth API endpoints', () => {
  test('GET /api/auth/me returns 401 when unauthenticated', async ({ request }) => {
    const res = await request.get('http://localhost:8080/api/auth/me');
    expect(res.status()).toBe(401);
  });

  test('POST /api/auth/login with invalid credentials returns 401', async ({ request }) => {
    const res = await request.post('http://localhost:8080/api/auth/login', {
      data: { email: 'nonexistent@example.com', password: 'wrong' },
    });
    expect([401, 422]).toContain(res.status());
  });

  test.skip(!EMAIL || !PASSWORD, 'Set E2E_USER_EMAIL and E2E_USER_PASSWORD to run login tests');

  test('login page is accessible', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('form, [data-testid="login-form"], input[type="email"]')).toBeVisible({ timeout: 10_000 });
  });

  test('unauthenticated root redirects to /login', async ({ page }) => {
    await page.goto('/');
    await page.waitForURL('**/login', { timeout: 10_000 });
    expect(page.url()).toContain('/login');
  });
});
