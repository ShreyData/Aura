import React, { useState, useEffect, useCallback } from 'react';
import { 
  Cpu, 
  Layers, 
  Download, 
  Trash2, 
  CheckCircle2, 
  AlertCircle, 
  Loader2, 
  Play,
  Zap,
  HardDrive,
  Info,
  RefreshCw
} from 'lucide-react';
import { AuraCoreAPI, auraWs } from '../../api/core';
import { ModelInfo } from '../../api/types';
import { useSettingsStore } from '../../stores/settingsStore';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const ModelsView: React.FC = () => {
  const { modelPreference, setModelPreference } = useSettingsStore();
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [activeModel, setActiveModel] = useState<string | null>(null);
  const [activeVram, setActiveVram] = useState<number>(0);
  const [recommendedModel, setRecommendedModel] = useState<string | null>(null);
  const [pullInput, setPullInput] = useState('');
  const [pullProgress, setPullProgress] = useState<{ model: string; percent: number; status: string } | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isPulling, setIsPulling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);
      const [modelsData, recommendationData] = await Promise.all([
        AuraCoreAPI.listModels(),
        AuraCoreAPI.getRecommendedModel()
      ]);
      
      setModels(modelsData.models);
      setActiveModel(modelsData.active_model || null);
      setActiveVram(modelsData.active_model_vram || 0);
      setRecommendedModel(recommendationData.recommended_model);
      
    } catch (err) {
      setError('Failed to fetch model information');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();

    const unsubProgress = auraWs.subscribe('model_pull_progress', (payload) => {
      setPullProgress({
        model: payload.model,
        percent: payload.percent,
        status: payload.status || 'Downloading...'
      });
      if (payload.percent === 100) {
        // Refresh models list once download is complete
        setTimeout(() => {
          setPullProgress(null);
          setIsPulling(false);
          fetchData();
        }, 2000);
      }
    });

    return () => {
      unsubProgress();
    };
  }, [fetchData]);

  const handlePull = async () => {
    if (!pullInput.trim() || isPulling) return;
    
    try {
      setIsPulling(true);
      setError(null);
      await AuraCoreAPI.pullModel(pullInput.trim());
      setPullInput('');
    } catch (err) {
      setError(`Failed to start pulling ${pullInput}`);
      setIsPulling(false);
    }
  };

  const handleDelete = async (name: string) => {
    if (!window.confirm(`Are you sure you want to delete the model "${name}"? This action cannot be undone.`)) return;
    
    try {
      await AuraCoreAPI.deleteModel(name);
      await fetchData();
    } catch (err) {
      setError(`Failed to delete model ${name}`);
    }
  };

  const handleSwitchModel = async (name: string) => {
    if (name === activeModel) return;
    if (!window.confirm(`Switch active model to ${name}? This will unload the current model from VRAM.`)) return;

    try {
      await AuraCoreAPI.updateConfig({ default_model: name });
      // Update local preference as well
      setModelPreference(name);
      // Refresh to show changes
      await fetchData();
    } catch (err) {
      setError(`Failed to switch to ${name}`);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-950">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-10 h-10 text-blue-500 animate-spin" />
          <p className="text-gray-500 font-medium animate-pulse">Loading Model Library...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto bg-gray-950 p-6 space-y-8 custom-scrollbar">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Model Management</h1>
          <p className="text-gray-500 text-sm mt-1">Control your local AI brains and system resources.</p>
        </div>
        <button 
          onClick={fetchData} 
          className="p-2 text-gray-400 hover:text-blue-400 hover:bg-blue-500/10 rounded-xl transition-all"
          title="Refresh library"
        >
          <RefreshCw size={20} />
        </button>
      </div>

      {/* Active Model & VRAM Usage */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-gray-900 border border-gray-800 rounded-3xl p-6 shadow-xl relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-64 h-64 bg-blue-500/5 blur-[100px] -mr-32 -mt-32 group-hover:bg-blue-500/10 transition-colors" />
          
          <div className="relative">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-bold text-gray-100 flex items-center gap-2">
                <Zap className="text-yellow-400 w-5 h-5" />
                Active Model
              </h2>
              {activeModel && (
                <span className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-green-500/10 text-green-400 text-[10px] font-bold uppercase tracking-wider border border-green-500/20">
                  <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
                  Loaded in Memory
                </span>
              )}
            </div>
            
            {activeModel ? (
              <div className="flex items-start justify-between">
                <div className="space-y-4">
                  <div>
                    <p className="text-3xl font-mono font-bold text-blue-400 leading-tight">{activeModel}</p>
                    <p className="text-sm text-gray-500 mt-1">Provider: Internal Ollama</p>
                  </div>
                  
                  <div className="flex flex-wrap gap-6">
                    <div className="space-y-1">
                      <p className="text-[10px] text-gray-500 uppercase tracking-widest font-bold">Disk Size</p>
                      <div className="flex items-center gap-2 text-gray-200">
                        <HardDrive size={16} className="text-blue-500" />
                        <span className="font-mono">{formatBytes(models.find(m => m.name === activeModel)?.size || 0)}</span>
                      </div>
                    </div>
                    <div className="space-y-1">
                      <p className="text-[10px] text-gray-500 uppercase tracking-widest font-bold">VRAM Usage</p>
                      <div className="flex items-center gap-2 text-gray-200">
                        <Cpu size={16} className="text-purple-500" />
                        <span className="font-mono">{activeVram > 0 ? formatBytes(activeVram) : 'Dynamic Allocation'}</span>
                      </div>
                    </div>
                  </div>
                </div>
                <div className="hidden sm:block p-4 rounded-3xl bg-blue-500/10 text-blue-400">
                  <BrainCircuit size={48} />
                </div>
              </div>
            ) : (
              <div className="py-8 text-center">
                <p className="text-gray-500 italic">No model is currently loaded. Start a conversation to initialize Aura.</p>
              </div>
            )}
          </div>
        </div>

        {/* Hardware Recommendation Card */}
        <div className="bg-blue-600/10 border border-blue-500/20 rounded-3xl p-6 flex flex-col justify-between">
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-blue-400">
              <Layers size={20} />
              <h2 className="font-bold uppercase tracking-tight text-sm">Hardware Recommendation</h2>
            </div>
            <p className="text-xs text-blue-100/70 leading-relaxed">
              Based on your system's detected RAM and CPU/GPU capabilities, we recommend the following variant for optimal performance:
            </p>
            <div className="p-3 bg-blue-500/20 rounded-xl border border-blue-500/30">
              <p className="text-lg font-mono font-bold text-white text-center">{recommendedModel}</p>
            </div>
          </div>
          
          {recommendedModel && !models.some(m => m.name === recommendedModel) && (
            <button 
              onClick={() => setPullInput(recommendedModel)}
              className="mt-6 w-full py-2 bg-blue-500 hover:bg-blue-400 text-white rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2"
            >
              <Download size={14} />
              Download Recommended
            </button>
          )}
        </div>
      </section>

      {/* Model Puller & Progress */}
      <section className="space-y-4">
        <h2 className="text-lg font-bold text-gray-100 flex items-center gap-2">
          <Download className="text-purple-400 w-5 h-5" />
          Download from Ollama Library
        </h2>
        
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1 relative group">
            <input 
              type="text" 
              value={pullInput}
              onChange={(e) => setPullInput(e.target.value)}
              placeholder="Enter model name (e.g. gemma4:e2b, llama3...)"
              className="w-full bg-gray-900 border border-gray-800 rounded-2xl px-5 py-3 text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all placeholder:text-gray-600"
            />
          </div>
          <button 
            onClick={handlePull}
            disabled={isPulling || !pullInput.trim()}
            className={cn(
              "px-8 py-3 rounded-2xl font-bold flex items-center justify-center gap-2 transition-all shadow-lg",
              isPulling || !pullInput.trim()
                ? "bg-gray-800 text-gray-600 cursor-not-allowed"
                : "bg-blue-600 hover:bg-blue-500 text-white shadow-blue-500/20"
            )}
          >
            {isPulling ? <Loader2 size={18} className="animate-spin" /> : <Download size={18} />}
            Start Download
          </button>
        </div>

        {pullProgress && (
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5 space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400">
                  <Loader2 size={16} className="animate-spin" />
                </div>
                <span className="font-mono font-bold text-gray-200">{pullProgress.model}</span>
              </div>
              <span className="text-xs font-mono font-bold text-blue-400">{pullProgress.percent}%</span>
            </div>
            
            <div className="relative h-2 w-full bg-gray-800 rounded-full overflow-hidden">
              <div 
                className="absolute top-0 left-0 h-full bg-blue-500 transition-all duration-300 ease-out shadow-[0_0_12px_rgba(59,130,246,0.5)]"
                style={{ width: `${pullProgress.percent}%` }}
              />
            </div>
            
            <div className="flex justify-between items-center text-[10px] font-bold uppercase tracking-widest text-gray-500">
              <span>{pullProgress.status}</span>
              {pullProgress.percent === 100 && <span className="text-green-400 flex items-center gap-1"><CheckCircle2 size={12} /> Complete</span>}
            </div>
          </div>
        )}
      </section>

      {/* Local Library List */}
      <section className="space-y-4">
        <h2 className="text-lg font-bold text-gray-100 flex items-center gap-2">
          <HardDrive className="text-green-400 w-5 h-5" />
          Local Library
        </h2>
        
        {models.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {models.map((model) => (
              <div 
                key={model.name}
                className={cn(
                  "bg-gray-900 border rounded-2xl p-5 flex flex-col justify-between group transition-all relative overflow-hidden",
                  activeModel === model.name 
                    ? "border-blue-500/50 bg-blue-500/5 ring-1 ring-blue-500/20" 
                    : "border-gray-800 hover:border-gray-700 hover:bg-gray-800/50"
                )}
              >
                {activeModel === model.name && (
                  <div className="absolute top-0 right-0 w-16 h-16 bg-blue-500/10 blur-2xl -mr-8 -mt-8" />
                )}
                
                <div className="flex items-start justify-between relative">
                  <div className="space-y-1 min-w-0">
                    <p className="font-mono font-bold text-gray-100 group-hover:text-blue-400 transition-colors truncate pr-2" title={model.name}>
                      {model.name}
                    </p>
                    <div className="flex items-center gap-3 text-xs text-gray-500">
                      <span>{formatBytes(model.size)}</span>
                      <span>•</span>
                      <span>Ollama</span>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-1 shrink-0">
                    {activeModel !== model.name && (
                      <button 
                        onClick={() => handleSwitchModel(model.name)}
                        className="p-2 text-gray-500 hover:text-blue-400 hover:bg-blue-500/10 rounded-lg transition-all"
                        title="Load model"
                      >
                        <Play size={18} fill="currentColor" />
                      </button>
                    )}
                    <button 
                      onClick={() => handleDelete(model.name)}
                      className="p-2 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-all"
                      title="Delete model"
                    >
                      <Trash2 size={18} />
                    </button>
                  </div>
                </div>
                
                <div className="mt-6 flex items-center justify-between">
                  <div className="flex -space-x-1">
                    {/* Visual indicators for model features could go here */}
                    <div className="w-6 h-6 rounded-full bg-gray-800 border-2 border-gray-900 flex items-center justify-center" title="Chat Support">
                       <MessageSquare size={10} className="text-gray-400" />
                    </div>
                    {model.name.includes('vision') && (
                       <div className="w-6 h-6 rounded-full bg-gray-800 border-2 border-gray-900 flex items-center justify-center" title="Vision Support">
                          <ImageIcon size={10} className="text-gray-400" />
                       </div>
                    )}
                  </div>
                  
                  {activeModel === model.name && (
                    <div className="text-[9px] font-bold uppercase tracking-widest text-blue-400 flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-blue-500/10 border border-blue-500/20">
                      <div className="w-1 h-1 bg-blue-400 rounded-full animate-pulse" />
                      Currently Active
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-gray-900/30 border border-gray-800 border-dashed rounded-3xl p-16 text-center">
            <div className="mx-auto w-16 h-16 rounded-full bg-gray-900 flex items-center justify-center text-gray-700 mb-4">
              <HardDrive size={32} />
            </div>
            <p className="text-gray-500 font-medium">Your library is currently empty.</p>
            <p className="text-xs text-gray-600 mt-1">Download a model above to begin using Aura.</p>
          </div>
        )}
      </section>

      {/* Floating Error Toast */}
      {error && (
        <div className="fixed bottom-8 right-8 bg-red-600 text-white px-6 py-4 rounded-2xl shadow-2xl flex items-center gap-4 animate-in slide-in-from-right-8 fade-in duration-300 z-50">
          <div className="p-2 bg-white/10 rounded-lg">
            <AlertCircle size={20} />
          </div>
          <div>
            <p className="text-xs font-bold uppercase tracking-widest opacity-70">Operation Failed</p>
            <p className="text-sm font-medium">{error}</p>
          </div>
          <button onClick={() => setError(null)} className="ml-4 p-1 hover:bg-white/10 rounded-full transition-colors">
            <X size={16} />
          </button>
        </div>
      )}
    </div>
  );
};

// Internal icon components used in the sidebar logic or similar but needed here for the list
const BrainCircuit: React.FC<{ size: number }> = ({ size }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .52 8.105 4 4 0 0 0 8.003 0 4 4 0 0 0 .52-8.105 4 4 0 0 0-2.52-5.77A3 3 0 0 0 12 5Z" />
    <path d="M9 13h.01" />
    <path d="M15 13h.01" />
    <path d="M12 17h.01" />
  </svg>
);

const MessageSquare: React.FC<{ size: number, className?: string }> = ({ size, className }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>
);

const ImageIcon: React.FC<{ size: number, className?: string }> = ({ size, className }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <rect width="18" height="18" x="3" y="3" rx="2" ry="2" />
    <circle cx="9" cy="9" r="2" />
    <path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21" />
  </svg>
);

const X: React.FC<{ size: number }> = ({ size }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M18 6 6 18" />
    <path d="m6 6 12 12" />
  </svg>
);
