import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        background: 'var(--bg-main)',
        surface: 'var(--bg-surface)',
        panel: 'var(--bg-panel)',
        border: 'var(--border-color)',
        content: {
          DEFAULT: 'var(--text-main)',
          muted: 'var(--text-muted)',
        },
        accent: {
          DEFAULT: 'var(--accent-primary)',
          glow: 'var(--accent-glow)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
} satisfies Config
