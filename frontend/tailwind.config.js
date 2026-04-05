/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0f172a',    // slate-900
        surface: '#1e293b',       // slate-800
        primary: '#3b82f6',       // blue-500
        primaryHover: '#2563eb',  // blue-600
        text: '#f8fafc',          // slate-50
        textSecondary: '#94a3b8', // slate-400
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        }
      }
    },
  },
  plugins: [],
}
