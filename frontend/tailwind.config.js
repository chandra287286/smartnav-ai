/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      boxShadow: {
        map: '0 4px 20px rgba(15, 23, 42, 0.14)',
        'map-lg': '0 10px 30px rgba(15, 23, 42, 0.2)',
      },
    },
  },
  plugins: [],
};
