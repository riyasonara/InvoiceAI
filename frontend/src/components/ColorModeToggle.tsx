import { IconButton, Tooltip } from "@mui/material";
import { useColorScheme } from "@mui/material/styles";
import LightModeRoundedIcon from "@mui/icons-material/LightModeRounded";
import DarkModeRoundedIcon from "@mui/icons-material/DarkModeRounded";

// Reads the resolved system preference only to decide what the *first*
// toggle click switches away from — mode starts as "system" and MUI itself
// resolves that to light/dark via CSS, so there's nothing to read here
// beyond mode/setMode.
export default function ColorModeToggle() {
  const { mode, systemMode, setMode } = useColorScheme();
  const resolved = mode === "system" ? systemMode : mode;

  function toggle() {
    setMode(resolved === "dark" ? "light" : "dark");
  }

  return (
    <Tooltip title={resolved === "dark" ? "Switch to light mode" : "Switch to dark mode"}>
      <IconButton onClick={toggle} color="inherit" aria-label="Toggle color mode">
        {resolved === "dark" ? <LightModeRoundedIcon /> : <DarkModeRoundedIcon />}
      </IconButton>
    </Tooltip>
  );
}
