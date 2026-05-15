import React, { useEffect } from 'react';
import { getCurrentWebviewWindow, getAllWebviewWindows } from '@tauri-apps/api/webviewWindow';
import { LogicalPosition } from '@tauri-apps/api/window';
import { useOrbStore } from '../../stores/orbStore';
import './orb.css';

/**
 * Orb Component
 * Ambient ambient AI status widget with pure CSS animations.
 */
export const Orb: React.FC = () => {
  const state = useOrbStore((s) => s.state);
  
  useEffect(() => {
    // Initial positioning to bottom-right on mount
    const positionOrb = async () => {
      const window = getCurrentWebviewWindow();
      if (window.label === 'orb') {
        const monitor = await window.currentMonitor();
        if (monitor) {
          const { width, height } = monitor.size;
          const { scaleFactor } = monitor;
          
          // Position 40px from edges (scaled)
          const x = (width / scaleFactor) - 104; // 64 window + 40 margin
          const y = (height / scaleFactor) - 104;
          
          await window.setPosition(new LogicalPosition(x, y));
          await window.show();
        }
      }
    };

    positionOrb();
  }, []);

  const handleClick = async () => {
    const windows = await getAllWebviewWindows();
    const hub = windows.find((w) => w.label === 'hub');
    
    if (hub) {
      await hub.show();
      await hub.unminimize();
      await hub.setFocus();
    }
  };

  return (
    <div className="orb-container" onClick={handleClick}>
      <div className={`orb orb-${state}`} />
    </div>
  );
};
