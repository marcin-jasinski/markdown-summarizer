/**
 * Build System Tests — Tailwind v4 + PostCSS + lucide-angular
 *
 * These tests verify that the build-system dependencies and configuration
 * files are correctly installed and present. They act as a TDD red gate
 * before installation and green gate after.
 *
 * @vitest-environment node
 */
import { describe, it, expect } from 'vitest';
import { existsSync, readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const FRONTEND_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '../..');

describe('Build System — Tailwind v4 + PostCSS + lucide-angular', () => {
  it('tailwindcss and @tailwindcss/postcss are installed as dev dependencies', () => {
    const pkgJson = JSON.parse(readFileSync(resolve(FRONTEND_DIR, 'package.json'), 'utf-8'));
    expect(
      pkgJson.devDependencies,
      'package.json devDependencies must include tailwindcss',
    ).toHaveProperty('tailwindcss');
    expect(
      pkgJson.devDependencies,
      'package.json devDependencies must include @tailwindcss/postcss',
    ).toHaveProperty('@tailwindcss/postcss');
    expect(
      existsSync(resolve(FRONTEND_DIR, 'node_modules/tailwindcss')),
      'tailwindcss must be present in node_modules',
    ).toBe(true);
    expect(
      existsSync(resolve(FRONTEND_DIR, 'node_modules/@tailwindcss/postcss')),
      '@tailwindcss/postcss must be present in node_modules',
    ).toBe(true);
  });

  it('postcss.config.js exists and registers @tailwindcss/postcss (Tailwind v4)', () => {
    const configPath = resolve(FRONTEND_DIR, 'postcss.config.js');
    expect(
      existsSync(configPath),
      'postcss.config.js must exist in the frontend root',
    ).toBe(true);
    const content = readFileSync(configPath, 'utf-8');
    expect(
      content,
      'postcss.config.js must register @tailwindcss/postcss (not legacy tailwindcss)',
    ).toContain('@tailwindcss/postcss');
  });

  it('lucide-angular is installed as a runtime dependency', () => {
    const pkgJson = JSON.parse(readFileSync(resolve(FRONTEND_DIR, 'package.json'), 'utf-8'));
    expect(
      pkgJson.dependencies,
      'package.json dependencies must include lucide-angular',
    ).toHaveProperty('lucide-angular');
    expect(
      existsSync(resolve(FRONTEND_DIR, 'node_modules/lucide-angular')),
      'lucide-angular must be present in node_modules',
    ).toBe(true);
  });
});
