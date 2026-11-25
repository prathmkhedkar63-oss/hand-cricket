/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        cricket: {
          dark: '#0a0d14',
          card: '#111726',
          border: '#1e293b',
          accent: '#10b981',
          gold: '#f59e0b',
          crimson: '#ef4444',
          sky: '#0284c7'
        }
      }
    },
  },
  plugins: [],
}
