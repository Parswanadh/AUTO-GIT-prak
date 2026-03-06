'use client';

import { motion, useInView } from 'framer-motion';
import { useRef, useState } from 'react';

const tabs = [
  {
    title: 'Strategy Reasoner',
    desc: 'The most innovative part — root-cause analysis before fixing',
    code: `async def strategy_reasoner_node(state: AutoGITState) -> Dict[str, Any]:
    """
    Node 8.4: Strategic reasoning about WHY code failed.
    
    Instead of mechanically injecting errors and asking "fix this",
    this node DIAGNOSES root causes, CLASSIFIES failure types, and
    GENERATES strategic fix plans. Tracks previous failed strategies
    to avoid repeating mistakes.
    """
    # ... builds file overview, error text, previous strategy history
    
    reasoning_prompt = (
        "You are a senior software architect debugging a failed pipeline.\\n"
        "Your job is NOT to write code. Your job is to THINK STRATEGICALLY:\\n"
        "1. What is the ROOT CAUSE of each failure?\\n"
        "2. What CATEGORY of bug is this?\\n"
        "3. What is the BEST STRATEGY to fix it?\\n"
        "4. PREVIOUSLY TRIED STRATEGIES (DO NOT REPEAT): ..."
    )`,
  },
  {
    title: 'Error Memory Learning',
    desc: 'Persistent learning from code generation failures',
    code: `class CodegenErrorMemory:
    """Persistent learning from code generation failures.
    
    Append-only JSONL ledger. Before generating code, the system
    reads its past mistakes and injects them as warnings.
    
    233 errors recorded across 27 runs — the system genuinely
    improves over time.
    """
    
    def get_top_lessons(self, n: int = 15) -> str:
        """Returns top-N most common bug patterns as formatted lessons."""
        # Counts (bug_type, description) pairs
        # Returns: "LESSONS FROM PAST RUNS (avoid these mistakes):
        #   1. [API_MISMATCH × 4] Never call methods that don't exist..."
        counter = Counter(
            (e["bug_type"], e["description"]) for e in self.entries
        )
        return self._format_lessons(counter.most_common(n))`,
  },
  {
    title: 'Multi-Agent Debate',
    desc: '3 domain experts debate simultaneously with consensus scoring',
    code: `# 3 domain experts debate simultaneously
proposals = await asyncio.gather(
    generate_proposal(perspectives[0], research_context, llm),
    generate_proposal(perspectives[1], research_context, llm),
    generate_proposal(perspectives[2], research_context, llm),
)

# Each expert critiques ALL proposals (N² critique matrix)
for reviewer in perspectives:
    for proposal in proposals:
        critique = await generate_critique(reviewer, proposal, llm)
        critiques.append(critique)

# Weighted consensus scoring
consensus_score = sum(
    1.0 if c["recommendation"] == "accept"
    else 0.5 if c["recommendation"] == "revise" 
    else 0.0
    for c in critiques
) / len(critiques)

if consensus_score < 0.7 and round < max_rounds:
    # Re-debate with critique feedback
    return {"round": round + 1, "status": "re-debate"}`,
  },
];

export default function CodeShowcaseSection() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });
  const [activeTab, setActiveTab] = useState(0);

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
            Real Code. Real Output.
          </h2>
          <p className="text-lg text-[rgba(248,250,252,0.7)] max-w-3xl mx-auto">
            Key snippets from the pipeline&apos;s own source code — the most innovative parts.
          </p>
        </motion.div>

        {/* Tab Buttons */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={isInView ? { opacity: 1 } : {}}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="flex flex-wrap gap-2 mb-6 justify-center"
        >
          {tabs.map((tab, i) => (
            <button
              key={tab.title}
              onClick={() => setActiveTab(i)}
              className={`font-mono text-sm px-4 py-2 rounded-lg transition-all ${activeTab === i
                  ? 'bg-[rgba(0,212,255,0.15)] border border-[rgba(0,212,255,0.4)] text-[#00D4FF]'
                  : 'bg-[rgba(3,7,18,0.6)] border border-[rgba(0,212,255,0.1)] text-[rgba(248,250,252,0.5)] hover:text-[rgba(248,250,252,0.8)]'
                }`}
            >
              {tab.title}
            </button>
          ))}
        </motion.div>

        {/* Active Tab Content */}
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="bg-[rgba(0,0,0,0.7)] border border-[rgba(0,212,255,0.2)] rounded-xl overflow-hidden"
        >
          {/* Tab Header */}
          <div className="px-6 py-4 border-b border-[rgba(0,212,255,0.1)] flex items-center justify-between">
            <div>
              <h3 className="font-orbitron font-semibold text-[#00D4FF] text-sm">
                {tabs[activeTab].title}
              </h3>
              <p className="text-xs text-[rgba(248,250,252,0.4)] mt-1">
                {tabs[activeTab].desc}
              </p>
            </div>
            <span className="text-xs font-mono text-[rgba(248,250,252,0.3)] px-2 py-1 rounded bg-[rgba(0,212,255,0.05)]">
              Python
            </span>
          </div>
          {/* Code Block */}
          <div className="p-6 overflow-x-auto">
            <pre className="text-sm font-mono leading-relaxed">
              {tabs[activeTab].code.split('\n').map((line, i) => (
                <div key={i} className="flex">
                  <span className="text-[rgba(248,250,252,0.2)] w-8 text-right mr-4 select-none text-xs leading-relaxed">
                    {i + 1}
                  </span>
                  <span
                    className={
                      line.trim().startsWith('#')
                        ? 'text-[#7C3AED]'
                        : line.trim().startsWith('"""') || line.trim().startsWith("'")
                          ? 'text-[#10B981]'
                          : line.includes('def ') || line.includes('class ') || line.includes('async ')
                            ? 'text-[#00D4FF]'
                            : line.includes('await ') || line.includes('return ')
                              ? 'text-[#F59E0B]'
                              : 'text-[rgba(248,250,252,0.75)]'
                    }
                  >
                    {line || '\u00A0'}
                  </span>
                </div>
              ))}
            </pre>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
