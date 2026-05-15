import React, { useState, useEffect, useCallback } from 'react';
import { 
  ShieldAlert, 
  Check, 
  X, 
  Clock, 
  Terminal,
  ShieldCheck,
  ShieldBan
} from 'lucide-react';
import { useToolStore } from '../../stores/toolStore';
import { auraWs } from '../../api/core';
import { getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const PermissionDialog: React.FC = () => {
  const { pendingApprovals, addPendingApproval, approve, deny } = useToolStore();
  const [timeLeft, setTimeLeft] = useState(60);
  const currentRequest = pendingApprovals[0];

  useEffect(() => {
    const unsub = auraWs.subscribe('tool_approval_needed', (payload) => {
      addPendingApproval(payload);
      // Show window when request arrives
      getCurrentWebviewWindow().show();
      getCurrentWebviewWindow().setFocus();
      setTimeLeft(60);
    });

    return () => unsub();
  }, [addPendingApproval]);

  useEffect(() => {
    if (!currentRequest) {
      getCurrentWebviewWindow().hide();
      return;
    }

    const timer = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          handleDeny();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [currentRequest]);

  const handleApprove = async () => {
    if (!currentRequest) return;
    await approve(currentRequest.request_id);
  };

  const handleDeny = async () => {
    if (!currentRequest) return;
    await deny(currentRequest.request_id);
  };

  if (!currentRequest) return null;

  const progress = (timeLeft / 60) * 100;
  const radius = 16;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (progress / 100) * circumference;

  return (
    <div className="h-screen w-screen bg-gray-950 text-gray-100 flex flex-col border border-gray-800 shadow-2xl overflow-hidden select-none">
      {/* Header */}
      <div className={cn(
        "p-4 flex items-center justify-between border-b",
        currentRequest.risk_level === 'high' ? "bg-red-500/10 border-red-500/20" : "bg-amber-500/10 border-amber-500/20"
      )}>
        <div className="flex items-center gap-3">
          <div className={cn(
            "p-2 rounded-lg",
            currentRequest.risk_level === 'high' ? "bg-red-500 text-white" : "bg-amber-500 text-white"
          )}>
            <ShieldAlert size={20} />
          </div>
          <div>
            <h2 className="font-bold text-sm uppercase tracking-tight">Security Approval Required</h2>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={cn(
                "text-[10px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider",
                currentRequest.risk_level === 'high' ? "bg-red-500/20 text-red-400" : "bg-amber-500/20 text-amber-400"
              )}>
                {currentRequest.risk_level} Risk
              </span>
              <span className="text-[10px] text-gray-500 font-mono">{currentRequest.request_id.slice(0, 8)}</span>
            </div>
          </div>
        </div>

        {/* Countdown Ring */}
        <div className="relative w-10 h-10 flex items-center justify-center">
          <svg className="w-10 h-10 transform -rotate-90">
            <circle
              cx="20"
              cy="20"
              r={radius}
              stroke="currentColor"
              strokeWidth="3"
              fill="transparent"
              className="text-gray-800"
            />
            <circle
              cx="20"
              cy="20"
              r={radius}
              stroke="currentColor"
              strokeWidth="3"
              fill="transparent"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              strokeLinecap="round"
              className={cn(
                "transition-all duration-1000",
                timeLeft > 10 ? "text-blue-500" : "text-red-500"
              )}
            />
          </svg>
          <span className="absolute text-[10px] font-bold">{timeLeft}</span>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 p-5 space-y-4 overflow-y-auto custom-scrollbar">
        <div className="space-y-1">
          <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Tool Name</label>
          <div className="flex items-center gap-2 text-blue-400 font-mono font-bold">
            <Terminal size={14} />
            {currentRequest.tool_name}
          </div>
        </div>

        <div className="space-y-1">
          <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Description</label>
          <p className="text-sm text-gray-200 leading-relaxed">
            {currentRequest.description}
          </p>
        </div>

        <div className="space-y-1">
          <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Parameters</label>
          <div className="bg-black/50 border border-gray-800 rounded-xl p-3">
            <pre className="text-xs font-mono text-gray-400 overflow-x-auto">
              {JSON.stringify(currentRequest.args, null, 2)}
            </pre>
          </div>
        </div>
        
        <div className="p-3 rounded-lg bg-gray-900 border border-gray-800 flex items-start gap-2">
          <ShieldAlert size={14} className="text-amber-500 shrink-0 mt-0.5" />
          <p className="text-[10px] text-gray-500 leading-tight">
            Allowing this operation grants the AI permission to perform actions that may modify your system or data.
          </p>
        </div>
      </div>

      {/* Footer / Actions */}
      <div className="p-4 bg-gray-900/50 border-t border-gray-800 flex gap-3">
        <button
          onClick={handleDeny}
          className="flex-1 flex items-center justify-center gap-2 bg-gray-800 hover:bg-gray-700 text-gray-300 py-3 rounded-xl font-bold transition-all border border-gray-700"
        >
          <ShieldBan size={18} />
          Deny
        </button>
        <button
          onClick={handleApprove}
          className={cn(
            "flex-1 flex items-center justify-center gap-2 py-3 rounded-xl font-bold transition-all shadow-lg",
            currentRequest.risk_level === 'high' 
              ? "bg-red-600 hover:bg-red-500 text-white shadow-red-500/20" 
              : "bg-blue-600 hover:bg-blue-500 text-white shadow-blue-500/20"
          )}
        >
          <ShieldCheck size={18} />
          Approve
        </button>
      </div>
    </div>
  );
};
