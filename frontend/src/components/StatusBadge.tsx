import Chip from "@mui/material/Chip";
import type { InvoiceStatus } from "../types";

const COLOR: Record<InvoiceStatus, "success" | "warning" | "error"> = {
  paid: "success",
  pending: "warning",
  unpaid: "error",
};

interface StatusBadgeProps {
  status: InvoiceStatus | null | undefined;
}

// Colored MUI chip for an invoice status. Falls back to "pending".
export default function StatusBadge({ status }: StatusBadgeProps) {
  const value: InvoiceStatus = status || "pending";
  return (
    <Chip
      label={value}
      size="small"
      color={COLOR[value]}
      variant="outlined"
      sx={{ textTransform: "capitalize", fontWeight: 600 }}
    />
  );
}
