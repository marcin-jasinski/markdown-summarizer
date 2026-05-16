import { Injectable, NgZone } from '@angular/core';
import { Observable } from 'rxjs';
import type { SSEEvent } from '../models/api.models';

/**
 * Subscribes to the Server-Sent Events stream for a knowledge base.
 * Falls back gracefully when the EventSource connection is unavailable.
 */
@Injectable({ providedIn: 'root' })
export class EventService {
  private readonly zone: NgZone;

  constructor(zone: NgZone) {
    this.zone = zone;
  }

  /** Returns an Observable of SSEEvent from the KB event stream. */
  connect(kbId: string): Observable<SSEEvent> {
    return new Observable<SSEEvent>(subscriber => {
      const url = `/api/knowledge-bases/${kbId}/events`;
      const source = new EventSource(url, { withCredentials: true });

      source.onmessage = (event: MessageEvent) => {
        this.zone.run(() => {
          try {
            const parsed = JSON.parse(event.data) as SSEEvent;
            subscriber.next(parsed);
          } catch {
            // Ignore malformed frames
          }
        });
      };

      source.onerror = () => {
        // EventSource auto-reconnects; only complete on explicit close
        if (source.readyState === EventSource.CLOSED) {
          this.zone.run(() => subscriber.complete());
        }
      };

      return () => source.close();
    });
  }
}
