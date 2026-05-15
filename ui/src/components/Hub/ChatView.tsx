import React, { useState, useRef, useEffect } from 'react';
import TextareaAutosize from 'react-textarea-autosize';
import { Send, StopCircle, User, Bot, Terminal, ChevronDown, ChevronUp, Image as ImageIcon } from 'lucide-react';
import { useChatStore } from '../../stores/chatStore';
import { auraWs } from '../../api/core';
import { Markdown } from '../shared/Markdown';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const ChatView: React.FC = () => {
  const { messages, isStreaming, currentRequestId, addMessage, appendStreamChunk, setStreaming, finalizeStream } = useChatStore();
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: 'smooth'
      });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Subscribe to WebSocket events
  useEffect(() => {
    const unsubChunk = auraWs.subscribe('chat_chunk', (payload) => {
      appendStreamChunk(payload.request_id, payload.delta);
    });

    const unsubDone = auraWs.subscribe('chat_done', () => {
      finalizeStream();
    });

    const unsubToolResult = auraWs.subscribe('tool_result', (payload) => {
      addMessage({
        role: 'tool',
        name: payload.tool_name,
        content: payload.success ? JSON.stringify(payload.output) : (payload.error || 'Unknown error'),
      });
    });

    const unsubError = auraWs.subscribe('error', (payload) => {
      console.error('Chat error:', payload.message);
      finalizeStream();
    });

    return () => {
      unsubChunk();
      unsubDone();
      unsubToolResult();
      unsubError();
    };
  }, [appendStreamChunk, finalizeStream, addMessage]);

  const handleSend = () => {
    if (!input.trim() || isStreaming) return;

    const userMessage = { role: 'user' as const, content: input.trim() };
    addMessage(userMessage);
    
    const requestId = crypto.randomUUID();
    setStreaming(true, requestId);
    
    auraWs.send({
      type: 'chat',
      payload: {
        messages: [...messages, userMessage],
        stream: true,
        request_id: requestId,
      }
    });

    setInput('');
  };

  const handleCancel = () => {
    if (currentRequestId) {
      auraWs.send({
        type: 'cancel',
        payload: { request_id: currentRequestId }
      });
      finalizeStream();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-950 text-gray-100 overflow-hidden">
      {/* Messages List */}
      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 space-y-6 scroll-smooth custom-scrollbar"
      >
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-gray-500 space-y-4">
            <div className="p-4 rounded-full bg-gray-900 border border-gray-800 animate-pulse">
              <Bot size={48} className="text-blue-500 opacity-50" />
            </div>
            <div className="text-center">
              <p className="text-lg font-medium text-gray-300">How can I help you today?</p>
              <p className="text-sm text-gray-600 mt-1">Ask me to analyze your screen, run a command, or just chat.</p>
            </div>
          </div>
        )}
        
        {messages.map((msg, idx) => {
          if (msg.role === 'tool') {
             return <ToolResultCard key={idx} name={msg.name || 'unknown'} output={msg.content} />;
          }

          return (
            <div 
              key={idx} 
              className={cn(
                "flex flex-col max-w-[90%] group",
                msg.role === 'user' ? "ml-auto items-end" : "mr-auto items-start"
              )}
            >
              <div className="flex items-center space-x-2 mb-1 px-1">
                {msg.role === 'assistant' ? (
                  <>
                    <Bot size={14} className="text-blue-400" />
                    <span className="text-[10px] font-bold text-blue-400 uppercase tracking-tighter">Aura</span>
                  </>
                ) : (
                  <>
                    <span className="text-[10px] font-bold text-gray-500 uppercase tracking-tighter">You</span>
                    <User size={14} className="text-gray-500" />
                  </>
                )}
              </div>

              <div className={cn(
                "rounded-2xl px-4 py-3 shadow-lg transition-all",
                msg.role === 'user' 
                  ? "bg-blue-600 text-white rounded-tr-none" 
                  : "bg-gray-900 border border-gray-800 rounded-tl-none"
              )}>
                {msg.images && msg.images.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-3">
                    {msg.images.map((img, i) => (
                      <div key={i} className="relative group/img">
                        <img 
                          src={img.startsWith('data:') ? img : `data:image/jpeg;base64,${img}`} 
                          alt="Screen Capture" 
                          className="max-w-[200px] max-h-[150px] rounded-lg border border-white/20 shadow-md cursor-zoom-in hover:scale-[1.02] transition-transform"
                        />
                        <div className="absolute top-1 right-1 p-1 bg-black/50 rounded-md opacity-0 group-hover/img:opacity-100 transition-opacity">
                          <ImageIcon size={12} className="text-white" />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                
                <Markdown content={msg.content} />
                
                {msg.tool_calls?.map((tc, tidx) => (
                  <ToolCallCard key={tidx} toolCall={tc} />
                ))}
              </div>
            </div>
          );
        })}
        
        {isStreaming && (
          <div className="flex items-center space-x-3 text-blue-400 animate-pulse ml-1">
            <div className="flex space-x-1">
              <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
              <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
              <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce"></div>
            </div>
            <span className="text-[10px] font-bold uppercase tracking-widest opacity-70">Aura is thinking</span>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="p-4 border-t border-gray-800 bg-gray-950/50 backdrop-blur-sm">
        <div className="relative max-w-4xl mx-auto">
          <TextareaAutosize
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask Aura anything..."
            maxRows={8}
            className="w-full bg-gray-900 border border-gray-700 rounded-2xl py-3 pl-4 pr-12 text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all resize-none shadow-inner"
          />
          
          <div className="absolute right-3 bottom-3">
            {isStreaming ? (
              <button
                onClick={handleCancel}
                className="p-1.5 text-red-400 hover:bg-red-500/10 rounded-xl transition-colors border border-red-500/20"
                title="Stop generation"
              >
                <StopCircle size={20} />
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!input.trim()}
                className={cn(
                  "p-1.5 rounded-xl transition-all border",
                  input.trim() 
                    ? "text-blue-400 border-blue-500/20 hover:bg-blue-500/10" 
                    : "text-gray-600 border-transparent cursor-not-allowed"
                )}
              >
                <Send size={20} />
              </button>
            )}
          </div>
        </div>
        <div className="flex justify-center items-center space-x-4 mt-2">
           <p className="text-[9px] text-gray-600 uppercase tracking-tighter">
            <kbd className="bg-gray-800 px-1 rounded text-gray-400">Enter</kbd> to send
          </p>
          <div className="w-1 h-1 bg-gray-800 rounded-full" />
          <p className="text-[9px] text-gray-600 uppercase tracking-tighter">
            <kbd className="bg-gray-800 px-1 rounded text-gray-400">Shift + Enter</kbd> for newline
          </p>
        </div>
      </div>
    </div>
  );
};

const ToolCallCard: React.FC<{ toolCall: any }> = ({ toolCall }) => {
  const [isOpen, setIsOpen] = useState(false);
  const name = toolCall.function?.name || 'unknown_tool';
  const args = JSON.stringify(toolCall.function?.arguments || {}, null, 2);

  return (
    <div className="mt-3 border border-gray-700 rounded-xl overflow-hidden bg-black/40 shadow-inner">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-3 py-2 text-[10px] font-mono text-gray-400 hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center space-x-2">
          <Terminal size={12} className="text-blue-400" />
          <span>Call: <span className="text-blue-400 font-bold">{name}</span></span>
        </div>
        {isOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
      </button>
      
      {isOpen && (
        <div className="px-3 pb-3">
          <pre className="text-[10px] bg-black/50 p-2 rounded-lg border border-white/5 overflow-x-auto text-blue-200/70 font-mono">
            {args}
          </pre>
        </div>
      )}
    </div>
  );
};

const ToolResultCard: React.FC<{ name: string, output: string }> = ({ name, output }) => {
  const [isOpen, setIsOpen] = useState(false);
  
  let formattedOutput = output;
  try {
    const parsed = JSON.parse(output);
    formattedOutput = JSON.stringify(parsed, null, 2);
  } catch (e) {
    // Not JSON, keep as is
  }

  return (
    <div className="flex flex-col items-start max-w-[90%] mr-auto">
      <div className="flex items-center space-x-2 mb-1 px-1">
        <Terminal size={12} className="text-green-400" />
        <span className="text-[10px] font-bold text-green-400 uppercase tracking-tighter">Tool Result: {name}</span>
      </div>
      <div className="w-full border border-green-500/20 rounded-xl overflow-hidden bg-green-500/5 shadow-inner">
        <button 
          onClick={() => setIsOpen(!isOpen)}
          className="w-full flex items-center justify-between px-3 py-2 text-[10px] font-mono text-green-300/70 hover:bg-green-500/10 transition-colors"
        >
          <div className="flex items-center space-x-2">
            <span className="truncate">Output from {name}</span>
          </div>
          {isOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
        
        {isOpen && (
          <div className="px-3 pb-3">
            <pre className="text-[10px] bg-black/40 p-2 rounded-lg border border-green-500/10 overflow-x-auto text-green-200/60 font-mono">
              {formattedOutput}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};
