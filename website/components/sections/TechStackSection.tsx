'use client';

import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';

const techStack = [
  { category: 'Orchestration', tech: 'LangGraph', purpose: 'State machine workflow with conditional routing', icon: '🔄', color: '#00D4FF' },
  { category: 'LLM Providers', tech: 'OpenRouter, Groq, OpenAI, Ollama', purpose: 'Multi-provider fallback cascade', icon: '🤖', color: '#7C3AED' },
  { category: 'Models Used', tech: 'Qwen3-Coder 480B, Llama 3.3, DeepSeek R1, Gemini Flash', purpose: 'Different models for different tasks', icon: '🧠', color: '#10B981' },
  { category: 'Research', tech: 'arXiv API, DuckDuckGo, SearXNG', purpose: 'Multi-source academic + web search', icon: '🔍', color: '#F59E0B' },
  { category: 'Validation', tech: 'mypy, bandit, ruff, Python AST', purpose: 'Type checking, security, linting', icon: '✅', color: '#EF4444' },
  { category: 'Version Control', tech: 'GitHub API (PyGithub)', purpose: 'Auto-create repos and push code', icon: '📦', color: '#3B82F6' },
  { category: 'Runtime', tech: 'Python 3.10, asyncio', purpose: 'Async pipeline execution', icon: '⚡', color: '#F97316' },
  { category: 'Monitoring', tech: 'Rich console, JSONL tracing', purpose: 'Real-time progress + observability', icon: '📊', color: '#8B5CF6' },
  { category: 'Storage', tech: 'SQLite, JSONL', purpose: 'Crash-resume + learning (error memory)', icon: '💾', color: '#14B8A6' },
];

export default function TechStackSection() {
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
            Built With
          </h2>
        </motion.div>

        {/* Tech Grid */}
        <div className="grid md:grid-cols-3 gap-4">
          {techStack.map((t, i) => (
            <motion.div
              key={t.category}
              initial={{ opacity: 0, y: 30 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.4, delay: 0.15 + i * 0.08 }}
              className="bg-[rgba(3,7,18,0.8)] border border-[rgba(0,212,255,0.12)] rounded-xl p-5 hover-lift"
            >
              <div className="flex items-center gap-3 mb-3">
                <span className="text-2xl">{t.icon}</span>
                <div>
                  <div
                    className="font-orbitron font-bold text-xs uppercase tracking-wider"
                    style={{ color: t.color }}
                  >
                    {t.category}
                  </div>
                </div>
              </div>
              <div className="font-mono text-sm text-white mb-2">{t.tech}</div>
              <p className="text-xs text-[rgba(248,250,252,0.5)]">{t.purpose}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
