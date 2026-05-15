import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        cyber: {
          bg: '#06080d',
          surface: '#0c1018',
          'surface-light': '#141a26',
          border: '#1c2436',
          accent: '#38bdf8',
          green: '#34d399',
          purple: '#a78bfa',
          warning: '#fbbf24',
          danger: '#f87171',
          safe: '#34d399',
          text: '#edf0f5',
          muted: '#7a8294',
        },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      boxShadow: {
        'glow-sm': '0 0 20px rgba(56, 189, 248, 0.08), 0 0 60px rgba(56, 189, 248, 0.03)',
        'glow-green': '0 0 20px rgba(52, 211, 153, 0.08), 0 0 60px rgba(52, 211, 153, 0.03)',
        'glow-red': '0 0 20px rgba(248, 113, 113, 0.08), 0 0 60px rgba(248, 113, 113, 0.03)',
        'glow-lg': '0 0 40px rgba(56, 189, 248, 0.12), 0 0 80px rgba(56, 189, 248, 0.05)',
      },
    },
  },
  plugins: [],
} satisfies Config
