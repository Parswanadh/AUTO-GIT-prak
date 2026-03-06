import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Sci-fi color palette
        background: "#030712",
        primary: "#00D4FF",
        "primary-dim": "rgba(0, 212, 255, 0.1)",
        secondary: "#7C3AED",
        "secondary-dim": "rgba(124, 58, 237, 0.1)",
        success: "#10B981",
        warning: "#F59E0B",
        error: "#EF4444",
        text: "#F8FAFC",
        "text-dim": "rgba(248, 250, 252, 0.7)",
        "text-dimmer": "rgba(248, 250, 252, 0.5)",
      },
      fontFamily: {
        orbitron: ["var(--font-orbitron)", "system-ui", "sans-serif"],
        rajdhani: ["var(--font-rajdhani)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)", "monospace"],
      },
      animation: {
        "pulse-glow": "pulse-glow 2s ease-in-out infinite",
        "float": "float 6s ease-in-out infinite",
        "scan": "scan 4s linear infinite",
        "typing": "typing 3s steps(30) infinite",
      },
      keyframes: {
        "pulse-glow": {
          "0%, 100%": { opacity: "1", filter: "brightness(1)" },
          "50%": { opacity: "0.8", filter: "brightness(1.2)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-20px)" },
        },
        scan: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100vh)" },
        },
        typing: {
          "0%, 10%": { width: "0" },
          "50%, 90%": { width: "100%" },
          "100%": { width: "0" },
        },
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic": "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
        "cyber-grid": "linear-gradient(rgba(0, 212, 255, 0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0, 212, 255, 0.03) 1px, transparent 1px)",
      },
    },
  },
  plugins: [],
};

export default config;
