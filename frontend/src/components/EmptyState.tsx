import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import type { ReactNode } from "react";

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  message?: string;
  action?: ReactNode;
}

// Friendly empty screen: icon, title, message, optional action button.
export default function EmptyState({ icon = "📄", title, message, action }: EmptyStateProps) {
  return (
    <Box sx={{ textAlign: "center", py: 4, px: 2 }}>
      <Box sx={{ fontSize: 34 }} aria-hidden>{icon}</Box>
      <Typography variant="subtitle1" sx={{ fontWeight: 700, mt: 1 }}>{title}</Typography>
      {message && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 2 }}>{message}</Typography>
      )}
      {action}
    </Box>
  );
}
