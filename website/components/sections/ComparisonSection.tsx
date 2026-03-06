'use client';

import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';

const features = [
  { feature: 'Multi-file projects', gpt: '❌ Single file', copilot: '❌ Autocomplete', autogit: '✅ 3-11 files' },
  { feature: 'Research before coding', gpt: '❌ No', copilot: '❌ No', autogit: '✅ arXiv + web + GitHub' },
  { feature: 'Multi-expert debate', gpt: '❌ No', copilot: '❌ No', autogit: '✅ 3 domain experts' },
  { feature: 'Cross-file validation', gpt: '❌ No', copilot: '❌ No', autogit: '✅ AST-based analysis' },
  { feature: 'Security scanning', gpt: '❌ No', copilot: '❌ No', autogit: '✅ Bandit integration' },
  { feature: 'Auto-fix loop', gpt: '❌ Manual', copilot: '❌ Manual', autogit: '✅ Strategy → Fix → Test' },
  { feature: 'Learns from mistakes', gpt: '❌ No', copilot: '❌ No', autogit: '✅ 233 error entries' },
  { feature: 'Publishes to GitHub', gpt: '❌ Copy-paste', copilot: '❌ No', autogit: '✅ Auto repo + push' },
  { feature: 'Runs generated code', gpt: '❌ No', copilot: '❌ No', autogit: '✅ Sandbox testing' },
  { feature: 'Self-evaluation', gpt: '❌ No', copilot: '❌ No', autogit: '✅ 4-dimension scoring' },
];

export default function ComparisonSection() {
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
          className="text-center mb-12"
        >
          <h2 className="font-orbitron font-bold text-3xl md:text-5xl mb-4 bg-gradient-to-r from-[#00D4FF] to-[#7C3AED] bg-clip-text text-transparent">
            How Auto-GIT Compares
          </h2>
        </motion.div>

        {/* Comparison Table */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="overflow-x-auto bg-[rgba(3,7,18,0.8)] border border-[rgba(0,212,255,0.15)] rounded-xl"
        >
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[rgba(0,212,255,0.2)]">
                <th className="p-4 text-left text-[rgba(248,250,252,0.5)] font-orbitron text-xs uppercase tracking-wider">
                  Feature
                </th>
                <th className="p-4 text-center text-[rgba(248,250,252,0.4)] font-orbitron text-xs">
                  ChatGPT
                </th>
                <th className="p-4 text-center text-[rgba(248,250,252,0.4)] font-orbitron text-xs">
                  GitHub Copilot
                </th>
                <th className="p-4 text-center font-orbitron text-xs" style={{ color: '#00D4FF' }}>
                  Auto-GIT
                </th>
              </tr>
            </thead>
            <tbody>
              {features.map((row, i) => (
                <motion.tr
                  key={row.feature}
                  initial={{ opacity: 0, x: -10 }}
                  animate={isInView ? { opacity: 1, x: 0 } : {}}
                  transition={{ duration: 0.3, delay: 0.3 + i * 0.06 }}
                  className="border-b border-[rgba(0,212,255,0.05)] hover:bg-[rgba(0,212,255,0.03)] transition-colors"
                >
                  <td className="p-4 text-[rgba(248,250,252,0.7)] font-medium">{row.feature}</td>
                  <td className="p-4 text-center text-[rgba(248,250,252,0.4)] text-xs">{row.gpt}</td>
                  <td className="p-4 text-center text-[rgba(248,250,252,0.4)] text-xs">{row.copilot}</td>
                  <td className="p-4 text-center text-[#10B981] text-xs font-semibold">{row.autogit}</td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </motion.div>
      </div>
    </section>
  );
}
