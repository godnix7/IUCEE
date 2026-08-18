import React, { createContext, useContext, useState, useCallback } from 'react';
import type { ReactNode } from 'react';
import { X, CheckCircle, AlertCircle, Info } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'info';

export interface ToastMessage {
  id: string;
  type: ToastType;
  message: string;
}

interface ToastContextType {
  addToast: (message: string, type: ToastType) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const ToastProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = useCallback((message: string, type: ToastType) => {
    // Generate simple ID
    const id = Date.now().toString() + Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => removeToast(id), 5000);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ addToast, removeToast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`flex items-center gap-3 p-4 rounded-xl shadow-2xl border backdrop-blur-md min-w-[300px] max-w-[400px] transform transition-all duration-300 translate-y-0 opacity-100 ${
              toast.type === 'success' ? 'bg-[#064e3b]/90 border-emerald-500/50 text-emerald-100' :
              toast.type === 'error' ? 'bg-[#7f1d1d]/90 border-red-500/50 text-red-100' :
              'bg-[#1e3a8a]/90 border-blue-500/50 text-blue-100'
            }`}
          >
            {toast.type === 'success' && <CheckCircle className="text-emerald-400" size={20} />}
            {toast.type === 'error' && <AlertCircle className="text-red-400" size={20} />}
            {toast.type === 'info' && <Info className="text-blue-400" size={20} />}
            <p className="flex-1 text-sm font-medium">{toast.message}</p>
            <button
              onClick={() => removeToast(toast.id)}
              className="p-1 hover:bg-white/10 rounded-full transition-colors shrink-0"
            >
              <X size={16} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
};

export const useToast = () => {
  const context = useContext(ToastContext);
  if (context === undefined) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};
