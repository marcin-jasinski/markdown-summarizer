import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./pages/login/login').then(m => m.LoginComponent),
  },
  {
    path: '',
    loadComponent: () => import('./shell/shell').then(m => m.ShellComponent),
    canActivate: [authGuard],
    children: [
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
      {
        path: 'dashboard',
        loadComponent: () => import('./pages/dashboard/dashboard').then(m => m.DashboardComponent),
      },
      {
        path: 'knowledge-bases',
        loadComponent: () => import('./pages/knowledge-bases/knowledge-bases').then(m => m.KnowledgeBasesComponent),
      },
      {
        path: 'kb/:kbId/documents',
        loadComponent: () => import('./pages/documents/documents').then(m => m.DocumentsComponent),
      },
      {
        path: 'kb/:kbId/concepts',
        loadComponent: () => import('./pages/concept-map/concept-map').then(m => m.ConceptMapComponent),
      },
      {
        path: 'kb/:kbId/quiz',
        loadComponent: () => import('./pages/quiz/quiz').then(m => m.QuizComponent),
      },
      {
        path: 'kb/:kbId/flashcards',
        loadComponent: () => import('./pages/flashcards/flashcards').then(m => m.FlashcardsComponent),
      },
      {
        path: 'kb/:kbId/search',
        loadComponent: () => import('./pages/search/search').then(m => m.SearchComponent),
      },
      {
        path: 'kb/:kbId/chat',
        loadComponent: () => import('./pages/chat/chat').then(m => m.ChatComponent),
      },
    ],
  },
  { path: '**', redirectTo: 'dashboard' },
];
