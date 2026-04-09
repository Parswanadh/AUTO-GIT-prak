import type { Metadata } from "next";
import "./globals.css";
import PipelineAmbientBackground from "@/components/PipelineAmbientBackground";
import VerificationBadge from "@/components/VerificationBadge";
import ScrollProgress from "@/components/ScrollProgress";
import PresentationModeProvider from "@/components/PresentationModeProvider";
import PresentationModeSwitcher from "@/components/PresentationModeSwitcher";
import AutoScrollDemoController from "@/components/AutoScrollDemoController";

export const metadata: Metadata = {
  title: "Auto-GIT | AI-Powered Autonomous Software Development",
  description: "Transform ideas into production-ready code using multi-agent debate, research synthesis, and automated publishing. The future of software development is here.",
  keywords: ["AI", "autonomous", "software development", "multi-agent", "code generation", "LangGraph", "GitHub automation"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="scroll-smooth">
      <body className="antialiased">
        <PresentationModeProvider>
          <ScrollProgress />
          <PipelineAmbientBackground />

          {/* Background effects */}
          <div className="starfield" />
          <div className="particle-background" />
          <div className="grid-background" />
          <div className="scanline-effect" />

          {/* Floating orbs for visual depth */}
          <div className="floating-orb orb-1" />
          <div className="floating-orb orb-2" />
          <div className="floating-orb orb-3" />
          <div className="floating-orb orb-4" />

          {/* Main content */}
          {children}

          <VerificationBadge />
          <PresentationModeSwitcher />
          <AutoScrollDemoController />
        </PresentationModeProvider>
      </body>
    </html>
  );
}
