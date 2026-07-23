import { createTheme } from "@mui/material/styles";

// MUI theme matched to the existing design-token CSS (src/index.css) so MUI
// components look native to the app. Light/dark follow the OS preference,
// mirroring the current prefers-color-scheme behaviour.
const theme = createTheme({
  cssVariables: { colorSchemeSelector: "media" },
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
    fontFamily:
      'system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
    button: { textTransform: "none", fontWeight: 600 },
  },
});

export default theme;
