import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        cyber: {
          bg: '#08090e',
          surface: '#0f1117',
          'surface-light': '#161922',
          border: '#1f2430',
          accent: '#38bdf8',
          green: '#34d399',
          purple: '#a78bfa',
          warning: '#fbbf24',
          danger: '#f87171',
          safe: '#34d399',
          text: '#e8eaed',
          muted: '#7a8294',
        },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      boxShadow: {
        'glow-sm': '0 0 12px rgba(56, 189, 248, 0.06)',
        'glow-green': '0 0 12px rgba(52, 211, 153, 0.08)',
        'glow-red': '0 0 12px rgba(248, 113, 113, 0.08)',
      },
    },
  },
  plugins: [],
} satisfies Config
