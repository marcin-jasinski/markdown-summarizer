import {
  Component,
  OnInit,
  ChangeDetectionStrategy,
  inject,
  signal,
} from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MfSnackbarService } from '../../core/services/mf-snackbar.service';
import { QuizService } from '../../core/services/quiz.service';
import type { QuizQuestionResponse, AnswerEvaluationResponse } from '../../core/models/api.models';

type QuizState = 'idle' | 'question' | 'evaluated' | 'loading' | 'finished';

@Component({
  selector: 'app-quiz',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink],
  templateUrl: './quiz.html',
  styleUrl: './quiz.scss',
})
export class QuizComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly quizService = inject(QuizService);
  private readonly snackbarService = inject(MfSnackbarService);

  readonly kbId = signal('');
  readonly quizState = signal<QuizState>('idle');
  readonly currentQuestion = signal<QuizQuestionResponse | null>(null);
  readonly currentResult = signal<AnswerEvaluationResponse | null>(null);
  readonly answer = signal('');

  ngOnInit() {
    this.kbId.set(this.route.snapshot.paramMap.get('kbId') ?? '');
  }

  lessonLabel(): string {
    return this.currentQuestion()?.lesson_id ?? '';
  }

  getScoreClass(score?: number): string {
    if (score === undefined || score === null) return 'score-low';
    if (score >= 4) return 'score-high';
    if (score >= 3) return 'score-mid';
    return 'score-low';
  }

  startQuiz() {
    this.quizState.set('loading');
    this.currentResult.set(null);
    this.answer.set('');
    this.quizService.startSession(this.kbId()).subscribe({
      next: q => { this.currentQuestion.set(q); this.quizState.set('question'); },
      error: (err: Error) => { this.snackbarService.show(err.message, 'error'); this.quizState.set('idle'); },
    });
  }

  submitAnswer() {
    const q = this.currentQuestion();
    if (!q || !this.answer().trim()) return;
    this.quizState.set('loading');
    this.quizService.submitAnswer(this.kbId(), q.session_id, {
      question_id: q.question_id,
      user_answer: this.answer(),
    }).subscribe({
      next: eval_ => { this.currentResult.set(eval_); this.quizState.set('evaluated'); },
      error: (err: Error) => { this.snackbarService.show(err.message, 'error'); this.quizState.set('question'); },
    });
  }

  nextQuestion() {
    this.startQuiz();
  }

  endQuiz() {
    this.quizState.set('finished');
  }
}
