'use client';

import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';

const subsystems = [
  {
    title: 'Research Engine',
    color: '#00D4FF',
    items: ['arXiv API', 'DuckDuckGo', 'SearXNG'],
    icon: '🔍',
  },
  {
    title: 'Multi-Agent Debate',
    color: '#7C3AED',
    items: ['3 Dynamic Experts', 'N² Critique Matrix', 'Consensus Scoring'],
    icon: '🧠',
  },
  {
    title: 'Code Generation',
    color: '#10B981',
    items: ['Architect Spec', 'Parallel Codegen', 'Interface Contracts'],
    icon: '💻',
  },
];

const selfHealing = [
  { name: 'Code Review', desc: '12 bug types', icon: '🔍' },
  { name: 'Strategy Reasoner', desc: 'Root cause analysis', icon: '🧠' },
  { name: 'Code Fixer', desc: 'Strategic fixes', icon: '🔧' },
  { name: 'Test Runner', desc: 'Sandbox execution', icon: '🧪' },
];

const infrastructure = [
  { name: '5-Stage Validator', desc: 'syntax → types → security → lint → score', icon: '✅' },
  { name: 'Error Memory (JSONL)', desc: '233 entries, learns from past runs', icon: '📝' },
  { name: 'Model Manager', desc: '5-tier fallback, 27+ models, health cache', icon: '🤖' },
];

export default function ArchitectureSection() {
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
            System Architecture
          </h2>
        </motion.div>

        {/* Architecture Container */}
        <div className="relative bg-[rgba(3,7,18,0.6)] border border-[rgba(0,212,255,0.15)] rounded-2xl p-6 md:p-8">
          {/* Title Bar */}
          <div className="text-center mb-8">
            <span className="font-orbitron font-bold text-sm text-[rgba(248,250,252,0.3)] tracking-widest uppercase">
              Auto-GIT Pipeline
            </span>
          </div>

          {/* Top Row: 3 Main Subsystems */}
          <div className="grid md:grid-cols-3 gap-4 mb-6">
            {subsystems.map((s, i) => (
              <motion.div
                key={s.title}
                initial={{ opacity: 0, y: 20 }}
                animate={isInView ? { opacity: 1, y: 0 } : {}}
                transition={{ duration: 0.4, delay: 0.2 + i * 0.12 }}
                className="bg-[rgba(0,0,0,0.4)] border rounded-xl p-5"
                style={{ borderColor: `${s.color}30` }}
              >
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xl">{s.icon}</span>
                  <h3 className="font-orbitron font-semibold text-sm" style={{ color: s.color }}>
                    {s.title}
                  </h3>
                </div>
                <div className="space-y-1">
                  {s.items.map((item) => (
                    <div key={item} className="text-xs text-[rgba(248,250,252,0.5)] flex items-center gap-2">
                      <span style={{ color: s.color }}>•</span> {item}
                    </div>
                  ))}
                </div>
              </motion.div>
            ))}
          </div>

          {/* Arrow Down */}
          <div className="text-center text-[rgba(0,212,255,0.3)] text-2xl mb-4">↓</div>

          {/* Self-Healing Loop */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.5, delay: 0.5 }}
            className="bg-[rgba(0,0,0,0.4)] border border-[rgba(245,158,11,0.2)] rounded-xl p-5 mb-6"
          >
            <h3 className="font-orbitron font-semibold text-sm text-[#F59E0B] mb-4 text-center">
              Self-Healing Loop
            </h3>
            <div className="flex flex-wrap justify-center items-center gap-3">
              {selfHealing.map((s, i) => (
                <div key={s.name} className="flex items-center gap-2">
                  <div className="bg-[rgba(245,158,11,0.1)] border border-[rgba(245,158,11,0.15)] rounded-lg px-3 py-2 text-center">
                    <div className="text-lg">{s.icon}</div>
                    <div className="text-xs text-[#F59E0B] font-semibold">{s.name}</div>
                    <div className="text-[10px] text-[rgba(248,250,252,0.4)]">{s.desc}</div>
                  </div>
                  {i < selfHealing.length - 1 && (
                    <span className="text-[rgba(245,158,11,0.4)]">→</span>
                  )}
                </div>
              ))}
              <span className="text-[rgba(245,158,11,0.4)]">↩</span>
            </div>
          </motion.div>

          {/* Arrow Down */}
          <div className="text-center text-[rgba(0,212,255,0.3)] text-2xl mb-4">↓</div>

          {/* Infrastructure Row */}
          <div className="grid md:grid-cols-3 gap-4 mb-6">
            {infrastructure.map((inf, i) => (
              <motion.div
                key={inf.name}
                initial={{ opacity: 0, y: 20 }}
                animate={isInView ? { opacity: 1, y: 0 } : {}}
                transition={{ duration: 0.4, delay: 0.7 + i * 0.1 }}
                className="bg-[rgba(0,0,0,0.4)] border border-[rgba(0,212,255,0.12)] rounded-xl p-4"
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-lg">{inf.icon}</span>
                  <h4 className="font-orbitron font-semibold text-xs text-[#00D4FF]">{inf.name}</h4>
                </div>
                <p className="text-xs text-[rgba(248,250,252,0.5)]">{inf.desc}</p>
              </motion.div>
            ))}
          </div>

          {/* Arrow Down */}
          <div className="text-center text-[rgba(0,212,255,0.3)] text-2xl mb-4">↓</div>

          {/* Output */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={isInView ? { opacity: 1 } : {}}
            transition={{ delay: 1 }}
            className="bg-gradient-to-r from-[rgba(0,212,255,0.1)] to-[rgba(124,58,237,0.1)] border border-[rgba(0,212,255,0.2)] rounded-xl p-4 text-center"
          >
            <span className="text-lg mr-2">🚀</span>
            <span className="font-orbitron font-semibold text-sm text-white">
              Output: GitHub Repository with code, README, requirements
            </span>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
