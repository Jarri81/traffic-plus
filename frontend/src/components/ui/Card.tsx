import type { ReactNode } from 'react';
import clsx from 'clsx';

interface CardProps { children: ReactNode; className?: string; hover?: boolean; onClick?: () => void; }

export default function Card({ children, className, hover = false, onClick }: CardProps) {
  return (
    <div onClick={onClick} className={clsx(
      'bg-[#1A2230] border border-[#1E2A3A] rounded-xl p-5',
      hover && 'cursor-pointer transition-all duration-150 ease-in-out hover:border-[#2A3A4E] hover:bg-[#232E3F]',
      onClick && 'cursor-pointer', className
    )}>{children}</div>
  );
}
