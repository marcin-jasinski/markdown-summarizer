import {
  Component,
  OnInit,
  AfterViewChecked,
  ChangeDetectionStrategy,
  inject,
  signal,
  ElementRef,
  ViewChild,
} from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { MfSnackbarService } from '../../core/services/mf-snackbar.service';
import { ChatService } from '../../core/services/chat.service';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  sourceKeys?: string[];
}

@Component({
  selector: 'app-chat',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [],
  templateUrl: './chat.html',
  styleUrl: './chat.scss',
})
export class ChatComponent implements OnInit, AfterViewChecked {
  @ViewChild('messagesContainer') messagesContainer!: ElementRef<HTMLDivElement>;

  private readonly route = inject(ActivatedRoute);
  private readonly chatService = inject(ChatService);
  private readonly snackbarService = inject(MfSnackbarService);

  readonly kbId = signal('');
  readonly kbName = signal<string | null>(null);
  readonly sessionId = signal<string | null>(null);
  readonly messages = signal<ChatMessage[]>([]);
  readonly inputText = signal('');
  readonly sending = signal(false);
  readonly starting = signal(false);

  get isLoading() { return this.sending; }

  private shouldScrollToBottom = false;

  ngOnInit() {
    this.kbId.set(this.route.snapshot.paramMap.get('kbId') ?? '');
    this.startSession();
  }

  ngAfterViewChecked() {
    if (this.shouldScrollToBottom) {
      this.scrollToBottom();
      this.shouldScrollToBottom = false;
    }
  }

  startSession() {
    this.starting.set(true);
    this.chatService.startSession(this.kbId()).subscribe({
      next: session => { this.sessionId.set(session.session_id); this.starting.set(false); },
      error: (err: Error) => { this.snackbarService.show(err.message, 'error'); this.starting.set(false); },
    });
  }

  onSend() {
    const text = this.inputText().trim();
    const sid = this.sessionId();
    if (!text || !sid || this.sending()) return;

    this.messages.update(msgs => [...msgs, { role: 'user', content: text }]);
    this.inputText.set('');
    this.sending.set(true);
    this.shouldScrollToBottom = true;

    this.chatService.sendMessage(sid, { message: text }).subscribe({
      next: resp => {
        this.messages.update(msgs => [
          ...msgs,
          { role: 'assistant', content: resp.answer, sourceKeys: resp.source_concept_keys },
        ]);
        this.sending.set(false);
        this.shouldScrollToBottom = true;
      },
      error: (err: Error) => {
        this.snackbarService.show(err.message, 'error');
        this.sending.set(false);
      },
    });
  }

  onEnterKey(event: Event): void {
    if (!(event as KeyboardEvent).shiftKey) {
      event.preventDefault();
      this.onSend();
    }
  }

  formatMessage(content: string): string {
    return content.replace(/\n/g, '<br>');
  }

  private scrollToBottom() {
    try {
      const el = this.messagesContainer?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
    } catch { /* noop */ }
  }
}
