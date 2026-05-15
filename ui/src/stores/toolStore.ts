import { create } from 'zustand';
import { PendingToolCall } from '../api/types';
import { AuraCoreAPI } from '../api/core';

interface ToolState {
  pendingApprovals: PendingToolCall[];
  
  // Actions
  addPendingApproval: (approval: PendingToolCall) => void;
  removePendingApproval: (requestId: string) => void;
  approve: (requestId: string) => Promise<void>;
  deny: (requestId: string) => Promise<void>;
}

export const useToolStore = create<ToolState>((set, get) => ({
  pendingApprovals: [],

  addPendingApproval: (approval) =>
    set((state) => {
      // Prevent duplicates based on request_id
      if (state.pendingApprovals.some((p) => p.request_id === approval.request_id)) {
        return state;
      }
      return { pendingApprovals: [...state.pendingApprovals, approval] };
    }),

  removePendingApproval: (requestId) =>
    set((state) => ({
      pendingApprovals: state.pendingApprovals.filter((p) => p.request_id !== requestId),
    })),

  approve: async (requestId) => {
    try {
      await AuraCoreAPI.approveTool(requestId, true);
      get().removePendingApproval(requestId);
    } catch (error) {
      console.error('Failed to approve tool call:', error);
      // Even if API fails, we might want to remove it to prevent getting stuck
      get().removePendingApproval(requestId);
    }
  },

  deny: async (requestId) => {
    try {
      await AuraCoreAPI.approveTool(requestId, false);
      get().removePendingApproval(requestId);
    } catch (error) {
      console.error('Failed to deny tool call:', error);
      get().removePendingApproval(requestId);
    }
  },
}));
