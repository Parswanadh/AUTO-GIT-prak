'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const navItems = [
  { name: 'Home', href: '#hero' },
  { name: 'Problem', href: '#problem' },
  { name: 'Pipeline', href: '#pipeline' },
  { name: 'Models', href: '#model-showcase' },
  { name: 'Architecture', href: '#architecture' },
  { name: 'Demo', href: '#demo' },
];

export default function Navigation() {
  const [isOpen, setIsOpen] = useState(false);
  const [activeSection, setActiveSection] = useState('hero');

  useEffect(() => {
    const handleScroll = () => {
      const sections = navItems.map(item => item.href.slice(1));
      for (const section of sections) {
        const element = document.getElementById(section);
        if (element) {
          const rect = element.getBoundingClientRect();
          if (rect.top <= 100 && rect.bottom >= 100) {
            setActiveSection(section);
            break;
          }
        }
      }
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <motion.nav
      className="fixed top-0 left-0 right-0 z-50 bg-[rgba(3,7,18,0.9)] backdrop-blur-md border-b border-[rgba(0,212,255,0.1)]"
      initial={{ y: -100 }}
      animate={{ y: 0 }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo with subtle glow on hover */}
          <motion.div
            className="font-orbitron font-bold text-xl text-[#00D4FF]"
            whileHover={{ scale: 1.05 }}
            transition={{ duration: 0.2 }}
          >
            Auto-GIT
          </motion.div>

          {/* Desktop nav with hover effects */}
          <div className="hidden md:flex items-center space-x-8">
            {navItems.map((item, index) => (
              <motion.a
                key={item.name}
                href={item.href}
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: index * 0.05 }}
                whileHover={{ y: -2 }}
                className={`text-sm font-medium transition-colors relative ${
                  activeSection === item.href.slice(1)
                    ? 'text-[#00D4FF]'
                    : 'text-[rgba(248,250,252,0.7)] hover:text-[#00D4FF]'
                }`}
                style={{
                  textShadow: activeSection === item.href.slice(1)
                    ? '0 0 10px rgba(0, 212, 255, 0.5)'
                    : 'none'
                }}
              >
                {item.name}
                {/* Active indicator */}
                {activeSection === item.href.slice(1) && (
                  <motion.div
                    className="absolute -bottom-1 left-0 right-0 h-0.5 bg-[#00D4FF]"
                    layoutId="activeIndicator"
                    transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                  />
                )}
              </motion.a>
            ))}
          </div>

          {/* Mobile menu button */}
          <motion.button
            onClick={() => setIsOpen(!isOpen)}
            className="md:hidden p-2 rounded-lg text-[rgba(248,250,252,0.7)] hover:text-[#00D4FF]"
            whileTap={{ scale: 0.95 }}
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {isOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </motion.button>
        </div>

        {/* Mobile menu with animation */}
        <AnimatePresence>
          {isOpen && (
            <motion.div
              className="md:hidden py-4 space-y-2"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.3 }}
            >
              {navItems.map((item, index) => (
                <motion.a
                  key={item.name}
                  href={item.href}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.2, delay: index * 0.05 }}
                  className="block px-4 py-2 rounded-lg text-[rgba(248,250,252,0.7)] hover:text-[#00D4FF] hover:bg-[rgba(0,212,255,0.1)]"
                  onClick={() => setIsOpen(false)}
                  whileHover={{ x: 5 }}
                >
                  {item.name}
                </motion.a>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.nav>
  );
}
