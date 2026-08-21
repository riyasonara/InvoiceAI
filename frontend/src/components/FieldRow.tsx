import { Stack, Typography } from "@mui/material";
import type { ReactNode } from "react";

// A label/value line inside a mobile list-card — the row-level building
// block for the card layout tables switch to below the sm breakpoint,
// so a phone gets a readable stack instead of a horizontally-scrolling table.
export default function FieldRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <Stack direction="row" spacing={2} sx={{ justifyContent: "space-between", py: 0.4 }}>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
      <Typography variant="body2" sx={{ fontWeight: 500, textAlign: "right" }}>{value}</Typography>
    </Stack>
  );
}
