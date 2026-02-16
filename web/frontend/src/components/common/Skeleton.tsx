interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className = '' }: SkeletonProps) {
  return (
    <div className={`animate-pulse bg-border/50 rounded ${className}`} />
  );
}

export function SkeletonCard() {
  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <Skeleton className="h-3 w-24 mb-3" />
      <Skeleton className="h-8 w-32 mb-2" />
      <Skeleton className="h-3 w-16" />
    </div>
  );
}

export function SkeletonBotCard() {
  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <div className="flex items-center justify-between mb-3">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-5 w-16 rounded-full" />
      </div>
      <div className="flex items-center gap-2 mb-4">
        <Skeleton className="h-5 w-12 rounded-full" />
        <Skeleton className="h-3 w-20" />
      </div>
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div>
          <Skeleton className="h-3 w-8 mb-1" />
          <Skeleton className="h-4 w-16" />
        </div>
        <div>
          <Skeleton className="h-3 w-10 mb-1" />
          <Skeleton className="h-4 w-10" />
        </div>
      </div>
      <Skeleton className="h-7 w-16 rounded-lg" />
    </div>
  );
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center justify-between py-2 border-b border-border last:border-0">
          <div className="flex items-center gap-3">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-3 w-16" />
          </div>
          <Skeleton className="h-4 w-20" />
        </div>
      ))}
    </div>
  );
}

export function SkeletonDashboard() {
  return (
    <div>
      <Skeleton className="h-7 w-40 mb-6" />
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        {Array.from({ length: 4 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
      <div className="bg-surface border border-border rounded-xl p-5">
        <Skeleton className="h-3 w-24 mb-4" />
        <SkeletonTable rows={3} />
      </div>
    </div>
  );
}
