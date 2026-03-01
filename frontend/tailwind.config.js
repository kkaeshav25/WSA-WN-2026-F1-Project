/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            fontFamily: {
                display: ["'Outfit'", 'sans-serif'],
                mono: ["'JetBrains Mono'", 'monospace'],
            },
            colors: {
                'f1-bg': '#0a0a0f',
                'f1-surface': '#12121a',
                'f1-surface-alt': '#1a1a28',
                'f1-border': '#2a2a3a',
                'f1-text': '#ffffffff',
                'f1-text-muted': '#b5b5bcff',
                'f1-accent': '#e10600',
                'f1-accent-glow': '#ff2020',
                'f1-green': '#00d27a',
                'f1-yellow': '#ffc107',
                'f1-purple': '#9b59b6',
                'throttle': '#00d27a',
                'brake': '#e10600',
                'drs-active': '#00d27a',
                'drs-inactive': '#3a3a4a',
            },
        },
    },
    plugins: [],
}
