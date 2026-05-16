import { readdirSync, readFileSync } from 'fs';
import { resolve, join } from 'path';

function getAllFiles(dir: string, ext: string): string[] {
  const results: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory() && !entry.name.startsWith('.') && entry.name !== 'node_modules') {
      results.push(...getAllFiles(full, ext));
    } else if (entry.isFile() && entry.name.endsWith(ext)) {
      results.push(full);
    }
  }
  return results;
}

it('Test 1: no mat-* element selectors in HTML templates', () => {
  const appDir = resolve(__dirname, '../app');
  const htmlFiles = getAllFiles(appDir, '.html');
  const matUsages: string[] = [];
  for (const file of htmlFiles) {
    const content = readFileSync(file, 'utf-8');
    // Match <mat-* opening tags
    const matches = content.match(/<mat-[a-z-]+/g);
    if (matches) {
      matUsages.push(`${file}: ${matches.join(', ')}`);
    }
  }
  expect(matUsages).toEqual([]);
});

it('Test 2: @angular/cdk is present in package.json', () => {
  const pkg = JSON.parse(readFileSync(resolve(__dirname, '../../package.json'), 'utf-8'));
  const hasCdk = !!pkg.dependencies?.['@angular/cdk'] || !!pkg.devDependencies?.['@angular/cdk'];
  expect(hasCdk).toBe(true);
});

it('Test 3: no @angular/material imports remain in component TS files', () => {
  const appDir = resolve(__dirname, '../app');
  const tsFiles = getAllFiles(appDir, '.ts');
  const matImports: string[] = [];
  for (const file of tsFiles) {
    const content = readFileSync(file, 'utf-8');
    if (content.includes("from '@angular/material")) {
      matImports.push(file);
    }
  }
  expect(matImports).toEqual([]);
});
