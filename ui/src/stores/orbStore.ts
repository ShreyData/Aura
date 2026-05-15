import { create } from 'zustand';

type OrbStateType = 'idle' | 'listening' | 'thinking' | 'speaking' | 'acting' | 'error';

interface OrbState {
  state: OrbStateType;
  timeoutId: number | null;
  
  // Actions
  setState: (newState: OrbStateType) => void;
}

export const useOrbStore = create<OrbState>((set, get) => ({
  state: 'idle',
  timeoutId: null,

  setState: (newState) => {
    const { timeoutId } = get();
    
    // Clear any existing timeout to prevent state overrides
    if (timeoutId !== null) {
      window.clearTimeout(timeoutId);
    }

    // Auto-return to IDLE after 3 seconds if state is ERROR
    if (newState === 'error') {
      const newTimeoutId = window.setTimeout(() => {
        set({ state: 'idle', timeoutId: null });
      }, 3000);
      set({ state: 'error', timeoutId: newTimeoutId });
    } else {
      set({ state: newState, timeoutId: null });
    }
  },
}));
