import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { describe, it, expect, beforeEach } from 'vitest';

import { ApiService } from '../../core/services/api.service';
import { SidebarComponent } from './sidebar.component';

@Component({
  standalone: true,
  template: '',
})
class DummyRouteComponent {}

describe('SidebarComponent', () => {
  let router: Router;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SidebarComponent],
      providers: [
        provideRouter([
          { path: 'dashboard', component: DummyRouteComponent },
          { path: 'knowledge-bases', component: DummyRouteComponent },
          { path: 'kb/:kbId/documents', component: DummyRouteComponent },
          { path: 'kb/:kbId/concepts', component: DummyRouteComponent },
          { path: 'kb/:kbId/quiz', component: DummyRouteComponent },
          { path: 'kb/:kbId/flashcards', component: DummyRouteComponent },
        ]),
        {
          provide: ApiService,
          useValue: {
            getMyStats: () => of({ streak_days: 3, due_today: 2 }),
          },
        },
      ],
    }).compileComponents();

    router = TestBed.inject(Router);
  });

  it('shows only global navigation when no knowledge base is selected', async () => {
    await router.navigateByUrl('/knowledge-bases');

    const fixture = TestBed.createComponent(SidebarComponent);
    fixture.detectChanges();
    await fixture.whenStable();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';

    expect(text).toContain('Pulpit');
    expect(text).toContain('Bazy wiedzy');
    expect(text).not.toContain('Quiz');
    expect(text).not.toContain('Flashcards');
    expect(text).not.toContain('Concept map');
  });

  it('shows quiz, flashcards and concept-map links after opening a knowledge base', async () => {
    await router.navigateByUrl('/kb/kb-123/documents');

    const fixture = TestBed.createComponent(SidebarComponent);
    fixture.componentRef.setInput('currentKbId', 'kb-123');
    fixture.detectChanges();
    await fixture.whenStable();

    const links = Array.from(
      (fixture.nativeElement as HTMLElement).querySelectorAll('a.mf-nav-item'),
    ).map(anchor => anchor.getAttribute('href') ?? '');

    expect(links).toContain('/kb/kb-123/quiz');
    expect(links).toContain('/kb/kb-123/flashcards');
    expect(links).toContain('/kb/kb-123/concepts');
  });
});
