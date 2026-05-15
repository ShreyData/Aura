import { create } from 'zustand';
import { ChatMessage } from '../api/types';

interface ChatState {
  messages: ChatMessage[];
  isStreaming: boolean;
  currentRequestId: string | null;
  
  // Actions
  addMessage: (message: ChatMessage) => void;
  appendStreamChunk: (requestId: string, chunk: string) => void;
  setStreaming: (isStreaming: boolean, requestId: string | null) => void;
  finalizeStream: () => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isStreaming: false,
  currentRequestId: null,

  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),

  appendStreamChunk: (requestId, chunk) =>
    set((state) => {
      if (state.currentRequestId !== requestId) return state;

      const messages = [...state.messages];
      const lastMessage = messages[messages.length - 1];

      // If the last message is from the assistant, append to it.
      // Otherwise, create a new assistant message.
      if (lastMessage && lastMessage.role === 'assistant') {
        messages[messages.length - 1] = {
          ...lastMessage,
          content: lastMessage.content + chunk,
        };
      } else {
        messages.push({ role: 'assistant', content: chunk });
      }

      return { messages };
    }),

  setStreaming: (isStreaming, requestId) =>
    set({ isStreaming, currentRequestId: requestId }),

  finalizeStream: () =>
    set({ isStreaming: false, currentRequestId: null }),

  clearMessages: () =>
    set({ messages: [], isStreaming: false, currentRequestId: null }),
}));
