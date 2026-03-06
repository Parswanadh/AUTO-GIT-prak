'use client';

import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';

const errorEntries = [
  {
    run_id: 'cli_todo_app_001',
    bug_type: 'API_MISMATCH',
    file: 'main.py',
    description: 'main.py called cli_app.add_task() but CliApp only has run()',
  },
  {
    run_id: 'snn_accelerator_001',
    bug_type: 'TRUNCATED',
    file: 'main.py',
    description: 'main.py was 97 lines ending mid-function with no __main__ guard',
  },
  {
    run_id: 'run_16',
    bug_type: 'SHADOW_FILE',
    file: 'jwt.py',
    description: 'jwt.py shadows PyJWT package causing circular import crash',
  },
  {
    run_id: 'run_14',
    bug_type: 'PLACEHOLDER_INIT',
    file: 'model.py',
    description: 'model = nn.Module() used as placeholder instead of real class',
  },
  {
    run_id: 'run_12',
    bug_type: 'STUB_BODY',
    file: 'auth.py',
    description: 'def encrypt(self): pass — function body never implemented',
  },
];

const lessons = [
  { type: 'API_MISMATCH', count: 4, lesson: 'Never call methods that don\'t exist on the target class. Cross-check every method call against the interface contract.' },
  { type: 'TRUNCATED', count: 3, lesson: 'Always complete every function body. Never end mid-statement.' },
  { type: 'SHADOW_FILE', count: 1, lesson: 'Never name a file after a pip package (jwt.py, numpy.py, etc.)' },
];

export default function ErrorMemorySection() {
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
            The System Learns From Its Own Mistakes
          </h2>
          <p className="text-lg text-[rgba(248,250,252,0.7)] max-w-3xl mx-auto">
            Every bug the pipeline encounters is recorded in a persistent JSONL file.
            Before generating code in future runs, the system reads its past mistakes
            and injects them as warnings. Like a bug database that trains the next run.
          </p>
        </motion.div>

        {/* Learning Loop Visual */}
        <div className="grid md:grid-cols-2 gap-6 mb-16">
          {/* Before */}
          <motion.div
            initial={{ opacity: 0, x: -30 }}
            animate={isInView ? { opacity: 1, x: 0 } : {}}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="bg-[rgba(3,7,18,0.8)] border border-[rgba(239,68,68,0.3)] rounded-xl p-6"
          >
            <div className="flex items-center gap-2 mb-4">
              <span className="text-[#EF4444] font-orbitron font-bold text-sm">Run #10</span>
              <span className="text-xs text-[rgba(248,250,252,0.4)]">CLI Todo App</span>
            </div>
            <div className="font-mono text-sm space-y-2">
              <div className="text-[#EF4444]">✗ Bug: main.py called cli_app.add_task()</div>
              <div className="text-[rgba(248,250,252,0.5)]">  but class only has run()</div>
              <div className="mt-3 text-[#F59E0B]">→ Recorded as API_MISMATCH in error memory</div>
              <div className="mt-4 px-3 py-2 bg-[rgba(239,68,68,0.1)] rounded text-[#EF4444] text-xs">
                Result: 2 manual fixes needed
              </div>
            </div>
          </motion.div>

          {/* After */}
          <motion.div
            initial={{ opacity: 0, x: 30 }}
            animate={isInView ? { opacity: 1, x: 0 } : {}}
            transition={{ duration: 0.5, delay: 0.4 }}
            className="bg-[rgba(3,7,18,0.8)] border border-[rgba(16,185,129,0.3)] rounded-xl p-6"
          >
            <div className="flex items-center gap-2 mb-4">
              <span className="text-[#10B981] font-orbitron font-bold text-sm">Run #13</span>
              <span className="text-xs text-[rgba(248,250,252,0.4)]">Password Manager</span>
            </div>
            <div className="font-mono text-sm space-y-2">
              <div className="text-[#10B981]">✓ Prompt includes:</div>
              <div className="text-[rgba(248,250,252,0.6)]">  &ldquo;LESSON: Never call methods that aren&apos;t defined on the class&rdquo;</div>
              <div className="mt-3 text-[#10B981]">✓ Cross-checked all method calls</div>
              <div className="mt-4 px-3 py-2 bg-[rgba(16,185,129,0.1)] rounded text-[#10B981] text-xs">
                Result: ZERO manual fixes needed!
              </div>
            </div>
          </motion.div>
        </div>

        {/* Real Error Memory Entries */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5, delay: 0.5 }}
          className="mb-16"
        >
          <h3 className="font-orbitron font-semibold text-[#00D4FF] text-lg mb-4 text-center">
            Real Error Memory Entries
          </h3>
          <div className="bg-[rgba(0,0,0,0.6)] border border-[rgba(0,212,255,0.15)] rounded-xl p-4 font-mono text-xs space-y-2 max-h-64 overflow-y-auto">
            {errorEntries.map((e, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -20 }}
                animate={isInView ? { opacity: 1, x: 0 } : {}}
                transition={{ duration: 0.3, delay: 0.6 + i * 0.1 }}
                className="p-3 rounded-lg bg-[rgba(0,212,255,0.03)] border border-[rgba(0,212,255,0.08)]"
              >
                <span className="text-[rgba(248,250,252,0.3)]">{'{'}</span>
                <span className="text-[#F59E0B]">&quot;run_id&quot;</span>
                <span className="text-[rgba(248,250,252,0.3)]">: </span>
                <span className="text-[#10B981]">&quot;{e.run_id}&quot;</span>
                <span className="text-[rgba(248,250,252,0.3)]">, </span>
                <span className="text-[#F59E0B]">&quot;bug_type&quot;</span>
                <span className="text-[rgba(248,250,252,0.3)]">: </span>
                <span className="text-[#EF4444]">&quot;{e.bug_type}&quot;</span>
                <span className="text-[rgba(248,250,252,0.3)]">, </span>
                <span className="text-[#F59E0B]">&quot;file&quot;</span>
                <span className="text-[rgba(248,250,252,0.3)]">: </span>
                <span className="text-[#00D4FF]">&quot;{e.file}&quot;</span>
                <span className="text-[rgba(248,250,252,0.3)]">, </span>
                <br />
                <span className="text-[#F59E0B]"> &quot;description&quot;</span>
                <span className="text-[rgba(248,250,252,0.3)]">: </span>
                <span className="text-[rgba(248,250,252,0.6)]">&quot;{e.description}&quot;</span>
                <span className="text-[rgba(248,250,252,0.3)]">{'}'}</span>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* How Lessons Are Injected */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5, delay: 0.8 }}
          className="mb-12"
        >
          <h3 className="font-orbitron font-semibold text-[#00D4FF] text-lg mb-4 text-center">
            How Lessons Are Injected Into Prompts
          </h3>
          <div className="bg-[rgba(0,0,0,0.6)] border border-[rgba(0,212,255,0.15)] rounded-xl p-6 font-mono text-sm">
            <div className="text-[#7C3AED]"># Before generating code, the system reads its past mistakes</div>
            <div className="text-[rgba(248,250,252,0.7)]">lessons = error_memory.<span className="text-[#F59E0B]">get_top_lessons</span>(n=<span className="text-[#00D4FF]">15</span>)</div>
            <div className="mt-3 text-[rgba(248,250,252,0.7)]">prompt = <span className="text-[#10B981]">f&quot;&quot;&quot;</span></div>
            <div className="text-[#10B981] pl-4">LESSONS FROM PAST RUNS (avoid these mistakes):</div>
            {lessons.map((l, i) => (
              <div key={i} className="text-[#10B981] pl-4">
                {i + 1}. [<span className="text-[#EF4444]">{l.type}</span> × {l.count}] {l.lesson}
              </div>
            ))}
            <div className="text-[#10B981]">&quot;&quot;&quot;</div>
          </div>
        </motion.div>

        {/* Impact Stats */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.5, delay: 1 }}
          className="grid grid-cols-3 gap-4"
        >
          {[
            { value: '233', label: 'Error entries recorded', color: '#EF4444' },
            { value: '27', label: 'Pipeline runs learned from', color: '#00D4FF' },
            { value: '0', label: 'Manual fixes (best run)', color: '#10B981' },
          ].map((stat) => (
            <div
              key={stat.label}
              className="bg-[rgba(3,7,18,0.8)] border border-[rgba(0,212,255,0.12)] rounded-xl p-6 text-center"
            >
              <div
                className="text-4xl md:text-5xl font-bold font-orbitron mb-2"
                style={{ color: stat.color }}
              >
                {stat.value}
              </div>
              <div className="text-xs text-[rgba(248,250,252,0.5)]">{stat.label}</div>
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
