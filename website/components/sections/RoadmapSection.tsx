'use client';

import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';

const completed = [
  '15-node LangGraph pipeline',
  'Multi-agent debate system',
  'Self-improving error memory',
  '5-stage validation pipeline',
  '12-bug-type code review',
  'Strategy reasoner (reasoning-in-the-loop)',
  'Smart model management (5-tier fallback)',
  'GitHub auto-publishing',
  '27 successful pipeline runs',
];

const inProgress = [
  'SQL schema cross-validation',
  'Runtime execution testing improvements',
  'More shadow file patterns',
];

const planned = [
  'Multi-language support (Rust, Go, TypeScript)',
  'Auto-generated test suites (pytest)',
  'MCP (Model Context Protocol) integration',
  'Performance profiling dashboard',
  'Community release',
];

export default function RoadmapSection() {
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
            Roadmap
          </h2>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-6">
          {/* Completed */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="bg-[rgba(3,7,18,0.8)] border border-[rgba(16,185,129,0.2)] rounded-xl p-6"
          >
            <div className="flex items-center gap-2 mb-6">
              <span className="w-3 h-3 rounded-full bg-[#10B981]" />
              <h3 className="font-orbitron font-semibold text-[#10B981] text-sm uppercase tracking-wider">
                Completed ✅
              </h3>
            </div>
            <div className="space-y-3">
              {completed.map((item, i) => (
                <motion.div
                  key={item}
                  initial={{ opacity: 0, x: -10 }}
                  animate={isInView ? { opacity: 1, x: 0 } : {}}
                  transition={{ duration: 0.3, delay: 0.3 + i * 0.05 }}
                  className="flex items-start gap-2 text-sm"
                >
                  <span className="text-[#10B981] mt-0.5 text-xs">✓</span>
                  <span className="text-[rgba(248,250,252,0.6)]">{item}</span>
                </motion.div>
              ))}
            </div>
          </motion.div>

          {/* In Progress */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.5, delay: 0.4 }}
            className="bg-[rgba(3,7,18,0.8)] border border-[rgba(245,158,11,0.2)] rounded-xl p-6"
          >
            <div className="flex items-center gap-2 mb-6">
              <span className="w-3 h-3 rounded-full bg-[#F59E0B] animate-pulse" />
              <h3 className="font-orbitron font-semibold text-[#F59E0B] text-sm uppercase tracking-wider">
                In Progress 🔄
              </h3>
            </div>
            <div className="space-y-3">
              {inProgress.map((item, i) => (
                <motion.div
                  key={item}
                  initial={{ opacity: 0, x: -10 }}
                  animate={isInView ? { opacity: 1, x: 0 } : {}}
                  transition={{ duration: 0.3, delay: 0.5 + i * 0.05 }}
                  className="flex items-start gap-2 text-sm"
                >
                  <span className="text-[#F59E0B] mt-0.5 text-xs">◉</span>
                  <span className="text-[rgba(248,250,252,0.6)]">{item}</span>
                </motion.div>
              ))}
            </div>
          </motion.div>

          {/* Planned */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.5, delay: 0.6 }}
            className="bg-[rgba(3,7,18,0.8)] border border-[rgba(0,212,255,0.2)] rounded-xl p-6"
          >
            <div className="flex items-center gap-2 mb-6">
              <span className="w-3 h-3 rounded-full bg-[rgba(0,212,255,0.5)]" />
              <h3 className="font-orbitron font-semibold text-[#00D4FF] text-sm uppercase tracking-wider">
                Planned 📋
              </h3>
            </div>
            <div className="space-y-3">
              {planned.map((item, i) => (
                <motion.div
                  key={item}
                  initial={{ opacity: 0, x: -10 }}
                  animate={isInView ? { opacity: 1, x: 0 } : {}}
                  transition={{ duration: 0.3, delay: 0.7 + i * 0.05 }}
                  className="flex items-start gap-2 text-sm"
                >
                  <span className="text-[rgba(0,212,255,0.5)] mt-0.5 text-xs">○</span>
                  <span className="text-[rgba(248,250,252,0.5)]">{item}</span>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
