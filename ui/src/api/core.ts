import { invoke } from "@tauri-apps/api/core";
import {
  AppConfig,
  HealthResponse,
  ModelInfo,
  PendingToolCall,
  WsEvent,
  WsEventType,
  WsMessage,
} from "./types";

/**
 * AuraCoreAPI provides a typed bridge to the Aura Core backend via Tauri IPC.
 * All methods here call the Rust commands defined in src-tauri/src/ipc.rs.
 */
export const AuraCoreAPI = {
  async getHealth(): Promise<HealthResponse> {
    return await invoke("health");
  },

  async getRecommendedModel(): Promise<{ recommended_model: string; total_ram_gb: number; cpu_count: number }> {
    return await invoke("recommend_model");
  },

  async approveTool(requestId: string, approved: boolean): Promise<void> {
    return await invoke("approve_tool", { requestId, approved });
  },

  async getPendingTools(): Promise<PendingToolCall[]> {
    return await invoke("get_pending_tools");
  },

  async ingestFile(filePath: string): Promise<{ status: string }> {
    return await invoke("ingest_file", { filePath });
  },

  async listModels(): Promise<{ models: ModelInfo[]; active_model?: string; active_model_vram?: number }> {
    return await invoke("list_models");
  },

  async pullModel(model: string): Promise<void> {
    return await invoke("pull_model", { model });
  },

  async deleteModel(name: string): Promise<void> {
    return await invoke("delete_model", { name });
  },

  async getConfig(): Promise<AppConfig> {
    return await invoke("get_config");
  },

  async updateConfig(updates: Partial<AppConfig>): Promise<AppConfig> {
    return await invoke("update_config", { updates });
  },
};

/**
 * AuraWebSocket manages the real-time event bus connection with the Aura Core.
 * Handles automatic reconnection with exponential backoff.
 */
export class AuraWebSocket {
  private ws: WebSocket | null = null;
  private subscribers: Map<string, Set<(payload: any) => void>> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectDelay = 30000; // 30 seconds
  private baseUrl = "ws://127.0.0.1:11434/v1/ws";

  constructor() {
    this.connect();
  }

  private connect() {
    console.log("Connecting to Aura WebSocket...");
    this.ws = new WebSocket(this.baseUrl);

    this.ws.onopen = () => {
      console.log("Aura WebSocket connected.");
      this.reconnectAttempts = 0;
      this.send({ type: "ping", payload: {} });
    };

    this.ws.onmessage = (event) => {
      try {
        const data: WsEvent = JSON.parse(event.data);
        this.notify(data.type, data.payload);
      } catch (e) {
        console.error("Failed to parse WebSocket message:", e);
      }
    };

    this.ws.onclose = () => {
      console.warn("Aura WebSocket closed. Reconnecting...");
      this.handleReconnect();
    };

    this.ws.onerror = (error) => {
      console.error("Aura WebSocket error:", error);
      this.ws?.close();
    };
  }

  private handleReconnect() {
    const delay = Math.min(
      Math.pow(2, this.reconnectAttempts) * 1000,
      this.maxReconnectDelay
    );
    this.reconnectAttempts++;

    setTimeout(() => {
      this.connect();
    }, delay);
  }

  /**
   * Subscribe to a specific event type from the Aura event bus.
   */
  subscribe<T extends WsEventType>(
    type: T,
    callback: (payload: Extract<WsEvent, { type: T }>["payload"]) => void
  ) {
    if (!this.subscribers.has(type)) {
      this.subscribers.set(type, new Set());
    }
    this.subscribers.get(type)?.add(callback);

    return () => this.unsubscribe(type, callback);
  }

  /**
   * Unsubscribe from an event.
   */
  unsubscribe<T extends WsEventType>(
    type: T,
    callback: (payload: any) => void
  ) {
    this.subscribers.get(type)?.delete(callback);
  }

  private notify(type: string, payload: any) {
    this.subscribers.get(type)?.forEach((callback) => callback(payload));
  }

  /**
   * Send a message to the Aura Core via WebSocket.
   */
  send(message: WsMessage) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.error("WebSocket is not open. Message not sent:", message);
    }
  }

  /**
   * Close the connection permanently.
   */
  close() {
    if (this.ws) {
      this.ws.onclose = null; // Prevent auto-reconnect
      this.ws.close();
    }
  }
}

// Export a singleton instance
export const auraWs = new AuraWebSocket();
