/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#14213d",
        surface: "#f7f9fc",
        bankred: "#c8102e",
        success: "#157f3b",
        warning: "#b7791f",
        danger: "#b91c1c"
      },
      boxShadow: {
        soft: "0 16px 40px rgba(20, 33, 61, 0.08)"
      }
    }
  },
  plugins: []
};
