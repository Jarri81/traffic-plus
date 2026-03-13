import type { ReactNode } from 'react';
import clsx from 'clsx';

interface PageContainerProps { children: ReactNode; className?: string; }

export default function PageContainer({ children, className }: PageContainerProps) {
  return <div className={clsx('p-6 max-w-[1600px] mx-auto w-full', className)}>{children}</div>;
}
