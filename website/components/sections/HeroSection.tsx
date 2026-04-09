'use client';

import { motion, useInView } from 'framer-motion';
import { useRef, useEffect, useState } from 'react';
import { EVIDENCE_AS_OF, evidenceMetrics } from '@/data/evidenceMetrics';
import TrustBadges from '@/components/TrustBadges';
import { usePresentationMode } from '@/components/PresentationModeProvider';

// Animated counter component
function AnimatedCounter({ value, duration = 2, skipAnimation = false }: { value: string; duration?: number; skipAnimation?: boolean }) {
  const targetValue = parseInt(value.replace(/,/g, ''), 10);
  const [count, setCount] = useState(0);
  const [isVisible, setIsVisible] = useState(false);
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-100px' });

  useEffect(() => {
    if (skipAnimation) {
      setCount(targetValue);
      return;
    }

    if (inView && !isVisible) {
      setIsVisible(true);
      const startTime = Date.now();

      const animate = () => {
        const elapsed = Date.now() - startTime;
        const progress = Math.min(elapsed / (duration * 1000), 1);

        // Easing function for smooth animation
        const easeOutQuart = 1 - Math.pow(1 - progress, 4);
        const currentCount = Math.floor(targetValue * easeOutQuart);

        setCount(currentCount);

        if (progress < 1) {
          requestAnimationFrame(animate);
        }
      };

      requestAnimationFrame(animate);
    }
  }, [inView, isVisible, duration, targetValue, skipAnimation]);

  return (
    <span ref={ref}>
      {(skipAnimation ? targetValue : count).toLocaleString()}
    </span>
  );
}

export default function HeroSection() {
  const { effectiveMode, motionTier } = usePresentationMode();
  const isLowMotion = motionTier === 'low';
  const durationFactor = effectiveMode === 'evidence' ? 0.6 : 1;

  const stats = [
    { value: String(evidenceMetrics.pipelineNodes.value), label: 'Pipeline nodes', icon: '⚙️' },
    { value: String(evidenceMetrics.unitTestsCollected.value), label: 'Collected unit tests', icon: '🧪' },
    { value: String(evidenceMetrics.sourcePythonLoc.value), label: 'Python LOC in src', icon: '💻' },
    { value: String(evidenceMetrics.errorMemoryEntries.value), label: 'Error-memory entries', icon: '🧠' },
  ];

  const evidencePills = [
    `${evidenceMetrics.pipelineNodes.value}-node orchestrated pipeline`,
    `${evidenceMetrics.unitTestsCollected.value} collected unit tests`,
    `${evidenceMetrics.errorMemoryEntries.value} error-memory entries`,
  ];

  return (
    <section className="relative min-h-screen flex items-center justify-center pt-16">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <motion.div
          className="mx-auto mb-4 inline-flex items-center gap-2 rounded-full border border-[rgba(0,212,255,0.35)] bg-[rgba(0,212,255,0.12)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-[#7DD3FC]"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.42 * durationFactor, ease: 'easeOut' }}
        >
          Judge Showcase
          <span className="text-[rgba(248,250,252,0.7)]">Mode: {effectiveMode}</span>
        </motion.div>

        <motion.h1
          className="font-orbitron font-bold text-4xl sm:text-5xl md:text-6xl lg:text-7xl mb-6 bg-gradient-to-r from-[#00D4FF] via-[#7C3AED] to-[#10B981] bg-clip-text text-transparent"
          initial={{ opacity: 0, y: 30, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.75 * durationFactor, ease: 'easeOut' }}
          whileHover={isLowMotion ? {} : { scale: 1.01 }}
        >
          From Idea To Tested Repo In One Autonomous Run
        </motion.h1>

        <motion.p
          className="text-lg md:text-2xl text-[rgba(248,250,252,0.78)] max-w-4xl mx-auto mb-8 font-rajdhani"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65 * durationFactor, delay: 0.15, ease: 'easeOut' }}
        >
          Auto-GIT runs a full 19-stage engineering loop: research, multi-agent debate, code generation,
          validation, repair, and publish-ready outputs with evidence-first reporting.
        </motion.p>

        <motion.div
          className="mx-auto mb-8 flex max-w-4xl flex-wrap items-center justify-center gap-3"
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55 * durationFactor, delay: 0.22, ease: 'easeOut' }}
        >
          <a
            href="#demo"
            className="rounded-xl border border-cyan-300/40 bg-cyan-400/15 px-5 py-3 text-sm font-semibold text-cyan-200 transition-colors hover:bg-cyan-400/25"
          >
            Watch 60s Demo
          </a>
          <a
            href="#metrics"
            className="rounded-xl border border-violet-300/40 bg-violet-400/15 px-5 py-3 text-sm font-semibold text-violet-200 transition-colors hover:bg-violet-400/25"
          >
            View Evidence Metrics
          </a>
          <a
            href="https://github.com/Parswanadh/auto-git"
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-xl border border-slate-300/30 bg-slate-700/20 px-5 py-3 text-sm font-semibold text-slate-200 transition-colors hover:bg-slate-700/40"
          >
            Open Source Repo
          </a>
        </motion.div>

        <motion.p
          className="mx-auto mb-8 text-sm text-[rgba(248,250,252,0.62)]"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 * durationFactor, delay: 0.28 }}
        >
          Need a hands-free booth walkthrough?
          {' '}
          <a href="/?autodemo=1&autospeed=28#hero" className="font-semibold text-cyan-300 hover:text-cyan-200">
            Launch auto tour mode
          </a>
        </motion.p>

        <TrustBadges />

        <motion.div
          className="mx-auto mb-10 flex max-w-5xl flex-wrap items-center justify-center gap-3"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 * durationFactor, delay: 0.35, ease: 'easeOut' }}
        >
          {evidencePills.map((pill, index) => (
            <motion.div
              key={pill}
              className="rounded-full border border-[rgba(0,212,255,0.35)] bg-[linear-gradient(135deg,rgba(0,212,255,0.16),rgba(124,58,237,0.14))] px-4 py-2 text-sm font-semibold text-[rgba(248,250,252,0.92)] shadow-[0_0_18px_rgba(0,212,255,0.16)]"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.42 * durationFactor, delay: 0.42 + index * 0.09, ease: 'easeOut' }}
              whileHover={isLowMotion ? {} : { y: -2, scale: 1.02 }}
            >
              {pill}
            </motion.div>
          ))}
          <span className="text-xs text-[rgba(248,250,252,0.56)]">Evidence snapshot: {EVIDENCE_AS_OF}</span>
        </motion.div>

        <div className="flex flex-wrap justify-center gap-8 mb-12">
          {stats.map((stat, index) => (
            <motion.div
              key={stat.label}
              className="relative group"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45 * durationFactor, delay: 0.45 + index * 0.08, ease: 'easeOut' }}
              whileHover={isLowMotion ? {} : { y: -6, transition: { duration: 0.2 } }}
            >
              <motion.div
                className="absolute -top-3 -right-3 w-8 h-8 bg-gradient-to-br from-[#00D4FF] to-[#7C3AED] rounded-full flex items-center justify-center text-sm shadow-lg"
                initial={{ scale: 0, rotate: -180 }}
                animate={{ scale: 1, rotate: 0 }}
                transition={{ duration: 0.5 * durationFactor, delay: 0.55 + index * 0.08, type: 'spring' }}
                whileHover={isLowMotion ? {} : { rotate: 360, scale: 1.08 }}
              >
                {stat.icon}
              </motion.div>

              <div className="bg-[rgba(3,7,18,0.8)] border-2 border-[rgba(0,212,255,0.2)] rounded-2xl px-6 py-4 relative overflow-hidden">
                <motion.div
                  className="absolute inset-0 bg-gradient-to-br from-[rgba(0,212,255,0.1)] to-transparent"
                  initial={{ opacity: 0 }}
                  whileHover={isLowMotion ? {} : { opacity: 1 }}
                  transition={{ duration: 0.3 }}
                />

                <motion.div
                  className="text-4xl md:text-5xl font-bold text-[#00D4FF] font-orbitron relative z-10"
                  whileHover={isLowMotion ? {} : {
                    scale: 1.06,
                    textShadow: '0 0 20px rgba(0, 212, 255, 0.6), 0 0 32px rgba(124, 58, 237, 0.45)',
                  }}
                >
                  <AnimatedCounter value={stat.value} duration={1.5 * durationFactor} skipAnimation={isLowMotion} />
                </motion.div>

                <div className="text-sm text-[rgba(248,250,252,0.5)] mt-1 relative z-10">{stat.label}</div>

                <motion.div
                  className="absolute inset-0 bg-gradient-to-r from-transparent via-white to-transparent opacity-0"
                  whileHover={isLowMotion ? {} : { opacity: 0.08, x: ['0%', '180%'] }}
                  transition={{ duration: 0.6 }}
                />
              </div>
            </motion.div>
          ))}
        </div>

        {!isLowMotion && (
          <motion.div
            className="absolute bottom-8 left-1/2 transform -translate-x-1/2 flex flex-col items-center gap-2 cursor-pointer"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 1 * durationFactor, delay: 1.1 }}
            onClick={() => {
              const nextSection = document.querySelector('#problem');
              nextSection?.scrollIntoView({ behavior: 'smooth' });
            }}
          >
            <motion.p
              className="text-sm text-[rgba(248,250,252,0.5)] font-rajdhani"
              animate={{ opacity: [0.5, 1, 0.5] }}
              transition={{ duration: 2.1, repeat: Infinity }}
            >
              Scroll to explore
            </motion.p>
            <motion.div
              className="w-6 h-10 border-2 border-[rgba(0,212,255,0.4)] rounded-full flex justify-center pt-2"
              animate={{ borderColor: ['rgba(0,212,255,0.4)', 'rgba(0,212,255,0.8)', 'rgba(0,212,255,0.4)'] }}
              transition={{ duration: 2, repeat: Infinity }}
            >
              <motion.div
                className="w-1.5 h-3 bg-[#00D4FF] rounded-full"
                animate={{ y: [0, 12, 0] }}
                transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
              />
            </motion.div>
          </motion.div>
        )}
      </div>
    </section>
  );
}
