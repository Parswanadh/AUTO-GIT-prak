'use client';

import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';
import CountUp from 'react-countup';

const pipelineMetrics = [
  { value: 47726, label: 'Lines of pipeline source code', suffix: '', color: '#00D4FF' },
  { value: 4839, label: 'Lines in nodes.py (largest file)', suffix: '', color: '#7C3AED' },
  { value: 15, label: 'Pipeline nodes', suffix: '', color: '#10B981' },
  { value: 27, label: 'Completed pipeline runs', suffix: '', color: '#F59E0B' },
  { value: 30, label: 'Avg execution time', suffix: ' min', prefix: '~', color: '#3B82F6' },
  { value: 35000, label: 'Total lines of Python generated', suffix: '+', color: '#EF4444' },
];

const qualityMetrics = [
  { value: 16, label: 'Bug types auto-detected', color: '#EF4444' },
  { value: 233, label: 'Error memory entries', color: '#F59E0B' },
  { value: 12, label: 'Bug types in Code Review', color: '#7C3AED' },
  { value: 5, label: 'Validation stages', color: '#10B981' },
  { value: 0, label: 'Manual fixes (best run)', color: '#00D4FF' },
];

const infraMetrics = [
  { value: 27, label: 'Free AI models available', suffix: '+', color: '#3B82F6' },
  { value: 5, label: 'Provider tiers', color: '#7C3AED' },
  { value: 5, label: 'Model profiles', color: '#10B981' },
  { value: 5, label: 'Search engines integrated', color: '#F59E0B' },
  { value: 8, label: 'Max Groq API keys', color: '#00D4FF' },
];

function MetricCard({ value, label, suffix = '', prefix = '', color, delay }: {
  value: number; label: string; suffix?: string; prefix?: string; color: string; delay: number;
}) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true });

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 20 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.4, delay }}
      className="bg-[rgba(3,7,18,0.8)] border border-[rgba(0,212,255,0.12)] rounded-xl p-5 text-center hover-lift"
    >
      <div className="text-3xl md:text-4xl font-bold font-orbitron mb-2" style={{ color }}>
        {prefix}
        {isInView ? (
          <CountUp end={value} duration={2} separator="," />
        ) : (
          '0'
        )}
        {suffix}
      </div>
      <div className="text-xs text-[rgba(248,250,252,0.5)]">{label}</div>
    </motion.div>
  );
}

export default function MetricsDashboard() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });

  return (
    <section className="relative py-24 lg:py-32" ref={ref}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <h2 className="font-orbitron font-bold text-3xl md:text-5xl mb-4 bg-gradient-to-r from-[#00D4FF] to-[#7C3AED] bg-clip-text text-transparent">
            The Numbers
          </h2>
        </motion.div>

        {/* Pipeline Metrics */}
        <motion.h3
          initial={{ opacity: 0 }}
          animate={isInView ? { opacity: 1 } : {}}
          transition={{ delay: 0.2 }}
          className="font-orbitron font-semibold text-sm text-[rgba(248,250,252,0.4)] uppercase tracking-widest mb-4 text-center"
        >
          Pipeline Metrics
        </motion.h3>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-12">
          {pipelineMetrics.map((m, i) => (
            <MetricCard key={m.label} {...m} delay={0.1 + i * 0.08} />
          ))}
        </div>

        {/* Quality Metrics */}
        <motion.h3
          initial={{ opacity: 0 }}
          animate={isInView ? { opacity: 1 } : {}}
          transition={{ delay: 0.5 }}
          className="font-orbitron font-semibold text-sm text-[rgba(248,250,252,0.4)] uppercase tracking-widest mb-4 text-center"
        >
          Quality Metrics
        </motion.h3>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-12">
          {qualityMetrics.map((m, i) => (
            <MetricCard key={m.label} {...m} delay={0.5 + i * 0.08} />
          ))}
        </div>

        {/* Infrastructure Metrics */}
        <motion.h3
          initial={{ opacity: 0 }}
          animate={isInView ? { opacity: 1 } : {}}
          transition={{ delay: 0.8 }}
          className="font-orbitron font-semibold text-sm text-[rgba(248,250,252,0.4)] uppercase tracking-widest mb-4 text-center"
        >
          Infrastructure Metrics
        </motion.h3>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {infraMetrics.map((m, i) => (
            <MetricCard key={m.label} {...m} delay={0.8 + i * 0.08} />
          ))}
        </div>
      </div>
    </section>
  );
}
