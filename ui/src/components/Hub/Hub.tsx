import React, { useState } from 'react';
import { 
  MessageSquare, 
  Layers, 
  Settings as SettingsIcon, 
  Search,
  LayoutDashboard,
  BrainCircuit
} from 'lucide-react';
import { ChatView } from './ChatView';
import { ModelsView } from './ModelsView';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const Hub: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'chat' | 'models' | 'settings'>('chat');

  return (
    <div className="flex h-screen w-screen bg-gray-950 text-gray-100 overflow-hidden">
      {/* Sidebar */}
      <div className="w-20 flex flex-col items-center py-8 bg-gray-900 border-r border-gray-800 space-y-8">
        <div className="p-3 rounded-2xl bg-blue-600 shadow-lg shadow-blue-500/20">
          <BrainCircuit size={28} className="text-white" />
        </div>

        <nav className="flex-1 flex flex-col gap-4">
          <TabButton 
            active={activeTab === 'chat'} 
            onClick={() => setActiveTab('chat')} 
            icon={<MessageSquare size={24} />} 
            label="Chat"
          />
          <TabButton 
            active={activeTab === 'models'} 
            onClick={() => setActiveTab('models')} 
            icon={<Layers size={24} />} 
            label="Models"
          />
        </nav>

        <TabButton 
          active={activeTab === 'settings'} 
          onClick={() => setActiveTab('settings')} 
          icon={<SettingsIcon size={24} />} 
          label="Settings"
        />
      </div>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 bg-gray-950">
        <header className="h-16 border-b border-gray-800 flex items-center justify-between px-8 bg-gray-950/50 backdrop-blur-md">
          <h1 className="text-lg font-bold capitalize flex items-center gap-2">
            {activeTab === 'chat' && <MessageSquare size={18} className="text-blue-400" />}
            {activeTab === 'models' && <Layers size={18} className="text-purple-400" />}
            {activeTab === 'settings' && <SettingsIcon size={18} className="text-gray-400" />}
            {activeTab}
          </h1>
          
          <div className="flex items-center gap-4">
            <div className="relative group">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 group-focus-within:text-blue-400 transition-colors" size={16} />
              <input 
                type="text" 
                placeholder="Search memory..." 
                className="bg-gray-900 border border-gray-800 rounded-full py-1.5 pl-10 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all w-48 focus:w-64"
              />
            </div>
            <div className="w-8 h-8 rounded-full bg-blue-600/20 border border-blue-500/30 flex items-center justify-center">
              <span className="text-[10px] font-bold text-blue-400">A</span>
            </div>
          </div>
        </header>

        <div className="flex-1 overflow-hidden flex flex-col">
          {activeTab === 'chat' && <ChatView />}
          {activeTab === 'models' && <ModelsView />}
          {activeTab === 'settings' && (
            <div className="flex-1 flex items-center justify-center text-gray-500">
              <p>Settings coming soon...</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

interface TabButtonProps {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}

const TabButton: React.FC<TabButtonProps> = ({ active, onClick, icon, label }) => {
  return (
    <button 
      onClick={onClick}
      className={cn(
        "p-3 rounded-2xl transition-all relative group",
        active 
          ? "bg-blue-600/10 text-blue-400 shadow-inner" 
          : "text-gray-500 hover:bg-gray-800 hover:text-gray-300"
      )}
      title={label}
    >
      {icon}
      {active && (
        <div className="absolute left-[-12px] top-1/2 -translate-y-1/2 w-1 h-6 bg-blue-500 rounded-r-full shadow-[0_0_8px_rgba(59,130,246,0.5)]" />
      )}
      <div className="absolute left-full ml-4 px-2 py-1 bg-gray-800 text-white text-[10px] font-bold rounded opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity whitespace-nowrap z-50">
        {label}
      </div>
    </button>
  );
};
