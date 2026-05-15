/**
 * TypeScript definitions for Aura Core API and WebSocket event bus.
 * Strictly follows docs/API_Contract.md and core/aura/api/schemas.py.
 */

// --- REST API Models ---

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  name?: string;
  tool_calls?: any[];
  images?: string[];
}

export interface ChatCompletionRequest {
  model: string;
  messages: ChatMessage[];
  stream?: boolean;
  temperature?: number;
  top_p?: number;
  n?: number;
  max_tokens?: number;
  stop?: string | string[];
  presence_penalty?: number;
  frequency_penalty?: number;
  logit_bias?: Record<string, number>;
  user?: string;
  tools?: any[];
  tool_choice?: string | any;
}

export interface ChatCompletionResponseChoice {
  index: number;
  message: ChatMessage;
  finish_reason?: string;
}

export interface ChatCompletionUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface ChatCompletionResponse {
  id: string;
  object: 'chat.completion';
  created: number;
  model: string;
  choices: ChatCompletionResponseChoice[];
  usage?: ChatCompletionUsage;
}

export interface ChatCompletionChunkDelta {
  role?: string;
  content?: string;
  tool_calls?: any[];
}

export interface ChatCompletionChunkChoice {
  index: number;
  delta: ChatCompletionChunkDelta;
  finish_reason?: string;
}

export interface ChatCompletionChunk {
  id: string;
  object: 'chat.completion.chunk';
  created: number;
  model: string;
  choices: ChatCompletionChunkChoice[];
}

export interface HealthResponse {
  aura: boolean;
  ollama: boolean;
  active_model?: string;
  uptime_s: number;
}

export interface PendingToolCall {
  request_id: string;
  tool_name: string;
  description: string;
  args: Record<string, any>;
  risk_level: 'low' | 'medium' | 'high';
}

export interface ModelInfo {
  name: string;
  size: number;
  digest: string;
  modified_at: string;
}

export interface AppConfig {
  core_port: number;
  ollama_port: number;
  ollama_models_dir: string;
  default_model: string;
  embed_model: string;
  workspace_path: string;
  allow_system_paths: boolean;
  require_approval_medium: boolean;
  log_level: string;
  auto_unload_minutes: number;
}

// --- WebSocket Event Bus ---

export type WsEvent =
  | { type: 'chat_chunk'; payload: { delta: string; request_id: string } }
  | { type: 'chat_done'; payload: { request_id: string; usage: { prompt_tokens: number; completion_tokens: number } } }
  | { type: 'tool_call_start'; payload: { tool_name: string; args: Record<string, any> } }
  | { type: 'tool_approval_needed'; payload: PendingToolCall }
  | { type: 'tool_result'; payload: { tool_name: string; success: boolean; output: string } }
  | { type: 'orb_state'; payload: { state: 'idle' | 'listening' | 'thinking' | 'speaking' | 'acting' | 'error' } }
  | { type: 'model_pull_progress'; payload: { model: string; percent: number; status?: string } }
  | { type: 'ollama_status'; payload: { running: boolean; active_model?: string } }
  | { type: 'error'; payload: { code: string; message: string } }
  | { type: 'pong'; payload: {} };

export type WsEventType = WsEvent['type'];

export interface WsMessage {
  type: 'chat' | 'cancel' | 'ping';
  payload: any;
}
