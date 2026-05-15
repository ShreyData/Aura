import React, { useState, useEffect } from 'react';
import { 
  Sparkles, 
  Cpu, 
  Download, 
  FolderOpen, 
  CheckCircle,
  ChevronRight,
  Loader2,
  Monitor
} from 'lucide-react';
import { open } from '@tauri-apps/plugin-dialog';
import { AuraCoreAPI, auraWs } from '../../api/core';
import { useSettingsStore } from '../../stores/settingsStore';
import { getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const OnboardingWizard: React.FC = () => {
  const [step, setStep] = useState(1);
  const { setOnboardingComplete, setWorkspacePath, setModelPreference } = useSettingsStore();
  
  const [recommendedModel, setRecommendedModel] = useState<string | null>(null);
  const [pullProgress, setPullProgress] = useState<{ percent: number; status: string } | null>(null);
  const [selectedPath, setSelectedPath] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (step === 2) {
      AuraCoreAPI.getRecommendedModel().then(res => {
        setRecommendedModel(res.recommended_model);
        setModelPreference(res.recommended_model);
      });
    }

    if (step === 3 && recommendedModel) {
      AuraCoreAPI.pullModel(recommendedModel);
      
      const unsub = auraWs.subscribe('model_pull_progress', (payload) => {
        if (payload.model === recommendedModel) {
          setPullProgress({
            percent: payload.percent,
            status: payload.status || 'Downloading...'
          });
          if (payload.percent === 100) {
            setTimeout(() => setStep(4), 1000);
          }
        }
      });
      return () => unsub();
    }
  }, [step, recommendedModel, setModelPreference]);

  const handlePickFolder = async () => {
    const selected = await open({
      directory: true,
      multiple: false,
      title: 'Select Aura Workspace Folder'
    });
    if (selected && typeof selected === 'string') {
      setSelectedPath(selected);
      setWorkspacePath(selected);
    }
  };

  const handleFinish = () => {
    setOnboardingComplete(true);
    getCurrentWebviewWindow().close();
  };

  return (
    <div className="h-screen w-screen bg-gray-950 text-gray-100 flex flex-col items-center justify-center p-8 overflow-hidden">
      {/* Background Glow */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-blue-600/10 blur-[120px] rounded-full" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-purple-600/10 blur-[120px] rounded-full" />
      </div>

      <div className="w-full max-w-lg relative z-10 space-y-8">
        {/* Progress Dots */}
        <div className="flex justify-center gap-2 mb-8">
          {[1, 2, 3, 4].map((s) => (
            <div 
              key={s} 
              className={cn(
                "h-1.5 rounded-full transition-all duration-500",
                step === s ? "w-8 bg-blue-500" : s < step ? "w-4 bg-green-500" : "w-4 bg-gray-800"
              )}
            />
          ))}
        </div>

        {/* Step 1: Welcome */}
        {step === 1 && (
          <div className="text-center space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-700">
            <div className="flex justify-center">
              <div className="p-4 rounded-3xl bg-blue-600/20 border border-blue-500/30 shadow-2xl shadow-blue-500/10">
                <Sparkles size={48} className="text-blue-400" />
              </div>
            </div>
            <div className="space-y-2">
              <h1 className="text-4xl font-bold tracking-tight">Welcome to Aura</h1>
              <p className="text-gray-400 text-lg">Your privacy-first, ambient AI layer.</p>
            </div>
            <button 
              onClick={() => setStep(2)}
              className="mt-8 px-8 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-2xl font-bold flex items-center gap-2 mx-auto transition-all shadow-lg shadow-blue-500/20 group"
            >
              Get Started
              <ChevronRight size={20} className="group-hover:translate-x-1 transition-transform" />
            </button>
          </div>
        )}

        {/* Step 2: Recommendation */}
        {step === 2 && (
          <div className="space-y-6 animate-in fade-in slide-in-from-right-4 duration-500">
            <div className="text-center space-y-2">
              <h2 className="text-2xl font-bold">Hardware Analysis</h2>
              <p className="text-gray-400">Finding the perfect brain for your machine.</p>
            </div>
            
            <div className="bg-gray-900 border border-gray-800 rounded-3xl p-6 space-y-6">
              <div className="flex items-center gap-4">
                <div className="p-3 rounded-2xl bg-blue-500/10 text-blue-400">
                  <Monitor size={24} />
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-400">System Detected</p>
                  <p className="text-gray-100 font-bold">Standard Workstation</p>
                </div>
              </div>

              <div className="flex items-center gap-4 p-4 rounded-2xl bg-blue-500/5 border border-blue-500/20">
                <div className="p-3 rounded-xl bg-blue-500/10 text-blue-400">
                  <Cpu size={24} />
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-blue-400">Recommended Model</p>
                  <p className="text-gray-100 font-mono font-bold">{recommendedModel || 'Calculating...'}</p>
                </div>
              </div>
            </div>

            <button 
              onClick={() => setStep(3)}
              disabled={!recommendedModel}
              className="w-full py-4 bg-blue-600 hover:bg-blue-500 text-white rounded-2xl font-bold flex items-center justify-center gap-2 transition-all shadow-lg shadow-blue-500/20 disabled:opacity-50"
            >
              Initialize Intelligence
              <ChevronRight size={20} />
            </button>
          </div>
        )}

        {/* Step 3: Pulling */}
        {step === 3 && (
          <div className="text-center space-y-8 animate-in fade-in zoom-in-95 duration-500">
            <div className="space-y-2">
              <h2 className="text-2xl font-bold">Downloading Aura</h2>
              <p className="text-gray-400 italic">This only happens once. Grab a coffee.</p>
            </div>

            <div className="relative py-12">
               <div className="absolute inset-0 flex items-center justify-center">
                  <div className="w-48 h-48 bg-blue-500/5 rounded-full animate-ping opacity-20" />
               </div>
               <div className="relative flex justify-center">
                 <Download size={64} className="text-blue-500 animate-bounce" />
               </div>
            </div>

            <div className="space-y-4">
              <div className="flex justify-between text-xs font-mono text-gray-500 mb-1">
                <span>{pullProgress?.status || 'Starting...'}</span>
                <span>{pullProgress?.percent || 0}%</span>
              </div>
              <div className="h-2 w-full bg-gray-900 border border-gray-800 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-blue-500 transition-all duration-300"
                  style={{ width: `${pullProgress?.percent || 0}%` }}
                />
              </div>
            </div>
          </div>
        )}

        {/* Step 4: Workspace */}
        {step === 4 && (
          <div className="space-y-6 animate-in fade-in slide-in-from-right-4 duration-500">
            <div className="text-center space-y-2">
              <h2 className="text-2xl font-bold">One Last Thing</h2>
              <p className="text-gray-400">Where should Aura keep your local memory?</p>
            </div>

            <div className="bg-gray-900 border border-gray-800 rounded-3xl p-6 space-y-6">
              <div 
                onClick={handlePickFolder}
                className={cn(
                  "p-8 rounded-2xl border-2 border-dashed transition-all cursor-pointer flex flex-col items-center gap-4 group",
                  selectedPath 
                    ? "border-green-500/30 bg-green-500/5" 
                    : "border-gray-800 hover:border-blue-500/30 hover:bg-blue-500/5"
                )}
              >
                <div className={cn(
                  "p-4 rounded-2xl transition-colors",
                  selectedPath ? "bg-green-500/20 text-green-400" : "bg-gray-800 group-hover:bg-blue-500/20 group-hover:text-blue-400"
                )}>
                  {selectedPath ? <CheckCircle size={32} /> : <FolderOpen size={32} />}
                </div>
                <div className="text-center">
                  <p className="font-bold">{selectedPath ? 'Workspace Selected' : 'Choose Workspace Folder'}</p>
                  <p className="text-xs text-gray-500 mt-1 max-w-[200px] truncate">
                    {selectedPath || 'All your data stays here locally.'}
                  </p>
                </div>
              </div>
            </div>

            <button 
              onClick={handleFinish}
              disabled={!selectedPath}
              className="w-full py-4 bg-green-600 hover:bg-green-500 text-white rounded-2xl font-bold flex items-center justify-center gap-2 transition-all shadow-lg shadow-green-500/20 disabled:opacity-50"
            >
              Finish Setup
              <CheckCircle size={20} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
