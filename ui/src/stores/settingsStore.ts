import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface SettingsState {
  modelPreference: string;
  workspacePath: string;
  hotkeyBindings: Record<string, string>;
  onboardingComplete: boolean;
  
  // Actions
  setModelPreference: (model: string) => void;
  setWorkspacePath: (path: string) => void;
  setHotkeyBinding: (action: string, combo: string) => void;
  setOnboardingComplete: (complete: boolean) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      modelPreference: 'gemma4:e4b', // Default recommendation
      workspacePath: '',
      hotkeyBindings: {
        capture: 'Alt+Space',
        dismiss: 'Escape',
      },
      onboardingComplete: false,

      setModelPreference: (model) => set({ modelPreference: model }),
      setWorkspacePath: (path) => set({ workspacePath: path }),
      setHotkeyBinding: (action, combo) =>
        set((state) => ({
          hotkeyBindings: {
            ...state.hotkeyBindings,
            [action]: combo,
          },
        })),
      setOnboardingComplete: (complete) => set({ onboardingComplete: complete }),
    }),
    {
      name: 'aura-settings-storage', // name of the item in the storage (must be unique)
    }
  )
);
