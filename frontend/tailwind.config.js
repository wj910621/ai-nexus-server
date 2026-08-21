/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // TRAE 风格配色
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
        },
        sidebar: {
          bg: '#1e1e2e',
          hover: '#2a2a3e',
          active: '#3b3f54',
          text: '#cdd6f4',
        },
        brand: {
          primary: 'var(--brand-primary)',
          hover: 'var(--brand-primary-hover)',
          active: 'var(--brand-primary-active)',
          light: 'var(--brand-primary-light)',
        },
        accent: {
          cyan: 'var(--accent-cyan)',
          emerald: 'var(--accent-emerald)',
          amber: 'var(--accent-amber)',
          rose: 'var(--accent-rose)',
          violet: 'var(--accent-violet)',
        },
        surface: {
          base: 'var(--bg-base)',
          surface: 'var(--bg-surface)',
          elevated: 'var(--bg-elevated)',
          hover: 'var(--bg-hover)',
          active: 'var(--bg-active)',
        },
      },
      boxShadow: {
        glow: 'var(--shadow-glow)',
      },
      animation: {
        'pulse-dot': 'pulse-dot 2s ease-in-out infinite',
        blink: 'blink 1s infinite',
      },
    },
  },
  plugins: [],
}
