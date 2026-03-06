'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { Loader2 } from 'lucide-react';

interface PageTransitionProps {
  children: React.ReactNode;
  isLoading?: boolean;
}

export default function PageTransition({ children, isLoading }: PageTransitionProps) {
  return (
    <AnimatePresence mode="wait">
      {isLoading ? (
        <motion.div
          key="loading"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[100] flex items-center justify-center bg-[#030712]"
        >
          <div className="flex flex-col items-center gap-6">
            {/* Animated loader */}
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
              className="relative w-16 h-16"
            >
              <div className="absolute inset-0 border-4 border-cyan-500/30 rounded-full" />
              <div className="absolute inset-0 border-4 border-transparent border-t-cyan-500 rounded-full" />
              <div className="absolute inset-2 border-4 border-transparent border-t-purple-500 rounded-full" />
            </motion.div>

            {/* Loading text with dots animation */}
            <div className="flex items-center gap-2 text-cyan-400 font-rajdhani text-lg">
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Loading</span>
              <motion.span
                animate={{ opacity: [0, 1, 0] }}
                transition={{ duration: 1.4, repeat: Infinity }}
                className="font-mono"
              >
                ...
              </motion.span>
            </div>

            {/* Progress bar */}
            <div className="w-48 h-1 bg-slate-800 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-cyan-500 to-purple-600"
                initial={{ width: '0%' }}
                animate={{ width: '100%' }}
                transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
              />
            </div>
          </div>
        </motion.div>
      ) : (
        <motion.div
          key="content"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.5 }}
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
