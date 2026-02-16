import { create } from 'zustand';
import { motion, AnimatePresence } from 'framer-motion';

type ToastType = 'success' | 'error' | 'info' | 'warning';

interface Toast {
  id: number;
  message: string;
  type: ToastType;
}

interface ToastStore {
  toasts: Toast[];
  add: (message: string, type?: ToastType) => void;
  remove: (id: number) => void;
}

let toastId = 0;

export const useToastStore = create<ToastStore>((set) => ({
  toasts: [],
  add: (message, type = 'info') => {
    const id = ++toastId;
    set((s) => ({ toasts: [...s.toasts, { id, message, type }] }));
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
    }, 4000);
  },
  remove: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

const typeStyles: Record<ToastType, string> = {
  success: 'border-profit/50 bg-profit/10 text-profit',
  error: 'border-loss/50 bg-loss/10 text-loss',
  info: 'border-blue/50 bg-blue/10 text-blue',
  warning: 'border-orange/50 bg-orange/10 text-orange',
};

export function ToastContainer() {
  const { toasts, remove } = useToastStore();

  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2 pointer-events-none">
      <AnimatePresence>
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            initial={{ opacity: 0, y: 20, x: 20 }}
            animate={{ opacity: 1, y: 0, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.2 }}
            className={`pointer-events-auto border rounded-lg px-4 py-3 text-sm font-medium shadow-lg cursor-pointer ${typeStyles[toast.type]}`}
            onClick={() => remove(toast.id)}
          >
            {toast.message}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
