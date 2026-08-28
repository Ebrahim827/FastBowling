/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        pitch: {
          950: "#0A120E",   // deepest background - turf at night, not pure black
          900: "#0F1A14",
          800: "#16241D",   // card/surface background
          700: "#223328",
          600: "#33473A",
        },
        seam: {
          DEFAULT: "#A8321F",  // cricket ball oxblood red - primary accent
          light: "#C24632",
          dark: "#7C2416",
        },
        bail: {
          DEFAULT: "#D2A24C",  // stumps/bails gold - secondary accent
          light: "#E3BE73",
        },
        cream: "#F1EEE2",       // cricket whites - primary text
        sage: "#8FA396",        // muted pitch-grey-green - secondary text
      },
      fontFamily: {
        display: ["Oswald", "sans-serif"],
        body: ["Inter", "sans-serif"],
        mono: ["IBM Plex Mono", "monospace"],
      },
    },
  },
  plugins: [],
}
