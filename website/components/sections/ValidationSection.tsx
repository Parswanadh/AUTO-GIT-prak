'use client';

import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';

const stages = [
  { name: 'SYNTAX', tool: 'ast.parse', weight: '40%', icon: '📝', color: '#00D4FF' },
  { name: 'TYPE CHECK', tool: 'mypy', weight: '20%', icon: '🔍', color: '#7C3AED' },
  { name: 'SECURITY', tool: 'bandit', weight: '25%', icon: '🛡️', color: '#EF4444' },
  { name: 'LINT', tool: 'ruff', weight: '15%', icon: '✨', color: '#F59E0B' },
  { name: 'QUALITY', tool: 'threshold ≥ 50', weight: 'Gate', icon: '📊', color: '#10B981' },
];

const exampleResult = [
  { name: 'Syntax', score: 100, max: 100, status: '✓', color: '#10B981', note: 'valid Python AST' },
  { name: 'Types', score: 92, max: 100, status: '✓', color: '#10B981', note: '2 missing annotations' },
  { name: 'Security', score: 85, max: 100, status: '⚠', color: '#F59E0B', note: 'hardcoded salt detected' },
  { name: 'Lint', score: 96, max: 100, status: '✓', color: '#10B981', note: '2 style issues' },
];

export default function ValidationSection() {
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
            5-Stage Quality Gate
          </h2>
          <p className="text-lg text-[rgba(248,250,252,0.7)] max-w-3xl mx-auto">
            Before any code ships — every file passes through syntax checking, type analysis,
            security scanning, linting, and quality scoring.
          </p>
        </motion.div>

        {/* Pipeline Stages */}
        <div className="flex flex-col md:flex-row gap-3 mb-16 items-stretch">
          {stages.map((s, i) => (
            <motion.div
              key={s.name}
              initial={{ opacity: 0, y: 30 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.4, delay: 0.2 + i * 0.12 }}
              className="flex-1 relative"
            >
              <div
                className="bg-[rgba(3,7,18,0.8)] border rounded-xl p-5 text-center h-full hover-lift"
                style={{ borderColor: `${s.color}30` }}
              >
                <div className="text-3xl mb-2">{s.icon}</div>
                <h3 className="font-orbitron font-bold text-sm mb-1" style={{ color: s.color }}>
                  {s.name}
                </h3>
                <div className="font-mono text-xs text-[rgba(248,250,252,0.5)] mb-2">{s.tool}</div>
                <div
                  className="inline-block font-mono font-bold text-xs px-2 py-1 rounded"
                  style={{ background: `${s.color}20`, color: s.color }}
                >
                  Weight: {s.weight}
                </div>
              </div>
              {/* Arrow connector */}
              {i < stages.length - 1 && (
                <div className="hidden md:block absolute top-1/2 -right-3 transform -translate-y-1/2 text-[rgba(0,212,255,0.3)] text-lg z-10">
                  →
                </div>
              )}
            </motion.div>
          ))}
        </div>

        {/* Example Validation Result */}
        <div className="grid md:grid-cols-2 gap-8">
          <motion.div
            initial={{ opacity: 0, x: -30 }}
            animate={isInView ? { opacity: 1, x: 0 } : {}}
            transition={{ duration: 0.5, delay: 0.6 }}
            className="bg-[rgba(0,0,0,0.6)] border border-[rgba(0,212,255,0.15)] rounded-xl p-6"
          >
            <div className="font-mono text-sm mb-4">
              <span className="text-[rgba(248,250,252,0.4)]">File: </span>
              <span className="text-[#00D4FF]">auth.py</span>
            </div>
            {exampleResult.map((r, i) => (
              <motion.div
                key={r.name}
                initial={{ opacity: 0, x: -20 }}
                animate={isInView ? { opacity: 1, x: 0 } : {}}
                transition={{ duration: 0.3, delay: 0.7 + i * 0.1 }}
                className="flex items-center gap-3 mb-3"
              >
                <span className="text-lg">{r.status}</span>
                <span className="font-mono text-sm w-20 text-[rgba(248,250,252,0.6)]">{r.name}:</span>
                <div className="flex-1 h-2 bg-[rgba(0,212,255,0.08)] rounded-full overflow-hidden">
                  <motion.div
                    className="h-full rounded-full"
                    style={{ backgroundColor: r.color }}
                    initial={{ width: '0%' }}
                    animate={isInView ? { width: `${r.score}%` } : {}}
                    transition={{ duration: 0.8, delay: 0.8 + i * 0.1 }}
                  />
                </div>
                <span className="font-mono text-xs" style={{ color: r.color }}>
                  {r.score}/{r.max}
                </span>
              </motion.div>
            ))}
            <div className="mt-4 pt-4 border-t border-[rgba(0,212,255,0.1)] flex items-center justify-between">
              <span className="font-mono text-sm text-[rgba(248,250,252,0.5)]">Quality Score:</span>
              <span className="font-orbitron font-bold text-xl text-[#10B981]">93/100 ✓ PASSED</span>
            </div>
          </motion.div>

          {/* Runtime Testing */}
          <motion.div
            initial={{ opacity: 0, x: 30 }}
            animate={isInView ? { opacity: 1, x: 0 } : {}}
            transition={{ duration: 0.5, delay: 0.8 }}
            className="bg-[rgba(0,0,0,0.6)] border border-[rgba(0,212,255,0.15)] rounded-xl p-6"
          >
            <h3 className="font-orbitron font-semibold text-[#00D4FF] mb-4">
              Runtime Testing
            </h3>
            <div className="space-y-4 font-mono text-sm">
              {[
                { step: 'Create isolated Python venv', status: '✓', color: '#10B981' },
                { step: 'Install from cleaned requirements.txt', status: '✓', color: '#10B981' },
                { step: 'Run python main.py', status: '✓', color: '#10B981' },
                { step: '30-second timeout guard', status: '✓', color: '#10B981' },
                { step: 'Capture stdout/stderr for diagnosis', status: '✓', color: '#10B981' },
              ].map((item, i) => (
                <motion.div
                  key={item.step}
                  initial={{ opacity: 0, y: 10 }}
                  animate={isInView ? { opacity: 1, y: 0 } : {}}
                  transition={{ duration: 0.3, delay: 0.9 + i * 0.1 }}
                  className="flex items-center gap-3"
                >
                  <span style={{ color: item.color }}>{item.status}</span>
                  <span className="text-[rgba(248,250,252,0.6)]">{item.step}</span>
                </motion.div>
              ))}
            </div>
            <div className="mt-6 p-3 rounded-lg bg-[rgba(16,185,129,0.1)] border border-[rgba(16,185,129,0.2)]">
              <div className="text-xs text-[#10B981] font-mono">
                The code actually runs — not just syntactically valid, actually executes in a sandbox.
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
