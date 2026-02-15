/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          200: '#bae6fd',
          300: '#7dd3fc',
          400: '#38bdf8',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
          800: '#075985',
          900: '#0c4a6e',
        },
        therapy: {
          calm: '#4F46E5',      // Indigo - calming
          support: '#10B981',    // Green - supportive
          warm: '#F59E0B',       // Amber - warm
          gentle: '#8B5CF6',     // Purple - gentle
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        hebrew: ['Rubik', 'Assistant', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
