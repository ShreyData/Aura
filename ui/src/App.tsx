import React, { useEffect, useState } from 'react';
import { getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow';
import { Orb } from './components/Orb/Orb';

import { PermissionDialog } from './components/PermissionDialog/PermissionDialog';

import { OnboardingWizard } from './components/Onboarding/OnboardingWizard';

import { Hub } from './components/Hub/Hub';

const App: React.FC = () => {
  const [label, setLabel] = useState<string | null>(null);

  useEffect(() => {
    setLabel(getCurrentWebviewWindow().label);
  }, []);

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
