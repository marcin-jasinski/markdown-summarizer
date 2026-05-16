/**
 * Complex Screens Tests — Chat + Concept Map
 * Group 10 — Phase 4 Screen Redesigns
 */
import { TestBed, ComponentFixture } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { ActivatedRoute } from '@angular/router';
import { signal } from '@angular/core';
import { of } from 'rxjs';

import { ChatComponent } from '../app/pages/chat/chat';
import { ConceptMapComponent } from '../app/pages/concept-map/concept-map';
import { ChatService } from '../app/core/services/chat.service';
import { ConceptService } from '../app/core/services/concept.service';
import { MfSnackbarService } from '../app/core/services/mf-snackbar.service';
import { ThemeService } from '../app/core/services/theme.service';

// Mock Cytoscape to avoid canvas errors in jsdom
vi.mock('cytoscape', () => ({
  default: vi.fn(() => ({
    on: vi.fn(),
    style: vi.fn(),
    fit: vi.fn(),
    zoom: vi.fn(() => 1),
  })),
}));

const mockActivatedRoute = {
  snapshot: { paramMap: { get: (_: string) => 'kb-1' } },
};
const mockSnackbar = { show: vi.fn() };

const mockChatService = {
  startSession: () => of({ session_id: 's1' }),
  sendMessage: () => of({ answer: 'Hello', source_concept_keys: [] }),
};

const mockConceptService = {
  getGraph: () => of({ concepts: [], edges: [] }),
};

const mockThemeService = {
  isDark: signal(false),
};

// ---------------------------------------------------------------------------
// ChatComponent
// ---------------------------------------------------------------------------

describe('ChatComponent (redesigned)', () => {
  let fixture: ComponentFixture<ChatComponent>;
  let el: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ChatComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: mockActivatedRoute },
        { provide: ChatService, useValue: mockChatService },
        { provide: MfSnackbarService, useValue: mockSnackbar },
        { provide: ThemeService, useValue: mockThemeService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ChatComponent);
    el = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
  });

  it('Test 1: user message bubble has mf-bubble-user class', () => {
    fixture.componentInstance.messages.set([
      { role: 'user', content: 'Hello' },
    ]);
    fixture.detectChanges();

    const bubble = el.querySelector('.mf-bubble-user') as HTMLElement;
    expect(bubble).not.toBeNull();
    const style = window.getComputedStyle(bubble);
    // class presence is sufficient — CSS is not evaluated in jsdom
    expect(bubble.classList.contains('mf-bubble-user')).toBe(true);
  });

  it('Test 2: assistant message bubble has mf-bubble-assistant class', () => {
    fixture.componentInstance.messages.set([
      { role: 'assistant', content: 'Hi there' },
    ]);
    fixture.detectChanges();

    const bubble = el.querySelector('.mf-bubble-assistant') as HTMLElement;
    expect(bubble).not.toBeNull();
    expect(bubble.classList.contains('mf-bubble-assistant')).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// ConceptMapComponent
// ---------------------------------------------------------------------------

describe('ConceptMapComponent (redesigned)', () => {
  let fixture: ComponentFixture<ConceptMapComponent>;
  let el: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ConceptMapComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: mockActivatedRoute },
        { provide: ConceptService, useValue: mockConceptService },
        { provide: MfSnackbarService, useValue: mockSnackbar },
        { provide: ThemeService, useValue: mockThemeService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ConceptMapComponent);
    el = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
  });

  it('Test 3: isDark computed signal returns false by default', () => {
    const comp = fixture.componentInstance;
    expect(comp.isDark()).toBe(false);
  });

  it('Test 4: setting selectedNode signal makes node data accessible', () => {
    const comp = fixture.componentInstance;
    expect(comp.selectedNode()).toBeNull();

    comp.selectedNode.set({ id: 'n1', label: 'Angular', description: 'A framework' });
    fixture.detectChanges();

    expect(comp.selectedNode()).not.toBeNull();
    expect(comp.selectedNode()?.label).toBe('Angular');
  });

  it('Test 5: when selectedNode is set, panel is rendered in DOM', () => {
    const comp = fixture.componentInstance;

    comp.selectedNode.set({ id: 'n1', label: 'TypeScript', description: 'A language' });
    fixture.detectChanges();

    const panel = el.querySelector('.mf-cmap-panel');
    expect(panel).not.toBeNull();
  });
});
