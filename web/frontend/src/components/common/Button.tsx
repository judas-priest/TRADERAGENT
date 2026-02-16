import { type ButtonHTMLAttributes, type ReactNode } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'danger' | 'ghost';
  size?: 'sm' | 'md';
  children: ReactNode;
}

const variants = {
  primary: 'bg-primary hover:bg-primary-hover text-white',
  danger: 'bg-loss/20 hover:bg-loss/30 text-loss',
  ghost: 'bg-transparent hover:bg-surface-hover text-text-muted hover:text-text',
};

const sizes = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2 text-sm',
};

export function Button({ variant = 'primary', size = 'md', children, className = '', ...props }: ButtonProps) {
  return (
    <button
      className={`rounded-lg font-medium transition-colors disabled:opacity-50 ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
