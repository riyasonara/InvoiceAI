import { Box, Stack, Typography, Button } from "@mui/material";
import ArrowBackRoundedIcon from "@mui/icons-material/ArrowBackRounded";
import type { ReactNode } from "react";

interface PageHeaderProps {
  title: ReactNode;
  subtitle?: ReactNode;
  badge?: ReactNode;
  actions?: ReactNode;
  onBack?: () => void;
}

// The title/subtitle/actions block every page opens with — was hand-rolled
// 9 times with the same responsive Stack; this is that pattern, once.
export default function PageHeader({ title, subtitle, badge, actions, onBack }: PageHeaderProps) {
  return (
    <Stack direction={{ xs: "column", sm: "row" }} spacing={2}
      sx={{ mb: 3, justifyContent: "space-between", alignItems: { sm: "flex-start" } }}>
      <Box sx={{ minWidth: 0 }}>
        {onBack && (
          <Button startIcon={<ArrowBackRoundedIcon />} onClick={onBack} size="small" sx={{ mb: 1 }}>
            Back
          </Button>
        )}
        <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>{title}</Typography>
          {badge}
        </Stack>
        {subtitle && <Typography color="text.secondary">{subtitle}</Typography>}
      </Box>
      {actions && (
        <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap" }}>{actions}</Stack>
      )}
    </Stack>
  );
}
