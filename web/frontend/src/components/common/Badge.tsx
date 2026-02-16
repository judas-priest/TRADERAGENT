interface BadgeProps {
  variant: 'success' | 'error' | 'warning' | 'info' | 'default';
  children: React.ReactNode;
}

const variants = {
  success: 'bg-profit/20 text-profit',
  error: 'bg-loss/20 text-loss',
  warning: 'bg-orange/20 text-orange',
  info: 'bg-blue/20 text-blue',
  default: 'bg-border text-text-muted',
};

export function Badge({ variant, children }: BadgeProps) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${variants[variant]}`}>
      {children}
    </span>
  );
}
