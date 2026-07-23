import { Box, Typography } from "@mui/material";

// Self-contained brand mark (no external CSS), so it works everywhere.
export default function Brand() {
  return (
    <Box sx={{ display: "inline-flex", alignItems: "center", gap: 1.25 }}>
      <Box sx={{
        width: 36, height: 36, borderRadius: 2.5, display: "grid", placeItems: "center",
        bgcolor: "primary.main", color: "primary.contrastText",
      }}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M5 2v20l2-1.5L9 22l2-1.5L13 22l2-1.5L17 22l2-1.5V2l-2 1.5L15 2l-2 1.5L11 2 9 3.5 7 2 5 3.5Z" />
          <path d="M9 8h6M9 12h6M9 16h4" />
        </svg>
      </Box>
      <Typography sx={{ fontSize: 18, fontWeight: 700, letterSpacing: "-0.02em" }}>InvoiceAI</Typography>
    </Box>
  );
}
