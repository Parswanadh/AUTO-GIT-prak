'use client';

import React from 'react';
import dynamic from 'next/dynamic';

// Import Navigation directly
import Navigation from '@/components/Navigation';

// Dynamic imports for sections - all use default exports
const HeroSection = dynamic(() => import('@/components/sections/HeroSection'), { ssr: true });
const ProblemSection = dynamic(() => import('@/components/sections/ProblemSection'));
const PipelineSection = dynamic(() => import('@/components/sections/PipelineSection'));
const MultiAgentSection = dynamic(() => import('@/components/sections/MultiAgentSection'));
const ModelManagementSection = dynamic(() => import('@/components/sections/ModelManagementSection'));
const ErrorMemorySection = dynamic(() => import('@/components/sections/ErrorMemorySection'));
const EvolutionSection = dynamic(() => import('@/components/sections/EvolutionSection'));
const ValidationSection = dynamic(() => import('@/components/sections/ValidationSection'));
const TechStackSection = dynamic(() => import('@/components/sections/TechStackSection'));
const CodeShowcaseSection = dynamic(() => import('@/components/sections/CodeShowcaseSection'));
const MetricsDashboard = dynamic(() => import('@/components/sections/MetricsDashboard'));
const ComparisonSection = dynamic(() => import('@/components/sections/ComparisonSection'));
const ArchitectureSection = dynamic(() => import('@/components/sections/ArchitectureSection'));
const LiveDemoSection = dynamic(() => import('@/components/sections/LiveDemoSection'));
const RoadmapSection = dynamic(() => import('@/components/sections/RoadmapSection'));

export default function HomePage() {
  return (
    <main className="relative min-h-screen bg-[#030712] w-full">
      {/* Navigation */}
      <Navigation />

      {/* Hero Section */}
      <section id="hero" className="w-full">
        {React.createElement(HeroSection || 'div')}
      </section>

      {/* Problem Section */}
      <section id="problem" className="w-full">
        {React.createElement(ProblemSection || 'div')}
      </section>

      {/* Pipeline Section (THE CENTERPIECE) */}
      <section id="pipeline" className="w-full">
        {React.createElement(PipelineSection || 'div')}
      </section>

      {/* Multi-Agent Debate Section */}
      <section id="multi-agent" className="w-full">
        {React.createElement(MultiAgentSection || 'div')}
      </section>

      {/* Model Management Section */}
      <section id="model-management" className="w-full">
        {React.createElement(ModelManagementSection || 'div')}
      </section>


      {/* Error Memory Section */}
      <section id="error-memory" className="w-full">
        {React.createElement(ErrorMemorySection || 'div')}
      </section>

      {/* Evolution Section */}
      <section id="evolution" className="w-full">
        {React.createElement(EvolutionSection || 'div')}
      </section>

      {/* Validation Section */}
      <section id="validation" className="w-full">
        {React.createElement(ValidationSection || 'div')}
      </section>

      {/* Tech Stack Section */}
      <section id="tech-stack" className="w-full">
        {React.createElement(TechStackSection || 'div')}
      </section>

      {/* Code Showcase Section */}
      <section id="code-showcase" className="w-full">
        {React.createElement(CodeShowcaseSection || 'div')}
      </section>

      {/* Metrics Dashboard */}
      <section id="metrics" className="w-full">
        {React.createElement(MetricsDashboard || 'div')}
      </section>

      {/* Comparison Section */}
      <section id="comparison" className="w-full">
        {React.createElement(ComparisonSection || 'div')}
      </section>

      {/* Architecture Section */}
      <section id="architecture" className="w-full">
        {React.createElement(ArchitectureSection || 'div')}
      </section>

      {/* Live Demo Section */}
      <section id="demo" className="w-full">
        {React.createElement(LiveDemoSection || 'div')}
      </section>

      {/* Roadmap Section */}
      <section id="roadmap" className="w-full">
        {React.createElement(RoadmapSection || 'div')}
      </section>

      {/* Footer */}
      <footer className="relative py-12 border-t border-slate-800 bg-slate-900/50 w-full">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid md:grid-cols-3 gap-8 mb-8">
            {/* Links */}
            <div>
              <h4 className="text-white font-semibold mb-4">Project</h4>
              <ul className="space-y-2">
                <li>
                  <a href="https://github.com/Parswanadh/auto-git" target="_blank" rel="noopener noreferrer" className="text-slate-400 hover:text-cyan-400 transition-colors">
                    Source Code
                  </a>
                </li>
                <li>
                  <a href="https://github.com/Parswanadh/auto-git-pipeline-runs" target="_blank" rel="noopener noreferrer" className="text-slate-400 hover:text-cyan-400 transition-colors">
                    Pipeline Runs
                  </a>
                </li>
              </ul>
            </div>

            {/* Info */}
            <div>
              <h4 className="text-white font-semibold mb-4">Built By</h4>
              <p className="text-slate-400 mb-2">Parswanadh</p>
              <p className="text-slate-500 text-sm">Feb 22-26, 2026</p>
            </div>

            {/* Stats */}
            <div>
              <h4 className="text-white font-semibold mb-4">System Stats</h4>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-cyan-400 font-semibold">47,726</span>
                  <span className="text-slate-500 ml-1">LOC</span>
                </div>
                <div>
                  <span className="text-purple-400 font-semibold">27</span>
                  <span className="text-slate-500 ml-1">Runs</span>
                </div>
                <div>
                  <span className="text-emerald-400 font-semibold">233</span>
                  <span className="text-slate-500 ml-1">Errors</span>
                </div>
                <div>
                  <span className="text-blue-400 font-semibold">27+</span>
                  <span className="text-slate-500 ml-1">Models</span>
                </div>
              </div>
            </div>
          </div>

          <div className="pt-8 border-t border-slate-800 text-center">
            <p className="text-slate-500 text-sm">
              © 2026 Auto-GIT. Built with Next.js, TypeScript, Tailwind CSS, and Framer Motion.
            </p>
          </div>
        </div>
      </footer>
    </main>
  );
}
