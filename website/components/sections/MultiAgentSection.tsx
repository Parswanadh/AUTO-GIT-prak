'use client';

import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';

const experts = [
  {
    icon: '🧑‍🔬',
    role: 'Network Engineer',
    focus: 'WebSocket protocol, async I/O, concurrency',
    color: '#00D4FF',
  },
  {
    icon: '🧑‍💻',
    role: 'Security Architect',
    focus: 'Auth, E2E encryption, JWT tokens, rate limiting',
    color: '#7C3AED',
  },
  {
    icon: '📊',
    role: 'Systems Designer',
    focus: 'Scalability, database design, message persistence',
    color: '#10B981',
  },
];

const steps = [
  {
    num: 1,
    title: 'Expert Generation',
    desc: 'LLM dynamically invents 3 domain-specific experts per topic — NOT hardcoded roles.',
    icon: '🧠',
  },
  {
    num: 2,
    title: 'Independent Proposals',
    desc: 'Each expert proposes a complete solution architecture independently, in parallel via asyncio.gather().',
    icon: '💡',
  },
  {
    num: 3,
    title: 'Cross-Critique',
    desc: 'Each expert reviews ALL proposals — creating an N² critique matrix with strengths, weaknesses, recommendations.',
    icon: '⚔️',
  },
  {
    num: 4,
    title: 'Consensus Scoring',
    desc: 'Weighted scoring: accept=1.0, revise=0.5, reject=0.0. Below 0.7 threshold → re-debate automatically.',
    icon: '🤝',
  },
];

export default function MultiAgentSection() {
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
            Three AI Experts. One Debate. Best Solution Wins.
          </h2>
          <p className="text-lg text-[rgba(248,250,252,0.7)] max-w-3xl mx-auto">
            Inspired by the{' '}
            <span className="text-[#00D4FF]">STORM Paper</span> (Stanford, 2024)
            — multi-perspective synthesis produces higher quality than a single
            LLM call. Like code review, but automated with 3 specialized
            reviewers.
          </p>
        </motion.div>

        {/* Expert Cards */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={isInView ? { opacity: 1 } : {}}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="grid md:grid-cols-3 gap-6 mb-16"
        >
          {experts.map((expert, i) => (
            <motion.div
              key={expert.role}
              initial={{ opacity: 0, y: 40 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.5, delay: 0.3 + i * 0.15 }}
              className="relative bg-[rgba(3,7,18,0.8)] border rounded-xl p-6 hover-lift"
              style={{ borderColor: `${expert.color}33` }}
            >
              <div className="text-4xl mb-3">{expert.icon}</div>
              <h3
                className="font-orbitron font-semibold text-lg mb-2"
                style={{ color: expert.color }}
              >
                {expert.role}
              </h3>
              <p className="text-sm text-[rgba(248,250,252,0.6)]">
                Focus: {expert.focus}
              </p>
              {/* Speech bubble */}
              <motion.div
                initial={{ opacity: 0, scale: 0.8 }}
                animate={isInView ? { opacity: 1, scale: 1 } : {}}
                transition={{ duration: 0.4, delay: 0.8 + i * 0.2 }}
                className="mt-4 p-3 rounded-lg text-xs font-mono"
                style={{
                  background: `${expert.color}15`,
                  borderLeft: `3px solid ${expert.color}`,
                }}
              >
                {i === 0 && (
                  <>
                    &ldquo;JWT refresh token rotation is well designed, but E2E
                    encryption adds 15ms latency per message.&rdquo;
                  </>
                )}
                {i === 1 && (
                  <>
                    &ldquo;WebSocket approach is solid but needs rate limiting to
                    prevent DoS on handshake endpoints.&rdquo;
                  </>
                )}
                {i === 2 && (
                  <>
                    &ldquo;Message persistence needs sharding strategy for &gt;10K
                    concurrent users.&rdquo;
                  </>
                )}
              </motion.div>
            </motion.div>
          ))}
        </motion.div>

        {/* 4-Step Process */}
        <div className="grid md:grid-cols-2 gap-6 mb-16">
          {steps.map((step, i) => (
            <motion.div
              key={step.title}
              initial={{ opacity: 0, x: i % 2 === 0 ? -30 : 30 }}
              animate={isInView ? { opacity: 1, x: 0 } : {}}
              transition={{ duration: 0.5, delay: 0.4 + i * 0.15 }}
              className="bg-[rgba(3,7,18,0.8)] border border-[rgba(0,212,255,0.15)] rounded-xl p-6 hover-glow"
            >
              <div className="flex items-center gap-3 mb-3">
                <span className="text-2xl">{step.icon}</span>
                <span className="font-orbitron text-[#00D4FF] font-semibold text-xs">
                  STEP {step.num}
                </span>
                <h3 className="font-orbitron font-semibold text-white">
                  {step.title}
                </h3>
              </div>
              <p className="text-sm text-[rgba(248,250,252,0.65)] leading-relaxed">
                {step.desc}
              </p>
            </motion.div>
          ))}
        </div>

        {/* Consensus Scoring Visual */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, delay: 0.8 }}
          className="bg-[rgba(3,7,18,0.9)] border border-[rgba(0,212,255,0.2)] rounded-xl p-8"
        >
          <h3 className="font-orbitron font-semibold text-[#00D4FF] text-lg mb-6 text-center">
            Live Consensus Scoring
          </h3>
          <div className="flex flex-col md:flex-row items-center justify-center gap-6">
            {/* Round 1 */}
            <div className="flex-1 text-center">
              <div className="text-sm text-[rgba(248,250,252,0.5)] mb-2 font-mono">
                Round 1
              </div>
              <div className="relative w-32 h-32 mx-auto mb-3">
                <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                  <circle
                    cx="50"
                    cy="50"
                    r="42"
                    fill="none"
                    stroke="rgba(0,212,255,0.1)"
                    strokeWidth="8"
                  />
                  <motion.circle
                    cx="50"
                    cy="50"
                    r="42"
                    fill="none"
                    stroke="#F59E0B"
                    strokeWidth="8"
                    strokeLinecap="round"
                    strokeDasharray={`${0.58 * 264} ${264}`}
                    initial={{ strokeDashoffset: 264 }}
                    animate={isInView ? { strokeDashoffset: 0 } : {}}
                    transition={{ duration: 1.5, delay: 1 }}
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-2xl font-bold text-[#F59E0B]">0.58</span>
                </div>
              </div>
              <div className="text-[#F59E0B] font-semibold text-sm">
                Below 0.7 → RE-DEBATE
              </div>
            </div>

            {/* Arrow */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={isInView ? { opacity: 1 } : {}}
              transition={{ delay: 1.5 }}
              className="text-[rgba(248,250,252,0.3)] text-3xl"
            >
              →
            </motion.div>

            {/* Round 2 */}
            <div className="flex-1 text-center">
              <div className="text-sm text-[rgba(248,250,252,0.5)] mb-2 font-mono">
                Round 2
              </div>
              <div className="relative w-32 h-32 mx-auto mb-3">
                <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
                  <circle
                    cx="50"
                    cy="50"
                    r="42"
                    fill="none"
                    stroke="rgba(0,212,255,0.1)"
                    strokeWidth="8"
                  />
                  <motion.circle
                    cx="50"
                    cy="50"
                    r="42"
                    fill="none"
                    stroke="#10B981"
                    strokeWidth="8"
                    strokeLinecap="round"
                    strokeDasharray={`${0.83 * 264} ${264}`}
                    initial={{ strokeDashoffset: 264 }}
                    animate={isInView ? { strokeDashoffset: 0 } : {}}
                    transition={{ duration: 1.5, delay: 1.8 }}
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-2xl font-bold text-[#10B981]">0.83</span>
                </div>
              </div>
              <div className="text-[#10B981] font-semibold text-sm">
                Above 0.7 → ACCEPTED ✓
              </div>
            </div>
          </div>

          {/* Why better */}
          <div className="mt-8 grid md:grid-cols-2 gap-4 text-sm">
            <div className="p-4 rounded-lg bg-[rgba(239,68,68,0.1)] border border-[rgba(239,68,68,0.2)]">
              <div className="text-[#EF4444] font-semibold mb-1">
                ❌ Single LLM Call
              </div>
              <p className="text-[rgba(248,250,252,0.6)]">
                &ldquo;Build a chat app&rdquo; → gets ONE perspective, misses
                security, scalability, edge cases
              </p>
            </div>
            <div className="p-4 rounded-lg bg-[rgba(16,185,129,0.1)] border border-[rgba(16,185,129,0.2)]">
              <div className="text-[#10B981] font-semibold mb-1">
                ✅ Multi-Agent Debate
              </div>
              <p className="text-[rgba(248,250,252,0.6)]">
                3 perspectives, each critiques the others, finds blind spots →
                more robust architecture
              </p>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
