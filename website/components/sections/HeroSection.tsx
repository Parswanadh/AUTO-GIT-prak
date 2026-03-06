'use client';

import { motion, useInView } from 'framer-motion';
import { useRef, useEffect, useState } from 'react';

// Animated counter component
function AnimatedCounter({ value, duration = 2 }: { value: string; duration?: number }) {
  const [count, setCount] = useState(0);
  const [isVisible, setIsVisible] = useState(false);
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: '-100px' });

  useEffect(() => {
    if (inView && !isVisible) {
      setIsVisible(true);
      const targetValue = parseInt(value.replace(/,/g, ''));
      const startTime = Date.now();

      const animate = () => {
        const elapsed = Date.now() - startTime;
        const progress = Math.min(elapsed / (duration * 1000), 1);

        // Easing function for smooth animation
        const easeOutQuart = 1 - Math.pow(1 - progress, 4);
        const currentCount = Math.floor(targetValue * easeOutQuart);

        setCount(currentCount);

        if (progress < 1) {
          requestAnimationFrame(animate);
        }
      };

      requestAnimationFrame(animate);
    }
  }, [inView, isVisible, value, duration]);

  return (
    <span ref={ref}>
      {count.toLocaleString()}
    </span>
  );
}

export default function HeroSection() {
  const stats = [
    { value: '47726', label: 'Lines of Code', icon: '💻' },
    { value: '27', label: 'Pipeline Runs', icon: '🔄' },
    { value: '15', label: 'Pipeline Nodes', icon: '⚙️' },
    { value: '233', label: 'Errors Learned', icon: '🧠' },
  ];

  return (
    <section className="relative min-h-screen flex items-center justify-center pt-16">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        {/* Title with enhanced animations */}
        <motion.h1
          className="font-orbitron font-bold text-5xl md:text-6xl lg:text-7xl mb-6 bg-gradient-to-r from-[#00D4FF] via-[#7C3AED] to-[#10B981] bg-clip-text text-transparent"
          initial={{ opacity: 0, y: 30, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          whileHover={{ scale: 1.02 }}
        >
          Transform Ideas Into Code
        </motion.h1>

        {/* Subtitle with gradient text animation */}
        <motion.p
          className="text-xl md:text-2xl text-[rgba(248,250,252,0.7)] max-w-3xl mx-auto mb-8 font-rajdhani"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.2, ease: 'easeOut' }}
        >
          Autonomous software development powered by{' '}
          <motion.span
            className="text-[#00D4FF] font-semibold"
            animate={{
              backgroundPosition: ['0%', '100%', '0%'],
            }}
            transition={{
              duration: 4,
              repeat: Infinity,
              ease: 'linear',
            }}
            style={{
              background: 'linear-gradient(90deg, #00D4FF, #7C3AED, #10B981, #00D4FF)',
              backgroundSize: '200% auto',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}
          >
            multi-agent AI debate
          </motion.span>
          , research synthesis, and automated publishing.
        </motion.p>

        {/* Stats with circular progress indicators and counting animation */}
        <div className="flex flex-wrap justify-center gap-8 mb-12">
          {stats.map((stat, index) => (
            <motion.div
              key={stat.label}
              className="relative group"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.4 + index * 0.1, ease: 'easeOut' }}
              whileHover={{
                y: -8,
                transition: { duration: 0.2 }
              }}
            >
              {/* Circular progress ring */}
              <svg className="absolute -top-2 -left-2 w-16 h-16 opacity-0 group-hover:opacity-100 transition-opacity duration-300" viewBox="0 0 64 64">
                <motion.circle
                  cx="32"
                  cy="32"
                  r="28"
                  fill="none"
                  stroke="url(#gradient)"
                  strokeWidth="3"
                  strokeLinecap="round"
                  initial={{ pathLength: 0 }}
                  whileHover={{ pathLength: 1 }}
                  transition={{ duration: 0.8, ease: 'easeInOut' }}
                  style={{ filter: 'drop-shadow(0 0 4px rgba(0, 212, 255, 0.5))' }}
                />
                <defs>
                  <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#00D4FF" />
                    <stop offset="100%" stopColor="#7C3AED" />
                  </linearGradient>
                </defs>
              </svg>

              {/* Icon badge */}
              <motion.div
                className="absolute -top-3 -right-3 w-8 h-8 bg-gradient-to-br from-[#00D4FF] to-[#7C3AED] rounded-full flex items-center justify-center text-sm shadow-lg"
                initial={{ scale: 0, rotate: -180 }}
                animate={{ scale: 1, rotate: 0 }}
                transition={{ duration: 0.5, delay: 0.6 + index * 0.1, type: 'spring' }}
                whileHover={{ rotate: 360, scale: 1.2 }}
              >
                {stat.icon}
              </motion.div>

              {/* Content */}
              <div className="bg-[rgba(3,7,18,0.8)] border-2 border-[rgba(0,212,255,0.2)] rounded-2xl px-6 py-4 relative overflow-hidden">
                {/* Glow effect on hover */}
                <motion.div
                  className="absolute inset-0 bg-gradient-to-br from-[rgba(0,212,255,0.1)] to-transparent"
                  initial={{ opacity: 0 }}
                  whileHover={{ opacity: 1 }}
                  transition={{ duration: 0.3 }}
                />

                {/* Animated number */}
                <motion.div
                  className="text-4xl md:text-5xl font-bold text-[#00D4FF] font-orbitron relative z-10"
                  whileHover={{
                    scale: 1.1,
                    textShadow: '0 0 20px rgba(0, 212, 255, 0.8), 0 0 40px rgba(124, 58, 237, 0.6)',
                  }}
                >
                  <AnimatedCounter value={stat.value} />
                </motion.div>

                {/* Label with gradient */}
                <div className="text-sm text-[rgba(248,250,252,0.5)] mt-1 relative z-10">{stat.label}</div>

                {/* Shine effect */}
                <motion.div
                  className="absolute inset-0 bg-gradient-to-r from-transparent via-white to-transparent opacity-0"
                  whileHover={{ opacity: 0.1, x: ['0%', '200%'] }}
                  transition={{ duration: 0.6 }}
                />
              </div>
            </motion.div>
          ))}
        </div>

        {/* Scroll indicator with bouncing animation */}
        <motion.div
          className="absolute bottom-8 left-1/2 transform -translate-x-1/2 flex flex-col items-center gap-2 cursor-pointer"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1, delay: 1.5 }}
          onClick={() => {
            const nextSection = document.querySelector('#problem');
            nextSection?.scrollIntoView({ behavior: 'smooth' });
          }}
        >
          <motion.p
            className="text-sm text-[rgba(248,250,252,0.5)] font-rajdhani"
            animate={{ opacity: [0.5, 1, 0.5] }}
            transition={{ duration: 2, repeat: Infinity }}
          >
            Scroll to explore
          </motion.p>
          <motion.div
            className="w-6 h-10 border-2 border-[rgba(0,212,255,0.4)] rounded-full flex justify-center pt-2"
            animate={{ borderColor: ['rgba(0,212,255,0.4)', 'rgba(0,212,255,0.8)', 'rgba(0,212,255,0.4)'] }}
            transition={{ duration: 2, repeat: Infinity }}
          >
            <motion.div
              className="w-1.5 h-3 bg-[#00D4FF] rounded-full"
              animate={{ y: [0, 12, 0] }}
              transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
            />
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}
