import { createTheme } from "@mui/material/styles";

// "class"-driven color scheme (not "media"): lets useColorScheme() override
// the OS preference and persists the user's choice to localStorage — the
// mechanism ColorModeToggle relies on.
const theme = createTheme({
  cssVariables: { colorSchemeSelector: "class" },
  colorSchemes: {
    light: {
      palette: {
        primary: { main: "#0d9488" },
        background: { default: "#f5f7f7", paper: "#ffffff" },
        text: { primary: "#0f1a18", secondary: "#5c6b68" },
        divider: "#e2e8e7",
        success: { main: "#10b981" },
        warning: { main: "#d97706" },
        error: { main: "#ef4444" },
      },
    },
    dark: {
      palette: {
        primary: { main: "#17b8a6" },
        background: { default: "#0a0d0c", paper: "#141a19" },
        text: { primary: "#e9eeed", secondary: "#98a4a1" },
        divider: "#262e2d",
        success: { main: "#17b8a6" },
        warning: { main: "#f59e0b" },
        error: { main: "#ef4444" },
      },
    },
  },
  shape: { borderRadius: 12 },
  typography: {
    fontFamily: '"Source Sans 3", system-ui, -apple-system, "Segoe UI", sans-serif',
    h1: { fontFamily: '"Lexend", system-ui, sans-serif', fontWeight: 700, letterSpacing: "-0.01em" },
    h2: { fontFamily: '"Lexend", system-ui, sans-serif', fontWeight: 700, letterSpacing: "-0.01em" },
    h3: { fontFamily: '"Lexend", system-ui, sans-serif', fontWeight: 600 },
    h4: { fontFamily: '"Lexend", system-ui, sans-serif', fontWeight: 600, letterSpacing: "-0.01em" },
    h5: { fontFamily: '"Lexend", system-ui, sans-serif', fontWeight: 600 },
    h6: { fontFamily: '"Lexend", system-ui, sans-serif', fontWeight: 600 },
    subtitle1: { fontFamily: '"Lexend", system-ui, sans-serif', fontWeight: 600 },
    subtitle2: { fontFamily: '"Lexend", system-ui, sans-serif', fontWeight: 600 },
    button: { textTransform: "none", fontWeight: 600 },
  },
});

export default theme;
