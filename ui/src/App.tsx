import React, { useEffect, useState } from 'react';
import { getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow';
import { Orb } from './components/Orb/Orb';

import { PermissionDialog } from './components/PermissionDialog/PermissionDialog';

import { OnboardingWizard } from './components/Onboarding/OnboardingWizard';

import { Hub } from './components/Hub/Hub';

import { useSettingsStore } from './stores/settingsStore';
import { getAllWebviewWindows } from '@tauri-apps/api/webviewWindow';

const App: React.FC = () => {
  const [label, setLabel] = useState<string | null>(null);
  const onboardingComplete = useSettingsStore((s) => s.onboardingComplete);

  useEffect(() => {
    const currentWindow = getCurrentWebviewWindow();
    setLabel(currentWindow.label);

    // Initial onboarding check
    if (!onboardingComplete && (currentWindow.label === 'orb' || currentWindow.label === 'hub')) {
      const showOnboarding = async () => {
        const windows = await getAllWebviewWindows();
        const onboarding = windows.find((w) => w.label === 'onboarding');
        if (onboarding) {
          await onboarding.show();
          await onboarding.setFocus();
        }
      };
      showOnboarding();
    }
  }, [onboardingComplete]);

  if (!label) return null;

  return (
    <div className="h-screen w-screen overflow-hidden">
      {label === 'orb' && <Orb />}
      
      {label === 'hub' && <Hub />}

      {label === 'permission' && <PermissionDialog />}

      {label === 'onboarding' && <OnboardingWizard />}
    </div>
  );
};

export default App;
