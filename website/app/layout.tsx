import type { Metadata } from "next";
import "./globals.css";

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
        {/* Background effects */}
        <div className="starfield" />
        <div className="particle-background" />
        <div className="grid-background" />
        <div className="scanline-effect" />

        {/* Floating orbs for visual depth - MUCH LARGER */}
        <div className="floating-orb orb-1" />
        <div className="floating-orb orb-2" />
        <div className="floating-orb orb-3" />
        <div className="floating-orb orb-4" />

        {/* Main content */}
        {children}
      </body>
    </html>
  );
}
