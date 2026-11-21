/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html','./src/**/*.{js,jsx}'],
  theme: { extend: {
    colors: { cream:'#FAF5E9', ink:'#141414', 'lime-brand':'#B9E62E', sun:'#FFD93D', royal:'#2F6BFF', blush:'#FF6B6B' },
    fontFamily: { display:['Archivo','sans-serif'], body:['Inter','sans-serif'] },
    boxShadow: { hard:'4px 4px 0 #141414', hardSm:'2px 2px 0 #141414', hardLg:'6px 6px 0 #141414' },
    borderRadius: { '2xl':'1rem' }
  }}, plugins: []
}
