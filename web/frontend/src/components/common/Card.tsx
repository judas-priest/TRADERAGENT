import { type ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  className?: string;
  title?: string;
}

export function Card({ children, className = '', title }: CardProps) {
  return (
    <div className={`bg-surface border border-border rounded-xl p-5 ${className}`}>
      {title && <h3 className="text-sm font-semibold text-text-muted mb-3 uppercase tracking-wide">{title}</h3>}
      {children}
    </div>
  );
}
