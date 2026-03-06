'use client';

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Terminal, Play, RotateCcw, Copy, Check, Sparkles } from 'lucide-react';

interface DemoStep {
  id: string;
  command?: string;
  output?: string;
  status: 'pending' | 'running' | 'complete' | 'error';
  duration?: number;
}

const demoScenarios = [
  {
    name: 'URL Shortener API',
    commands: [
      '> auto-git generate "Create a URL shortener API"',
      '▸ Researching arXiv papers...',
      '  ✓ Found 12 relevant papers',
      '  ✓ Analyzed 3 GitHub repositories',
      '▸ Multi-agent debate initiated...',
      '  • ML Researcher: "Use hash-based encoding for"',
      '  • Systems Engineer: "Implement rate limiting"',
      '  • Applied Scientist: "Add analytics tracking"',
      '  ✓ Consensus reached (3 rounds)',
      '▸ Generating code...',
      '  ✓ main.py (127 lines)',
      '  ✓ api.py (89 lines)',
      '  ✓ models.py (45 lines)',
      '▸ Running validation...',
      '  ✓ Syntax check passed',
      '  ✓ Type check passed',
      '  ✓ Security scan: 0 vulnerabilities',
      '▸ Publishing to GitHub...',
      '  ✓ Repository created: auto-git-url-shortener',
      '▸ Pipeline complete! (3m 47s)',
    ],
  },
  {
    name: 'Sentiment Analyzer',
    commands: [
      '> auto-git generate "Build a sentiment analysis tool"',
      '▸ Researching...',
      '  ✓ Found 8 papers on NLP & transformers',
      '▸ Multi-agent debate...',
      '  • ML Researcher: "Use transformer model"',
      '  • Systems Engineer: "Add caching layer"',
      '  • Applied Scientist: "Include confidence scores"',
      '  ✓ Solution selected',
      '▸ Generating code...',
      '  ✓ model.py (156 lines)',
      '  ✓ train.py (98 lines)',
      '  ✓ main.py (67 lines)',
      '▸ Running tests...',
      '  ✓ 12/12 tests passed',
      '▸ Published to GitHub!',
      '▸ Complete! (2m 31s)',
    ],
  },
];

export default function LiveDemoSection() {
  const [currentScenario, setCurrentScenario] = useState(0);
  const [currentLine, setCurrentLine] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [copiedCommand, setCopiedCommand] = useState<string | null>(null);
  const terminalRef = useRef<HTMLDivElement>(null);

  const commands = demoScenarios[currentScenario].commands;

  // Auto-play effect
  useEffect(() => {
    if (!isPlaying) return;

    const interval = setInterval(() => {
      setCurrentLine((prev) => {
        if (prev < commands.length - 1) {
          return prev + 1;
        } else {
          setIsPlaying(false);
          return prev;
        }
      });
    }, 800);

    return () => clearInterval(interval);
  }, [isPlaying, commands.length]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [currentLine]);

  const handlePlay = () => {
    if (currentLine >= commands.length - 1) {
      setCurrentLine(0);
    }
    setIsPlaying(true);
  };

  const handleReset = () => {
    setCurrentLine(0);
    setIsPlaying(false);
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCommand(text);
    setTimeout(() => setCopiedCommand(null), 2000);
  };

  const switchScenario = (index: number) => {
    setCurrentScenario(index);
    setCurrentLine(0);
    setIsPlaying(false);
  };

  return (
    <section className="relative py-32 overflow-hidden">
      {/* Background decoration */}
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-cyan-500/5 to-transparent pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
        {/* Section header */}
        <motion.div
          className="text-center mb-16"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
        >
          <motion.div
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 text-sm mb-6"
            whileHover={{ scale: 1.05 }}
          >
            <Sparkles className="w-4 h-4" />
            <span>Interactive Demo</span>
          </motion.div>

          <h2 className="font-orbitron font-bold text-4xl md:text-5xl mb-4 bg-gradient-to-r from-[#00D4FF] to-[#7C3AED] bg-clip-text text-transparent">
            Watch Auto-GIT in Action
          </h2>

          <p className="text-xl text-[rgba(248,250,252,0.7)] max-w-3xl mx-auto">
            See how the pipeline transforms ideas into production-ready code in minutes
          </p>
        </motion.div>

        {/* Scenario selector */}
        <div className="flex justify-center gap-4 mb-8">
          {demoScenarios.map((scenario, index) => (
            <motion.button
              key={scenario.name}
              onClick={() => switchScenario(index)}
              className={`px-6 py-3 rounded-lg font-medium transition-all ${
                currentScenario === index
                  ? 'bg-gradient-to-r from-cyan-500 to-purple-600 text-white shadow-lg shadow-cyan-500/25'
                  : 'bg-slate-800/50 text-slate-400 hover:bg-slate-700/50 hover:text-slate-300'
              }`}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              {scenario.name}
            </motion.button>
          ))}
        </div>

        {/* Terminal */}
        <motion.div
          className="max-w-4xl mx-auto"
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.2 }}
        >
          {/* Terminal header */}
          <div className="bg-gradient-to-r from-slate-800 to-slate-900 rounded-t-xl px-4 py-3 flex items-center justify-between border border-slate-700">
            <div className="flex items-center gap-2">
              <div className="flex gap-2">
                <div className="w-3 h-3 rounded-full bg-red-500" />
                <div className="w-3 h-3 rounded-full bg-yellow-500" />
                <div className="w-3 h-3 rounded-full bg-green-500" />
              </div>
              <span className="ml-4 text-slate-400 text-sm font-mono">
                auto-git-terminal
              </span>
            </div>

            {/* Control buttons */}
            <div className="flex items-center gap-2">
              <motion.button
                onClick={handlePlay}
                disabled={isPlaying}
                className={`p-2 rounded-lg transition-all ${
                  isPlaying
                    ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
                    : 'bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30'
                }`}
                whileHover={!isPlaying ? { scale: 1.1 } : {}}
                whileTap={!isPlaying ? { scale: 0.9 } : {}}
              >
                <Play className="w-4 h-4" fill={isPlaying ? 'currentColor' : 'none'} />
              </motion.button>

              <motion.button
                onClick={handleReset}
                className="p-2 rounded-lg bg-purple-500/20 text-purple-400 hover:bg-purple-500/30 transition-all"
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
              >
                <RotateCcw className="w-4 h-4" />
              </motion.button>
            </div>
          </div>

          {/* Terminal body */}
          <div
            ref={terminalRef}
            className="bg-[rgba(0,0,0,0.95)] border border-t-0 border-slate-700 rounded-b-xl p-6 font-mono text-sm min-h-[400px] max-h-[500px] overflow-y-auto custom-scrollbar"
          >
            <AnimatePresence mode="popLayout">
              {commands.slice(0, currentLine + 1).map((line, index) => {
                const isCommand = line.startsWith('>');
                const isRunning = index === currentLine && isPlaying;
                const isComplete = index < currentLine || (!isPlaying && index === currentLine);

                return (
                  <motion.div
                    key={`${currentScenario}-${index}`}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 20 }}
                    transition={{ duration: 0.3 }}
                    className="mb-1"
                  >
                    <div
                      className={`flex items-start gap-2 ${
                        isCommand ? 'text-cyan-400 font-semibold' : 'text-slate-300'
                      }`}
                    >
                      {isCommand && (
                        <span className="text-purple-400">$</span>
                      )}
                      <span className={isRunning ? 'animate-pulse' : ''}>{line}</span>

                      {/* Copy button for commands */}
                      {isCommand && (
                        <motion.button
                          onClick={() => handleCopy(line.slice(2))}
                          className="ml-auto opacity-0 group-hover:opacity-100 hover:opacity-100 transition-opacity"
                          whileHover={{ scale: 1.1 }}
                          whileTap={{ scale: 0.9 }}
                        >
                          {copiedCommand === line.slice(2) ? (
                            <Check className="w-4 h-4 text-green-400" />
                          ) : (
                            <Copy className="w-4 h-4 text-slate-500 hover:text-slate-400" />
                          )}
                        </motion.button>
                      )}
                    </div>

                    {/* Progress indicator for running operations */}
                    {isRunning && !isCommand && (
                      <motion.div
                        className="ml-4 flex gap-1 mt-1"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                      >
                        {[0, 1, 2].map((i) => (
                          <motion.div
                            key={i}
                            className="w-1.5 h-1.5 rounded-full bg-cyan-400"
                            animate={{ scale: [1, 1.5, 1] }}
                            transition={{
                              duration: 0.8,
                              repeat: Infinity,
                              delay: i * 0.15,
                            }}
                          />
                        ))}
                      </motion.div>
                    )}
                  </motion.div>
                );
              })}
            </AnimatePresence>

            {/* Cursor */}
            <motion.span
              className="inline-block w-2 h-4 bg-cyan-400 ml-1 align-middle"
              animate={{ opacity: [1, 0, 1] }}
              transition={{ duration: 1, repeat: Infinity }}
            />
          </div>

          {/* Stats bar */}
          <div className="mt-4 flex items-center justify-between text-sm text-slate-400">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-cyan-400" />
                <span>
                  {commands.filter((c) => c.startsWith('▸')).length} pipeline stages
                </span>
              </div>
              <div>
                Files generated: <span className="text-cyan-400 font-semibold">
                  {commands.filter((c) => c.includes('.py')).length}
                </span>
              </div>
            </div>

            <div className="text-slate-500">
              {commands.filter((c) => c.includes('✓')).length} / {commands.length} steps
            </div>
          </div>
        </motion.div>

        {/* CTA */}
        <motion.div
          className="text-center mt-16"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.4 }}
        >
          <motion.a
            href="https://github.com/Parswanadh/auto-git"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-3 px-8 py-4 bg-gradient-to-r from-cyan-500 to-purple-600 rounded-xl text-white font-semibold text-lg shadow-lg shadow-cyan-500/25 hover:shadow-cyan-500/40 transition-all"
            whileHover={{ scale: 1.05, y: -2 }}
            whileTap={{ scale: 0.98 }}
          >
            <Play className="w-5 h-5" fill="currentColor" />
            Try Auto-GIT Yourself
          </motion.a>

          <p className="mt-4 text-slate-400 text-sm">
            Open source • Free to use • No API keys required
          </p>
        </motion.div>
      </div>
    </section>
  );
}
