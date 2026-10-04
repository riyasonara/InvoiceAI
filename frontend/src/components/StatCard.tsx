import { Card, Box, Typography } from "@mui/material";
import { alpha, useTheme } from "@mui/material/styles";
import type { ReactNode } from "react";

type Tone = "default" | "brand" | "neutral" | "green" | "amber" | "red" | "indigo";

interface StatCardProps {
  label: string;
  value: ReactNode;
  icon: ReactNode;
  tone?: Tone;
  hint?: string;
}

// A single dashboard metric card: icon, label, value, optional accent tone.
// Tones map to real theme palette colors (via alpha()), not fixed hex
// values, so they stay correct in both light and dark mode.
export default function StatCard({ label, value, icon, tone = "default", hint }: StatCardProps) {
  const theme = useTheme();
  const TONE_COLOR: Record<Tone, string> = {
    default: theme.palette.primary.main,
    brand: theme.palette.primary.main,
    neutral: theme.palette.text.secondary,  // calm grey — for non-semantic metrics
    green: theme.palette.success.main,
    amber: theme.palette.warning.main,
    red: theme.palette.error.main,
    indigo: theme.palette.info.main,
  };

  return (
    <Card variant="outlined" sx={{ p: 2, height: "100%", display: "flex", alignItems: "center", gap: 1.5 }}>
      <Box sx={{
        width: 46, height: 46, borderRadius: 2, flexShrink: 0,
        display: "grid", placeItems: "center", fontSize: 20,
        bgcolor: alpha(TONE_COLOR[tone], 0.15), color: TONE_COLOR[tone],
      }}>
        {icon}
      </Box>
      <Box sx={{ minWidth: 0 }}>
        <Typography variant="body2" color="text.secondary" noWrap>{label}</Typography>
        <Typography variant="h5" sx={{ fontWeight: 700, lineHeight: 1.25 }}>{value}</Typography>
        {hint && <Typography variant="caption" color="text.secondary">{hint}</Typography>}
      </Box>
    </Card>
  );
}
