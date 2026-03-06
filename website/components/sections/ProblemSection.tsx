'use client';

import { motion } from 'framer-motion';

const problems = [
  { title: 'Weeks of Development', desc: 'Traditional software takes weeks', icon: '⏱️' },
  { title: 'High Costs', desc: 'Developer time is expensive', icon: '💰' },
  { title: 'Quality Issues', desc: 'Bugs accumulate over time', icon: '🐛' },
];

export default function ProblemSection() {
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
          The Problem
        </motion.h2>

        {/* Subtitle */}
        <motion.p
          className="text-lg text-[rgba(248,250,252,0.7)] max-w-3xl mx-auto text-center mb-16"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.2 }}
        >
          Modern software development is slow, expensive, and error-prone.
        </motion.p>

        {/* Cards with enhanced hover effects */}
        <div className="grid md:grid-cols-3 gap-8 justify-center">
          {problems.map((item, i) => (
            <motion.div
              key={i}
              className="bg-[rgba(3,7,18,0.8)] border border-[rgba(0,212,255,0.2)] backdrop-blur-md rounded-xl p-6 relative overflow-hidden group"
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
              whileHover={{
                y: -8,
                scale: 1.02,
                borderColor: 'rgba(0, 212, 255, 0.5)',
                boxShadow: '0 20px 40px rgba(0, 212, 255, 0.2)',
                transition: { duration: 0.3 }
              }}
            >
              {/* Hover glow effect */}
              <div className="absolute inset-0 bg-gradient-to-br from-[rgba(0,212,255,0.1)] to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />

              {/* Icon with animation */}
              <motion.div
                className="text-4xl mb-4"
                whileHover={{ rotate: [0, -10, 10, -10, 0], scale: 1.2 }}
                transition={{ duration: 0.5 }}
              >
                {item.icon}
              </motion.div>

              {/* Content */}
              <h3 className="font-orbitron font-semibold text-xl mb-2 text-[#00D4FF] relative z-10">
                {item.title}
              </h3>
              <p className="text-[rgba(248,250,252,0.7)] relative z-10">{item.desc}</p>

              {/* Shine effect on hover */}
              <motion.div
                className="absolute inset-0 bg-gradient-to-r from-transparent via-white to-transparent opacity-0 group-hover:opacity-10"
                initial={{ x: '-100%' }}
                whileHover={{ x: '100%' }}
                transition={{ duration: 0.6 }}
              />
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
