import Box from "@mui/material/Box";
import MuiSkeleton from "@mui/material/Skeleton";

interface SkeletonProps {
  width?: number | string;
  height?: number | string;
  radius?: number;
}

export default function Skeleton({ width = "100%", height = 16, radius = 8 }: SkeletonProps) {
  return <MuiSkeleton variant="rounded" width={width} height={height} sx={{ borderRadius: `${radius}px` }} />;
}

// A block of stacked skeleton lines.
export function SkeletonLines({ count = 3 }: { count?: number }) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
      {Array.from({ length: count }).map((_, i) => (
        <MuiSkeleton key={i} variant="rounded" height={18} width={i === count - 1 ? "60%" : "100%"} />
      ))}
    </Box>
  );
}
