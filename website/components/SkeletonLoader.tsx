'use client';

import { motion } from 'framer-motion';

interface SkeletonProps {
  className?: string;
  variant?: 'text' | 'circular' | 'rectangular' | 'rounded';
  width?: string | number;
  height?: string | number;
  animation?: 'pulse' | 'wave' | 'none';
}

export function Skeleton({
  className = '',
  variant = 'rectangular',
  width,
  height,
  animation = 'pulse',
}: SkeletonProps) {
  const baseClasses = 'bg-slate-800';

  const variantClasses = {
    text: 'h-4 rounded',
    circular: 'rounded-full',
    rectangular: 'rounded-sm',
    rounded: 'rounded-lg',
  };

  const animationComponent = {
    pulse: (
      <motion.div
        className={`${baseClasses} ${variantClasses[variant]} ${className}`}
        style={{ width, height }}
        animate={{ opacity: [0.4, 0.8, 0.4] }}
        transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
      />
    ),
    wave: (
      <motion.div
        className={`${baseClasses} ${variantClasses[variant]} ${className} overflow-hidden relative`}
        style={{ width, height }}
      >
        <motion.div
          className="absolute inset-0 bg-gradient-to-r from-transparent via-slate-700 to-transparent"
          animate={{ x: ['-100%', '200%'] }}
          transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
        />
      </motion.div>
    ),
    none: (
      <div
        className={`${baseClasses} ${variantClasses[variant]} ${className}`}
        style={{ width, height }}
      />
    ),
  };

  return animationComponent[animation];
}

// Pre-configured skeleton components
export function CardSkeleton() {
  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6 space-y-4">
      <div className="flex items-center gap-4">
        <Skeleton variant="circular" width={48} height={48} />
        <div className="flex-1 space-y-2">
          <Skeleton variant="text" width="60%" />
          <Skeleton variant="text" width="40%" />
        </div>
      </div>
      <Skeleton variant="text" className="h-3" />
      <Skeleton variant="text" className="h-3" />
      <Skeleton variant="text" width="80%" className="h-3" />
    </div>
  );
}

export function HeroSkeleton() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center space-y-8 max-w-4xl mx-auto px-4">
        <Skeleton variant="text" width="70%" height={80} className="mx-auto" />
        <Skeleton variant="text" width="90%" height={32} className="mx-auto" />
        <div className="flex justify-center gap-8">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="text-center space-y-2">
              <Skeleton variant="text" width={80} height={48} />
              <Skeleton variant="text" width={60} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function PipelineSkeleton() {
  return (
    <div className="py-20 space-y-8">
      <div className="text-center space-y-4">
        <Skeleton variant="text" width="40%" height={48} className="mx-auto" />
        <Skeleton variant="text" width="60%" height={24} className="mx-auto" />
      </div>

      {/* Pipeline stages skeleton */}
      <div className="flex flex-wrap justify-center gap-4">
        {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((i) => (
          <Skeleton key={i} variant="rounded" width={140} height={100} />
        ))}
      </div>

      {/* Connection lines skeleton */}
      <div className="flex justify-center">
        <Skeleton variant="text" width="80%" height={4} />
      </div>
    </div>
  );
}

export function StatsSkeleton() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="bg-slate-900/50 border border-slate-800 rounded-xl p-6 text-center space-y-2">
          <Skeleton variant="text" width={80} height={40} className="mx-auto" />
          <Skeleton variant="text" width={60} className="mx-auto" />
        </div>
      ))}
    </div>
  );
}
