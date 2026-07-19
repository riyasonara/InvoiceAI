// Shimmer placeholder. Pass width/height (any CSS size) and optional radius.
export default function Skeleton({ width = "100%", height = 16, radius = 8, style }) {
  return (
    <span
      className="skeleton"
      style={{ width, height, borderRadius: radius, ...style }}
    />
  );
}

// A block of stacked skeleton lines.
export function SkeletonLines({ count = 3 }) {
  return (
    <div className="skeleton-lines">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} height={14} width={i === count - 1 ? "60%" : "100%"} />
      ))}
    </div>
  );
}
