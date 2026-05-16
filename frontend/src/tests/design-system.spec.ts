/**
 * Design System Tests — design-tokens.css + styles.scss
 *
 * Verify that the design token file exists with canonical values and that
 * styles.scss uses the correct selective Tailwind imports (no Preflight).
 *
 * @vitest-environment node
 */
import { describe, it, expect } from 'vitest';
import { readFileSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const FRONTEND_SRC = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const TOKENS_FILE = resolve(FRONTEND_SRC, 'app/core/styles/design-tokens.css');
const STYLES_FILE = resolve(FRONTEND_SRC, 'styles.scss');

describe('Design System — design-tokens.css', () => {
  it('design-tokens.css defines --mf-primary: #5B4FE9 in :root', () => {
    expect(
      existsSync(TOKENS_FILE),
      `design-tokens.css must exist at ${TOKENS_FILE}`,
    ).toBe(true);

    const content = readFileSync(TOKENS_FILE, 'utf-8');
    expect(
      content,
      'design-tokens.css :root block must define --mf-primary: #5B4FE9',
    ).toMatch(/--mf-primary:\s*#5B4FE9/);
  });

  it('[data-theme="dark"] block overrides --mf-surface-1 to #1C1B23', () => {
    expect(
      existsSync(TOKENS_FILE),
      `design-tokens.css must exist at ${TOKENS_FILE}`,
    ).toBe(true);

    const content = readFileSync(TOKENS_FILE, 'utf-8');

    // Locate the dark-mode block
    const darkBlockMatch = content.match(/\[data-theme="dark"\]\s*\{([^}]+)\}/s);
    expect(
      darkBlockMatch,
      'design-tokens.css must contain a [data-theme="dark"] block',
    ).not.toBeNull();

    const darkBlock = darkBlockMatch![1];
    expect(
      darkBlock,
      '[data-theme="dark"] block must override --mf-surface-1 to #1C1B23',
    ).toMatch(/--mf-surface-1:\s*#1C1B23/);
  });
});

describe('Design System — styles.scss', () => {
  it('styles.scss uses Tailwind v4 full import with @theme customisation', () => {
    expect(
      existsSync(STYLES_FILE),
      `styles.scss must exist at ${STYLES_FILE}`,
    ).toBe(true);

    const content = readFileSync(STYLES_FILE, 'utf-8');

    expect(
      content,
      'styles.scss must import tailwindcss (Tailwind v4 full bundle)',
    ).toMatch(/@import\s+["']tailwindcss["']/);

    expect(
      content,
      'styles.scss must import the MindForge design-tokens.css',
    ).toMatch(/@import\s+["'][^"']*design-tokens\.css["']/);

    expect(
      content,
      'styles.scss must contain a @theme block to map MF tokens to Tailwind colours',
    ).toMatch(/@theme\s*\{/);
  });
});
