/**
 * TDD Red Gate: FlashcardService.reviewCard() URL bug
 *
 * This test MUST FAIL before the fix is applied.
 *
 * Bug: reviewCard() sends POST to
 *   /api/knowledge-bases/{kbId}/flashcards/review
 * but the backend expects
 *   /api/knowledge-bases/{kbId}/flashcards/{card_id}/review
 *
 * The card_id is present in the ReviewRequest body but missing from the URL.
 */

import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { FlashcardService } from '../app/core/services/flashcard.service';
import { ApiService } from '../app/core/services/api.service';

describe('FlashcardService — TDD Red Gate', () => {
  let service: FlashcardService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), ApiService, FlashcardService],
    });
    service = TestBed.inject(FlashcardService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('reviewCard() should send POST with card_id in the URL path', () => {
    const kbId = 'kb-abc-123';
    const cardId = 'card-xyz-789';

    service.reviewCard(kbId, { card_id: cardId, rating: 4 }).subscribe();

    // Expect the URL to include the card_id as a path segment
    const expectedUrl = `/api/knowledge-bases/${kbId}/flashcards/${cardId}/review`;
    http.expectOne(expectedUrl);
    // If the bug is present, this test fails because the actual URL is:
    //   /api/knowledge-bases/kb-abc-123/flashcards/review
    // and HttpTestingController throws "Expected one matching request ..."
  });
});
