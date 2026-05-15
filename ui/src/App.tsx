import React, { useEffect, useState } from 'react';
import { getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow';
import { Orb } from './components/Orb/Orb';

const App: React.FC = () => {
  const [label, setLabel] = useState<string | null>(null);

  useEffect(() => {
    setLabel(getCurrentWebviewWindow().label);
  }, []);

  if (!label) return null;

  return (
    <div className="h-screen w-screen overflow-hidden">
      {label === 'orb' && <Orb />}
      
      {label === 'hub' && (
        <div className="flex h-screen w-screen items-center justify-center bg-gray-900 text-white">
          <h1>Aura Hub</h1>
        </div>
      )}

      {label === 'permission' && (
        <div className="flex h-screen w-screen items-center justify-center bg-gray-800 text-white border-2 border-amber-500">
          <h1>Permission Request</h1>
        </div>
      )}

      {label === 'onboarding' && (
        <div className="flex h-screen w-screen items-center justify-center bg-gray-900 text-white">
          <h1>Onboarding Wizard</h1>
        </div>
      )}
    </div>
  );
};

export default App;
