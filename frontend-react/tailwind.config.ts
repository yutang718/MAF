import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Driven by CSS variables set in src/theme/context.tsx, written as
        // channels so Tailwind's alpha modifiers (bg-cyber-surface/60) still work.
        cyber: {
          bg: 'rgb(var(--c-bg) / <alpha-value>)',
          surface: 'rgb(var(--c-surface) / <alpha-value>)',
          'surface-light': 'rgb(var(--c-surface-light) / <alpha-value>)',
          border: 'rgb(var(--c-border) / <alpha-value>)',
          accent: 'rgb(var(--c-accent) / <alpha-value>)',
          green: 'rgb(var(--c-green) / <alpha-value>)',
          purple: 'rgb(var(--c-purple) / <alpha-value>)',
          warning: 'rgb(var(--c-warning) / <alpha-value>)',
          danger: 'rgb(var(--c-danger) / <alpha-value>)',
          safe: 'rgb(var(--c-safe) / <alpha-value>)',
          text: 'rgb(var(--c-text) / <alpha-value>)',
          muted: 'rgb(var(--c-muted) / <alpha-value>)',
        },
      },
      fontFamily: {
        sans: ['var(--font-sans)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        'glow-sm': '0 0 20px rgb(var(--c-accent) / calc(0.08 * var(--glow-alpha))), 0 0 60px rgb(var(--c-accent) / calc(0.03 * var(--glow-alpha)))',
        'glow-green': '0 0 20px rgb(var(--c-green) / calc(0.08 * var(--glow-alpha))), 0 0 60px rgb(var(--c-green) / calc(0.03 * var(--glow-alpha)))',
        'glow-red': '0 0 20px rgb(var(--c-danger) / calc(0.08 * var(--glow-alpha))), 0 0 60px rgb(var(--c-danger) / calc(0.03 * var(--glow-alpha)))',
        'glow-lg': '0 0 40px rgb(var(--c-accent) / calc(0.12 * var(--glow-alpha))), 0 0 80px rgb(var(--c-accent) / calc(0.05 * var(--glow-alpha)))',
      },
    },
  },
  plugins: [],
} satisfies Config
