import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        'brand-teal': '#007B6E',
        'brand-teal-dark': '#005F55',
        'brand-light': '#ecf0ef',
        'surface': '#ffffff',
        'ink': '#000000',
        'ink-muted': '#5a6b68',
        'border': '#dfe5e3',
        'muted-bg': '#f6f8f7',
      },
    },
  },
  plugins: [],
}

export default config
