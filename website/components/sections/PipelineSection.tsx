'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';

const pipelineNodes = [
  { id: 'research', name: 'Research' },
  { id: 'problem', name: 'Problem' },
  { id: 'solution', name: 'Solution' },
  { id: 'critique', name: 'Critique' },
  { id: 'codegen', name: 'Code Gen' },
  { id: 'review', name: 'Review' },
  { id: 'test', name: 'Test' },
  { id: 'publish', name: 'Publish' },
];

export default function PipelineSection() {
  const [activeNode, setActiveNode] = useState(-1);

  const play = () => {
    setActiveNode(0);
    setTimeout(() => setActiveNode(1), 500);
    setTimeout(() => setActiveNode(2), 1000);
    setTimeout(() => setActiveNode(3), 1500);
    setTimeout(() => setActiveNode(4), 2000);
    setTimeout(() => setActiveNode(5), 2500);
    setTimeout(() => setActiveNode(6), 3000);
    setTimeout(() => setActiveNode(7), 3500);
  };

  return (
    <section className="relative py-32">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Title with fade-in */}
        <motion.h2
          className="font-orbitron font-bold text-4xl md:text-5xl mb-4 bg-gradient-to-r from-[#00D4FF] to-[#7C3AED] bg-clip-text text-transparent text-center"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.6 }}
        >
          Pipeline Architecture
        </motion.h2>

        {/* Enhanced play button with hover effects */}
        <motion.button
          onClick={play}
          className="mx-auto block px-8 py-4 rounded-xl bg-gradient-to-r from-[#00D4FF] to-[#7C3AED] text-white font-semibold mb-8 relative overflow-hidden group"
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.4, delay: 0.2 }}
          style={{
            boxShadow: '0 4px 20px rgba(0, 212, 255, 0.3)'
          }}
        >
          <span className="relative z-10">Play Pipeline</span>
          {/* Shine effect on hover */}
          <motion.div
            className="absolute inset-0 bg-gradient-to-r from-transparent via-white to-transparent opacity-0 group-hover:opacity-20"
            initial={{ x: '-100%' }}
            whileHover={{ x: '100%' }}
            transition={{ duration: 0.6 }}
          />
        </motion.button>

        {/* Pipeline nodes with staggered animations */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 justify-center">
          {pipelineNodes.map((node, i) => (
            <motion.div
              key={node.id}
              className={`p-4 rounded-xl border-2 text-center relative overflow-hidden ${activeNode >= i
                  ? 'border-[#00D4FF] bg-[rgba(0,212,255,0.1)]'
                  : 'border-[rgba(0,212,255,0.2)] bg-[rgba(3,7,18,0.8)]'
                }`}
              initial={{ opacity: 0, scale: 0.8 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.05 }}
              whileHover={{ scale: 1.05, y: -5 }}
              animate={activeNode === i ? {
                boxShadow: ['0 0 0px rgba(0, 212, 255, 0)', '0 0 30px rgba(0, 212, 255, 0.6)'],
                borderColor: ['#00D4FF', '#7C3AED', '#00D4FF']
              } : {}}
            >
              <motion.div
                className="font-orbitron font-semibold text-lg text-[#00D4FF] relative z-10"
                animate={activeNode === i ? { scale: [1, 1.1, 1] } : {}}
                transition={{ duration: 0.3 }}
              >
                {node.name}
              </motion.div>
              {/* Pulse effect when active */}
              {activeNode === i && (
                <motion.div
                  className="absolute inset-0 bg-[#00D4FF] opacity-20"
                  initial={{ scale: 0, opacity: 0.5 }}
                  animate={{ scale: 2, opacity: 0 }}
                  transition={{ duration: 1, ease: 'easeOut' }}
                />
              )}
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
