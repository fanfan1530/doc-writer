/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  corePlugins: {
    preflight: false,
  },
  theme: {
    extend: {
      colors: {
        police: {
          900: '#0a1628',
          800: '#0f1f3a',
          700: '#152a4d',
          600: '#1a3a5c',
          500: '#1e4470',
          400: '#2a5a8f',
          300: '#4a7ab5',
          200: '#8aadd4',
          100: '#c5d5e8',
          50: '#e8eef5',
        },
        gold: {
          600: '#a88c3a',
          500: '#c9a84c',
          400: '#d4b866',
          300: '#dfc980',
          200: '#eadba6',
          100: '#f5edcc',
        },
      },
      fontFamily: {
        sans: ['"PingFang SC"', '"Microsoft YaHei"', '"Noto Sans SC"', 'sans-serif'],
        document: ['"FangSong"', '"仿宋"', '"FZFS"', 'serif'],
      },
      animation: {
        'fade-in': 'fadeIn 0.4s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
};
