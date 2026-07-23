import { Card, Box, Typography } from "@mui/material";
import type { ReactNode } from "react";

type Tone = "default" | "brand" | "green" | "amber" | "red" | "indigo";

const ICON_BG: Record<Tone, string> = {
  default: "rgba(20,184,166,0.15)",
  brand: "rgba(20,184,166,0.15)",
  green: "rgba(16,185,129,0.15)",
  amber: "rgba(245,158,11,0.15)",
  red: "rgba(239,68,68,0.15)",
  indigo: "rgba(99,102,241,0.15)",
};

interface StatCardProps {
  label: string;
  value: ReactNode;
  icon: ReactNode;
  tone?: Tone;
  hint?: string;
}

// A single dashboard metric card: icon, label, value, optional accent tone.
export default function StatCard({ label, value, icon, tone = "default", hint }: StatCardProps) {
  return (
    <Card variant="outlined" sx={{ p: 2, height: "100%", display: "flex", alignItems: "center", gap: 1.5 }}>
      <Box sx={{
        width: 46, height: 46, borderRadius: 2, flexShrink: 0,
        display: "grid", placeItems: "center", fontSize: 20, bgcolor: ICON_BG[tone],
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
