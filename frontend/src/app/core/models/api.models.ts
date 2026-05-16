/**
 * TypeScript API contracts — mirrors mindforge/api/schemas.py.
 * Keep in sync with the Pydantic models. Every field name, type, and
 * optionality must match exactly.
 *
 * UUIDs and datetimes are typed as `string` (UUID v4 string / ISO-8601).
 */

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface RegisterRequest {
  email: string;
  password: string;
  display_name: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserResponse {
  user_id: string;
  display_name: string;
  email: string | null;
  avatar_url: string | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Knowledge Bases
// ---------------------------------------------------------------------------

export interface KnowledgeBaseCreate {
  name: string;
  description?: string;
  prompt_locale?: string;
}

export interface KnowledgeBaseUpdate {
  name?: string;
  description?: string;
  prompt_locale?: string;
}

export interface KnowledgeBaseResponse {
  kb_id: string;
  owner_id: string;
  name: string;
  description: string;
  created_at: string;
  document_count: number;
  prompt_locale: string;
}

// ---------------------------------------------------------------------------
// Documents
// ---------------------------------------------------------------------------

export interface DocumentResponse {
  document_id: string;
  knowledge_base_id: string;
  lesson_id: string;
  title: string;
  source_filename: string;
  mime_type: string;
  status: string;
  upload_source: string;
  revision: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface UploadResponse {
  document_id: string;
  task_id: string;
  lesson_id: string;
  revision: number;
  message: string;
}

export interface ReprocessRequest {
  force: boolean;
}

// ---------------------------------------------------------------------------
// Pipeline tasks
// ---------------------------------------------------------------------------

export interface TaskStatusResponse {
  task_id: string;
  document_id: string;
  status: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  attempt_count: number;
}

// ---------------------------------------------------------------------------
// Concepts / graph
// ---------------------------------------------------------------------------

export interface ConceptNodeResponse {
  key: string;
  label: string;
  description: string;
  related: string[];
}

export interface ConceptEdgeResponse {
  source: string;
  target: string;
  relation: string;
}

export interface ConceptGraphResponse {
  concepts: ConceptNodeResponse[];
  edges: ConceptEdgeResponse[];
}

// ---------------------------------------------------------------------------
// Quiz
// ---------------------------------------------------------------------------

export interface StartQuizRequest {
  topic?: string;
}

export interface QuizQuestionResponse {
  session_id: string;
  question_id: string;
  question_text: string;
  question_type: string;
  lesson_id: string;
}

export interface SubmitAnswerRequest {
  question_id: string;
  user_answer: string;
}

export interface AnswerEvaluationResponse {
  question_id: string;
  score: number;
  feedback: string;
  is_correct: boolean;
}

// ---------------------------------------------------------------------------
// Flashcards
// ---------------------------------------------------------------------------

export interface FlashcardResponse {
  card_id: string;
  lesson_id: string;
  card_type: string;
  front: string;
  back: string;
  tags: string[];
  next_review: string | null;
  ease_factor: number | null;
  interval: number | null;
}

export interface ReviewRequest {
  card_id: string;
  rating: number;
}

export interface DueCountResponse {
  due_count: number;
  kb_id: string;
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

export interface SearchRequest {
  query: string;
  top_k?: number;
}

export interface SearchResultItem {
  content: string;
  source_lesson_id: string;
  source_document_id: string;
  score: number;
  metadata: Record<string, unknown>;
}

export interface SearchResponse {
  results: SearchResultItem[];
  query: string;
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

export interface StartChatRequest {
  knowledge_base_id: string;
}

export interface ChatMessageRequest {
  message: string;
}

export interface ChatTurnResponse {
  role: string;
  content: string;
  created_at: string;
}

export interface ChatSessionResponse {
  session_id: string;
  knowledge_base_id: string;
  created_at: string;
  turns: ChatTurnResponse[];
}

export interface ChatMessageResponse {
  session_id: string;
  answer: string;
  source_concept_keys: string[];
}

// ---------------------------------------------------------------------------
// SSE / events
// ---------------------------------------------------------------------------

export interface SSEEvent {
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Interaction history (redacted)
// ---------------------------------------------------------------------------

export interface InteractionTurnResponse {
  turn_id: string;
  interaction_id: string;
  turn_number: number;
  role: string;
  content: string;
  created_at: string;
  tokens_used: number;
}

export interface InteractionResponse {
  interaction_id: string;
  interaction_type: string;
  created_at: string;
  knowledge_base_id: string | null;
  completed_at: string | null;
  turns: InteractionTurnResponse[];
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export interface HealthResponse {
  status: string;
  database: string;
  neo4j: string | null;
  redis: string | null;
}

// ---------------------------------------------------------------------------
// Admin
// ---------------------------------------------------------------------------

export interface SystemMetricsResponse {
  total_users: number;
  total_documents: number;
  total_knowledge_bases: number;
  pending_pipeline_tasks: number;
  outbox_unpublished: number;
}

// ---------------------------------------------------------------------------
// Lessons
// ---------------------------------------------------------------------------

export interface LessonResponse {
  lesson_id: string;
  title: string;
  document_count: number;
  flashcard_count: number;
  concept_count: number;
  last_processed_at: string | null;
}

// ---------------------------------------------------------------------------
// User stats
// ---------------------------------------------------------------------------

export interface UserStatsResponse {
  streak_days: number;
  due_today: number;
}
