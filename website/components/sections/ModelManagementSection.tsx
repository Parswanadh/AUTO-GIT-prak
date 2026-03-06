'use client';

import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';

const tiers = [
  {
    tier: 1,
    name: 'OpenRouter FREE',
    models: ['Qwen3-Coder 480B (free)', 'Trinity-Large 400B (free)'],
    status: '429 Rate Limited → Response received ✓',
    color: '#10B981',
    desc: 'Try free models first',
  },
  {
    tier: 2,
    name: 'OpenRouter PAID',
    models: ['DeepSeek Chat v3 — $0.07/1M', 'Gemini 2.5 Flash — $0.10/1M'],
    status: 'Low-cost fallback',
    color: '#3B82F6',
    desc: 'Cheap premium models',
  },
  {
    tier: 3,
    name: 'Groq Multi-Key Pool',
    models: ['Up to 8 independent API keys', 'Each with own rate limit'],
    status: 'Key 1: 429 ✗ Key 2: 429 ✗ Key 3: OK ✓',
    color: '#F59E0B',
    desc: 'Parallel key rotation',
  },
  {
    tier: 4,
    name: 'OpenAI gpt-4o-mini',
    models: ['Always available cloud model'],
    status: 'Last cloud resort',
    color: '#7C3AED',
    desc: 'Guaranteed availability',
  },
  {
    tier: 5,
    name: 'Ollama Local',
    models: ['Run on your own GPU'],
    status: '$0, offline capable',
    color: '#EF4444',
    desc: 'Fully offline fallback',
  },
];

const profiles = [
  {
    name: 'fast',
    usage: 'Extraction, simple parsing',
    models: 'Small 3B-30B models',
    why: 'Speed over quality',
    icon: '⚡',
    color: '#F59E0B',
  },
  {
    name: 'balanced',
    usage: 'Problem extraction, debate',
    models: '70B (Llama 3.3)',
    why: 'Good balance',
    icon: '⚖️',
    color: '#3B82F6',
  },
  {
    name: 'powerful',
    usage: 'Code generation, review',
    models: '400B-480B (Qwen3-Coder, Trinity)',
    why: 'Maximum quality',
    icon: '🚀',
    color: '#7C3AED',
  },
  {
    name: 'reasoning',
    usage: 'Critique, strategy, root-cause',
    models: 'DeepSeek R1',
    why: 'Deep thinking',
    icon: '🧠',
    color: '#10B981',
  },
  {
    name: 'research',
    usage: 'Web search + synthesis',
    models: 'Groq compound-beta',
    why: 'Built-in web search',
    icon: '🔍',
    color: '#00D4FF',
  },
];

const smartFeatures = [
  {
    title: 'Health Cache',
    desc: 'Dead models (404) permanently blacklisted. Rate-limited models (429) get 60-second cooldown.',
    icon: '💊',
  },
  {
    title: 'Per-Model Timeouts',
    desc: 'DeepSeek R1 gets 300s (slow but smart). Flash models get 25s. Based on real latency data.',
    icon: '⏱️',
  },
  {
    title: 'Multi-Key Pool',
    desc: '5-8 Groq API keys rotating. A rate limit on Key 1 doesn\'t block Key 2.',
    icon: '🔑',
  },
  {
    title: 'Token Tracking',
    desc: 'Every LLM call logged — prompt tokens, completion tokens, total cost tracked per run.',
    icon: '📊',
  },
];

export default function ModelManagementSection() {
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
            27+ AI Models. Zero Cost. Intelligent Fallback.
          </h2>
          <p className="text-lg text-[rgba(248,250,252,0.7)] max-w-3xl mx-auto">
            Free AI models have rate limits, go offline, and vary wildly in quality.
            The solution: a 5-tier provider cascade — like load balancer failover for API endpoints.
          </p>
        </motion.div>

        {/* 5-Tier Cascade */}
        <div className="mb-16 space-y-3">
          {tiers.map((tier, i) => (
            <motion.div
              key={tier.tier}
              initial={{ opacity: 0, x: -40 }}
              animate={isInView ? { opacity: 1, x: 0 } : {}}
              transition={{ duration: 0.5, delay: 0.2 + i * 0.12 }}
              className="relative bg-[rgba(3,7,18,0.8)] border rounded-xl p-5 hover-lift"
              style={{ borderColor: `${tier.color}30` }}
            >
              <div className="flex flex-col md:flex-row md:items-center gap-4">
                <div
                  className="flex items-center gap-3 md:w-56 shrink-0"
                >
                  <span
                    className="font-orbitron font-bold text-xs px-2 py-1 rounded"
                    style={{ background: `${tier.color}25`, color: tier.color }}
                  >
                    TIER {tier.tier}
                  </span>
                  <span className="font-orbitron font-semibold text-white text-sm">
                    {tier.name}
                  </span>
                </div>
                <div className="flex-1 text-sm text-[rgba(248,250,252,0.6)]">
                  {tier.models.join(' · ')}
                </div>
                <div
                  className="text-xs font-mono px-3 py-1 rounded-full shrink-0"
                  style={{ background: `${tier.color}15`, color: tier.color }}
                >
                  {tier.desc}
                </div>
              </div>
              {/* Connector arrow */}
              {i < tiers.length - 1 && (
                <div className="absolute -bottom-3 left-8 text-[rgba(248,250,252,0.15)] text-lg z-10">
                  ↓
                </div>
              )}
            </motion.div>
          ))}
        </div>

        {/* Model Profiles */}
        <motion.h3
          initial={{ opacity: 0 }}
          animate={isInView ? { opacity: 1 } : {}}
          transition={{ delay: 0.8 }}
          className="font-orbitron font-semibold text-xl text-center mb-8 text-white"
        >
          5 Model Profiles
        </motion.h3>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-16">
          {profiles.map((p, i) => (
            <motion.div
              key={p.name}
              initial={{ opacity: 0, y: 30 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.4, delay: 0.9 + i * 0.1 }}
              className="bg-[rgba(3,7,18,0.8)] border border-[rgba(0,212,255,0.15)] rounded-xl p-4 text-center hover-glow"
            >
              <div className="text-2xl mb-2">{p.icon}</div>
              <div
                className="font-mono font-bold text-sm mb-1"
                style={{ color: p.color }}
              >
                {p.name}
              </div>
              <div className="text-xs text-[rgba(248,250,252,0.5)] mb-2">
                {p.usage}
              </div>
              <div className="text-xs text-[rgba(248,250,252,0.4)] font-mono">
                {p.models}
              </div>
            </motion.div>
          ))}
        </div>

        {/* Smart Features */}
        <div className="grid md:grid-cols-2 gap-4">
          {smartFeatures.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 20 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.4, delay: 1.2 + i * 0.1 }}
              className="bg-[rgba(3,7,18,0.8)] border border-[rgba(0,212,255,0.12)] rounded-xl p-5 flex gap-4"
            >
              <span className="text-2xl">{f.icon}</span>
              <div>
                <h4 className="font-orbitron font-semibold text-[#00D4FF] text-sm mb-1">
                  {f.title}
                </h4>
                <p className="text-sm text-[rgba(248,250,252,0.6)]">{f.desc}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
