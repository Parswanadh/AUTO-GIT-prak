'use client';

import { motion, useInView } from 'framer-motion';
import { useRef, useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from 'recharts';

const locData = [
  { pass: 1, lines: 712, date: 'Feb 22', label: '' },
  { pass: 2, lines: 452, date: 'Feb 22', label: '' },
  { pass: 3, lines: 465, date: 'Feb 22', label: '' },
  { pass: 4, lines: 658, date: 'Feb 22', label: '' },
  { pass: 5, lines: 357, date: 'Feb 22', label: '' },
  { pass: 6, lines: 397, date: 'Feb 22', label: '' },
  { pass: 7, lines: 344, date: 'Feb 22', label: '' },
  { pass: 8, lines: 261, date: 'Feb 22', label: 'First main.py' },
  { pass: 9, lines: 701, date: 'Feb 23', label: '' },
  { pass: 10, lines: 328, date: 'Feb 23', label: '' },
  { pass: 11, lines: 465, date: 'Feb 23', label: '' },
  { pass: 12, lines: 453, date: 'Feb 24', label: '' },
  { pass: 13, lines: 818, date: 'Feb 24', label: '' },
  { pass: 14, lines: 1471, date: 'Feb 25', label: 'First 1000+ lines' },
  { pass: 15, lines: 3644, date: 'Feb 25', label: 'Biggest project' },
  { pass: 16, lines: 1873, date: 'Feb 25', label: '' },
  { pass: 17, lines: 1918, date: 'Feb 25', label: '' },
  { pass: 18, lines: 1005, date: 'Feb 25', label: '' },
  { pass: 19, lines: 1991, date: 'Feb 25', label: '' },
  { pass: 20, lines: 1966, date: 'Feb 25', label: '' },
  { pass: 21, lines: 1717, date: 'Feb 25', label: '' },
  { pass: 22, lines: 3325, date: 'Feb 25', label: 'ZERO manual fixes!' },
  { pass: 23, lines: 2659, date: 'Feb 26', label: '' },
  { pass: 24, lines: 638, date: 'Feb 26', label: 'Bad model profiles' },
  { pass: 25, lines: 694, date: 'Feb 26', label: 'Prose-as-code bug' },
  { pass: 26, lines: 1429, date: 'Feb 26', label: 'Shadow file crash' },
  { pass: 27, lines: 2018, date: 'Feb 26', label: '' },
];

const milestoneRuns = [8, 14, 15, 22, 24];

const getBarColor = (pass: number): string => {
  if (milestoneRuns.includes(pass)) return '#00D4FF';
  if (pass >= 24 && pass <= 26) return '#EF4444';
  if (pass >= 14) return '#10B981';
  return '#7C3AED';
};

const runHistory = [
  { pass: 1, name: 'Test Run (ML Training)', date: 'Feb 22', files: 7, lines: 712, status: '⚠️', issue: 'No entry point' },
  { pass: 2, name: 'Quantum Analog Attention', date: 'Feb 22', files: 3, lines: 452, status: '⚠️', issue: 'Library code only' },
  { pass: 3, name: 'Sparse Matrix Multiplication', date: 'Feb 22', files: 3, lines: 465, status: '⚠️', issue: 'No entry point' },
  { pass: 4, name: 'GPU Load Balancer', date: 'Feb 22', files: 4, lines: 658, status: '⚠️', issue: 'No entry point' },
  { pass: 5, name: 'GPU Resource Allocator', date: 'Feb 22', files: 2, lines: 357, status: '⚠️', issue: 'Only 2 files' },
  { pass: 6, name: 'Multimodal LLM Engine', date: 'Feb 22', files: 3, lines: 397, status: '⚠️', issue: 'No entry point' },
  { pass: 7, name: 'GPU Anomaly Detection', date: 'Feb 22', files: 2, lines: 344, status: '⚠️', issue: 'Only 2 files' },
  { pass: 8, name: 'Bias-Aware LLM Patch', date: 'Feb 22', files: 5, lines: 261, status: '✅', issue: 'First main.py!' },
  { pass: 9, name: 'Spike Memory Architecture', date: 'Feb 23', files: 6, lines: 701, status: '⚠️', issue: 'Truncated' },
  { pass: 10, name: 'Event-Driven Spike Cache', date: 'Feb 23', files: 4, lines: 328, status: '⚠️', issue: 'Dead logic' },
  { pass: 11, name: 'Mixed-Signal Neuron', date: 'Feb 23', files: 5, lines: 465, status: '⚠️', issue: 'Structural issues' },
  { pass: 12, name: 'Spiking Neuron (LOSN)', date: 'Feb 24', files: 5, lines: 453, status: '⚠️', issue: 'Stubs' },
  { pass: 13, name: 'Dynamic Depth Transformer', date: 'Feb 24', files: 12, lines: 818, status: '⚠️', issue: 'Import bugs' },
  { pass: 14, name: 'Surprise-Driven Layers', date: 'Feb 25', files: 5, lines: 1471, status: '✅', issue: '1000+ lines!' },
  { pass: 15, name: 'Uncertainty-Aware Prediction', date: 'Feb 25', files: 8, lines: 3644, status: '✅', issue: 'Biggest!' },
  { pass: 16, name: 'Surprise-Driven Growth', date: 'Feb 25', files: 5, lines: 1873, status: '✅', issue: 'OK' },
  { pass: 17, name: 'Adaptive Layer Expansion', date: 'Feb 25', files: 4, lines: 1918, status: '✅', issue: '8.0/10' },
  { pass: 18, name: 'Sentiment LSTM-Transformer', date: 'Feb 25', files: 5, lines: 1005, status: '✅', issue: 'OK' },
  { pass: 19, name: 'Palette Selector', date: 'Feb 25', files: 5, lines: 1991, status: '✅', issue: 'OK' },
  { pass: 20, name: 'CLI Todo App', date: 'Feb 25', files: 5, lines: 1966, status: '⚠️', issue: 'API_MISMATCH' },
  { pass: 21, name: 'PBKDF2 Key Rotation', date: 'Feb 25', files: 4, lines: 1717, status: '✅', issue: 'OK' },
  { pass: 22, name: 'Password Manager', date: 'Feb 25', files: 11, lines: 3325, status: '✅', issue: 'ZERO FIXES!' },
  { pass: 23, name: 'AEAD Vault', date: 'Feb 26', files: 9, lines: 2659, status: '✅', issue: 'OK' },
  { pass: 24, name: 'Terminal Abstraction', date: 'Feb 26', files: 8, lines: 638, status: '❌', issue: 'Bad models' },
  { pass: 25, name: 'Chat App (attempt 2)', date: 'Feb 26', files: 9, lines: 694, status: '❌', issue: 'Prose' },
  { pass: 26, name: 'JWT-E2EE Framework', date: 'Feb 26', files: 9, lines: 1429, status: '❌', issue: 'Shadow' },
  { pass: 27, name: 'WebSocket Chat', date: 'Feb 26', files: 8, lines: 2018, status: '⚠️', issue: 'SQL mismatch' },
];

const bugTimeline = [
  { bug: 'NO_ENTRY_POINT', fixed: 'Pass 8', color: '#10B981' },
  { bug: 'TRUNCATED', fixed: 'Pass 9', color: '#10B981' },
  { bug: 'DEAD_LOGIC', fixed: 'Pass 10', color: '#10B981' },
  { bug: 'STUB_BODY', fixed: 'Pass 12', color: '#10B981' },
  { bug: 'MISSING_EXPORT', fixed: 'Pass 13', color: '#10B981' },
  { bug: 'PLACEHOLDER_INIT', fixed: 'Pass 14', color: '#10B981' },
  { bug: 'API_MISMATCH', fixed: 'Pass 20', color: '#10B981' },
  { bug: 'SELF_METHOD_MISSING', fixed: 'Pass 20', color: '#10B981' },
  { bug: 'UNINITIALIZED_ATTR', fixed: 'Pass 21', color: '#10B981' },
  { bug: 'PROSE_AS_CODE', fixed: 'Pass 25', color: '#10B981' },
  { bug: 'SHADOW_FILE', fixed: 'Pass 26', color: '#10B981' },
  { bug: 'SQL_SCHEMA_MISMATCH', fixed: 'Open', color: '#F59E0B' },
];

const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: Array<{ payload: typeof locData[0] }> }) => {
  if (active && payload && payload.length) {
    const d = payload[0].payload;
    return (
      <div className="bg-[rgba(3,7,18,0.95)] border border-[rgba(0,212,255,0.3)] rounded-lg p-3 font-mono text-xs">
        <div className="text-[#00D4FF] font-bold">Pass {d.pass}</div>
        <div className="text-[rgba(248,250,252,0.7)]">{d.lines.toLocaleString()} lines</div>
        <div className="text-[rgba(248,250,252,0.5)]">{d.date}</div>
        {d.label && <div className="text-[#F59E0B] mt-1">{d.label}</div>}
      </div>
    );
  }
  return null;
};

export default function EvolutionSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });
  const [showTable, setShowTable] = useState(false);

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
            27 Runs. 5 Days. From Broken to Production.
          </h2>
          <p className="text-lg text-[rgba(248,250,252,0.7)] max-w-3xl mx-auto">
            Real data from 27 pipeline iterations showing measurable improvement over time.
          </p>
        </motion.div>

        {/* LOC Bar Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="bg-[rgba(3,7,18,0.8)] border border-[rgba(0,212,255,0.15)] rounded-xl p-6 mb-12"
        >
          <h3 className="font-orbitron font-semibold text-[#00D4FF] text-lg mb-6 text-center">
            Lines of Code Generated Per Run
          </h3>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={locData} margin={{ top: 20, right: 20, bottom: 30, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,212,255,0.08)" />
                <XAxis
                  dataKey="pass"
                  stroke="rgba(248,250,252,0.4)"
                  tick={{ fill: 'rgba(248,250,252,0.5)', fontSize: 11 }}
                  label={{ value: 'Pass Number', position: 'bottom', fill: 'rgba(248,250,252,0.4)', fontSize: 12, offset: 15 }}
                />
                <YAxis
                  stroke="rgba(248,250,252,0.4)"
                  tick={{ fill: 'rgba(248,250,252,0.5)', fontSize: 11 }}
                  label={{ value: 'Lines of Code', angle: -90, position: 'insideLeft', fill: 'rgba(248,250,252,0.4)', fontSize: 12 }}
                />
                <Tooltip content={<CustomTooltip />} />
                <ReferenceLine y={1000} stroke="rgba(245,158,11,0.3)" strokeDasharray="5 5" label={{ value: '1000 LOC', fill: '#F59E0B', fontSize: 10 }} />
                <Bar dataKey="lines" radius={[4, 4, 0, 0]}>
                  {locData.map((entry) => (
                    <Cell key={`cell-${entry.pass}`} fill={getBarColor(entry.pass)} fillOpacity={0.85} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-wrap gap-4 justify-center mt-4 text-xs">
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-[#7C3AED]" /> Early runs</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-[#10B981]" /> Mature runs</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-[#00D4FF]" /> Milestones</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-[#EF4444]" /> Regressions</span>
          </div>
        </motion.div>

        {/* Bug Types Timeline */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="bg-[rgba(3,7,18,0.8)] border border-[rgba(0,212,255,0.15)] rounded-xl p-6 mb-12"
        >
          <h3 className="font-orbitron font-semibold text-[#00D4FF] text-lg mb-6 text-center">
            Bug Types Discovered &amp; Fixed
          </h3>
          <div className="space-y-2">
            {bugTimeline.map((b, i) => (
              <motion.div
                key={b.bug}
                initial={{ opacity: 0, x: -20 }}
                animate={isInView ? { opacity: 1, x: 0 } : {}}
                transition={{ duration: 0.3, delay: 0.5 + i * 0.06 }}
                className="flex items-center gap-3"
              >
                <span className="font-mono text-xs w-44 shrink-0 text-[rgba(248,250,252,0.6)]">
                  {b.bug}
                </span>
                <div className="flex-1 h-1.5 bg-[rgba(0,212,255,0.08)] rounded-full relative">
                  <motion.div
                    className="h-full rounded-full"
                    style={{ backgroundColor: b.color }}
                    initial={{ width: '0%' }}
                    animate={isInView ? { width: b.fixed === 'Open' ? '95%' : `${(parseInt(b.fixed.replace('Pass ', '')) / 27) * 100}%` } : {}}
                    transition={{ duration: 0.8, delay: 0.6 + i * 0.06 }}
                  />
                </div>
                <span
                  className="text-xs font-mono shrink-0 w-16 text-right"
                  style={{ color: b.color }}
                >
                  {b.fixed === 'Open' ? '⚠️ Open' : `✓ ${b.fixed}`}
                </span>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* Milestones Timeline */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, delay: 0.6 }}
          className="grid grid-cols-5 gap-2 mb-12"
        >
          {[
            { date: 'Feb 22', items: ['First run', '7 runs in 1 night', 'No main.py'] },
            { date: 'Feb 23', items: ['Truncation detection', 'SNN projects'] },
            { date: 'Feb 24', items: ['Code Review Agent added'] },
            { date: 'Feb 25', items: ['ZERO fixes!', 'Error memory', '3,644 lines'] },
            { date: 'Feb 26', items: ['30 min runs', 'Shadow file fix', 'Speed optim.'] },
          ].map((m, i) => (
            <div key={m.date} className="text-center">
              <div className="font-orbitron text-xs font-bold text-[#00D4FF] mb-2">{m.date}</div>
              <div className="h-1 bg-gradient-to-r from-[#00D4FF] to-[#7C3AED] rounded mb-3" />
              <div className="space-y-1">
                {m.items.map((item) => (
                  <motion.div
                    key={item}
                    initial={{ opacity: 0 }}
                    animate={isInView ? { opacity: 1 } : {}}
                    transition={{ delay: 0.8 + i * 0.1 }}
                    className="text-xs text-[rgba(248,250,252,0.5)]"
                  >
                    {item}
                  </motion.div>
                ))}
              </div>
            </div>
          ))}
        </motion.div>

        {/* Toggle Run History Table */}
        <div className="text-center mb-6">
          <button
            onClick={() => setShowTable(!showTable)}
            className="font-orbitron text-sm font-semibold px-6 py-3 rounded-lg bg-[rgba(0,212,255,0.1)] border border-[rgba(0,212,255,0.3)] text-[#00D4FF] hover:bg-[rgba(0,212,255,0.2)] transition-colors"
          >
            {showTable ? 'Hide' : 'Show'} Complete Run History
          </button>
        </div>

        {/* Run History Table */}
        {showTable && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="overflow-x-auto bg-[rgba(3,7,18,0.8)] border border-[rgba(0,212,255,0.15)] rounded-xl"
          >
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[rgba(0,212,255,0.2)]">
                  <th className="p-3 text-left text-[#00D4FF] font-orbitron text-xs">Pass</th>
                  <th className="p-3 text-left text-[#00D4FF] font-orbitron text-xs">Project</th>
                  <th className="p-3 text-center text-[#00D4FF] font-orbitron text-xs">Date</th>
                  <th className="p-3 text-center text-[#00D4FF] font-orbitron text-xs">Files</th>
                  <th className="p-3 text-center text-[#00D4FF] font-orbitron text-xs">Lines</th>
                  <th className="p-3 text-center text-[#00D4FF] font-orbitron text-xs">Status</th>
                  <th className="p-3 text-left text-[#00D4FF] font-orbitron text-xs">Key Issue</th>
                </tr>
              </thead>
              <tbody>
                {runHistory.map((r) => {
                  const isMilestone = [8, 14, 15, 22].includes(r.pass);
                  return (
                    <tr
                      key={r.pass}
                      className={`border-b border-[rgba(0,212,255,0.05)] ${isMilestone ? 'bg-[rgba(0,212,255,0.05)]' : ''}`}
                    >
                      <td className={`p-3 font-mono ${isMilestone ? 'text-[#00D4FF] font-bold' : 'text-[rgba(248,250,252,0.6)]'}`}>
                        {r.pass}
                      </td>
                      <td className={`p-3 ${isMilestone ? 'text-white font-semibold' : 'text-[rgba(248,250,252,0.6)]'}`}>
                        {r.name}
                      </td>
                      <td className="p-3 text-center text-[rgba(248,250,252,0.4)] text-xs">{r.date}</td>
                      <td className="p-3 text-center text-[rgba(248,250,252,0.5)]">{r.files}</td>
                      <td className="p-3 text-center text-[rgba(248,250,252,0.5)]">{r.lines.toLocaleString()}</td>
                      <td className="p-3 text-center text-lg">{r.status}</td>
                      <td className={`p-3 text-xs ${isMilestone ? 'text-[#F59E0B] font-semibold' : 'text-[rgba(248,250,252,0.4)]'}`}>
                        {r.issue}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </motion.div>
        )}
      </div>
    </section>
  );
}
