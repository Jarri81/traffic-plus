import type { ReactNode, ButtonHTMLAttributes } from 'react';
import clsx from 'clsx';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary'; size?: 'sm' | 'md' | 'lg'; children: ReactNode;
}

const sizeClasses = { sm: 'px-3 py-1.5 text-[11px]', md: 'px-4 py-2 text-[13px]', lg: 'px-6 py-2.5 text-[15px]' };
const variantClasses = {
  primary: 'bg-[#D4915E] text-[#0B0F14] font-semibold hover:bg-[#E0A06E]',
  secondary: 'bg-transparent border border-[#2A3A4E] text-[#9BA3B0] font-medium hover:border-[#D4915E] hover:text-[#F4F5F7]',
};

export default function Button({ variant = 'primary', size = 'md', children, className, ...props }: ButtonProps) {
  return (
    <button className={clsx('rounded-lg transition-all duration-150 ease-in-out inline-flex items-center gap-2 tracking-[0.01em]', variantClasses[variant], sizeClasses[size], className)} {...props}>
      {children}
    </button>
  );
}
