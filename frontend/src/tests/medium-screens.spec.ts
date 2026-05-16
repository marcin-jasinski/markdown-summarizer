/**
 * Medium Screens Tests — Documents, Quiz, Flashcards, Search
 * Group 9 — Phase 4 Screen Redesigns
 */
import { TestBed, ComponentFixture } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { ActivatedRoute } from '@angular/router';
import { of } from 'rxjs';

import { DocumentsComponent } from '../app/pages/documents/documents';
import { QuizComponent } from '../app/pages/quiz/quiz';
import { FlashcardsComponent } from '../app/pages/flashcards/flashcards';
import { SearchComponent } from '../app/pages/search/search';
import { DocumentService } from '../app/core/services/document.service';
import { EventService } from '../app/core/services/event.service';
import { QuizService } from '../app/core/services/quiz.service';
import { FlashcardService } from '../app/core/services/flashcard.service';
import { SearchService } from '../app/core/services/search.service';
import { MfSnackbarService } from '../app/core/services/mf-snackbar.service';

// Import flashcards.scss as raw string via Node.js fs (Vitest runs in Node)
import { readFileSync } from 'fs';
import { resolve } from 'path';

const mockActivatedRoute = {
  snapshot: { paramMap: { get: (_: string) => 'kb-1' } },
};
const mockSnackbar = { show: vi.fn() };

// ---------------------------------------------------------------------------
// DocumentsComponent
// ---------------------------------------------------------------------------

describe('DocumentsComponent (redesigned)', () => {
  let fixture: ComponentFixture<DocumentsComponent>;
  let el: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DocumentsComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: mockActivatedRoute },
        {
          provide: DocumentService,
          useValue: { list: () => of([]), reprocess: () => of({}), delete: () => of(undefined) },
        },
        {
          provide: EventService,
          useValue: { connect: () => of() },
        },
        { provide: MfSnackbarService, useValue: mockSnackbar },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(DocumentsComponent);
    el = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
  });

  it('Test 1: template uses <table> not mat-table', () => {
    // Populate documents so the table renders
    fixture.componentInstance.documents.set([
      {
        document_id: 'd1',
        knowledge_base_id: 'kb-1',
        lesson_id: 'lesson-1',
        title: 'Doc 1',
        source_filename: 'doc1.pdf',
        mime_type: 'application/pdf',
        status: 'completed',
        upload_source: 'upload',
        revision: 1,
        is_active: true,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      },
    ]);
    fixture.detectChanges();

    const nativeTable = el.querySelector('table');
    const matTable = el.querySelector('[mat-table]');
    expect(nativeTable).not.toBeNull();
    expect(matTable).toBeNull();
  });

  it('Test 2: drag-over on upload zone sets isDragOver to true (adds mf-upload-zone-dragover class)', () => {
    const zone = el.querySelector('.mf-upload-zone') as HTMLElement;
    expect(zone).not.toBeNull();

    // Directly set the signal (DragEvent not available in jsdom)
    fixture.componentInstance.isDragOver.set(true);
    fixture.detectChanges();

    expect(zone.classList.contains('mf-upload-zone-dragover')).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// QuizComponent
// ---------------------------------------------------------------------------

describe('QuizComponent (redesigned)', () => {
  let fixture: ComponentFixture<QuizComponent>;
  let el: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [QuizComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: mockActivatedRoute },
        {
          provide: QuizService,
          useValue: {
            startSession: () => of({ session_id: 's1', question_id: 'q1', question_text: 'What?', question_type: 'open', lesson_id: 'L1' }),
            submitAnswer: () => of({ question_id: 'q1', score: 4, feedback: 'Good', is_correct: true }),
          },
        },
        { provide: MfSnackbarService, useValue: mockSnackbar },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(QuizComponent);
    el = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
  });

  it('Test 3: submit button is disabled when answer signal is empty string', () => {
    fixture.componentInstance.quizState.set('question');
    fixture.componentInstance.currentQuestion.set({
      session_id: 's1', question_id: 'q1', question_text: 'What is X?',
      question_type: 'open', lesson_id: 'L1',
    });
    fixture.componentInstance.answer.set('');
    fixture.detectChanges();

    const btn = el.querySelector('button[disabled]') as HTMLButtonElement;
    expect(btn).not.toBeNull();
  });

  it('Test 4: evaluated state shows .mf-score-badge element', () => {
    fixture.componentInstance.quizState.set('evaluated');
    fixture.componentInstance.currentResult.set({
      question_id: 'q1', score: 4, feedback: 'Great answer!', is_correct: true,
    });
    fixture.detectChanges();

    const badge = el.querySelector('.mf-score-badge');
    expect(badge).not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// FlashcardsComponent
// ---------------------------------------------------------------------------

describe('FlashcardsComponent (redesigned)', () => {
  let fixture: ComponentFixture<FlashcardsComponent>;
  let el: HTMLElement;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [FlashcardsComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: mockActivatedRoute },
        {
          provide: FlashcardService,
          useValue: {
            getDueCards: () => of([
              { card_id: 'c1', lesson_id: 'L1', card_type: 'basic', front: 'Q?', back: 'A.', tags: [], next_review: null, ease_factor: null, interval: null },
            ]),
            reviewCard: () => of({}),
          },
        },
        { provide: MfSnackbarService, useValue: mockSnackbar },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(FlashcardsComponent);
    el = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
  });

  it('Test 5: flashcards.scss contains transform-style: preserve-3d', () => {
    const scssPath = resolve(__dirname, '../app/pages/flashcards/flashcards.scss');
    const flashcardsScss = readFileSync(scssPath, 'utf-8');
    expect(flashcardsScss).toContain('preserve-3d');
  });

  it('Test 6: flip() adds .flipped class to .flashcard-inner', () => {
    const inner = el.querySelector('.flashcard-inner') as HTMLElement;
    expect(inner).not.toBeNull();
    expect(inner.classList.contains('flipped')).toBe(false);

    fixture.componentInstance.flip();
    fixture.detectChanges();

    expect(inner.classList.contains('flipped')).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// SearchComponent
// ---------------------------------------------------------------------------

describe('SearchComponent', () => {
  let fixture: ComponentFixture<SearchComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SearchComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: mockActivatedRoute },
        {
          provide: SearchService,
          useValue: {
            search: () => of({ results: [], query: '' }),
          },
        },
        { provide: MfSnackbarService, useValue: mockSnackbar },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(SearchComponent);
    fixture.detectChanges();
  });

  it('Test 7: removeFilter() removes the filter from activeFilters()', () => {
    const comp = fixture.componentInstance;
    comp.activeFilters.set(['Algebra', 'Physics']);
    comp.removeFilter('Algebra');
    expect(comp.activeFilters()).toEqual(['Physics']);
  });
});
