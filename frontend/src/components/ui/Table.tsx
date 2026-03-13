import type { ReactNode } from 'react';
import clsx from 'clsx';

interface Column<T> { key: string; header: string; render: (row: T) => ReactNode; className?: string; }
interface TableProps<T> { columns: Column<T>[]; data: T[]; keyExtractor: (row: T) => string; className?: string; }

export default function Table<T>({ columns, data, keyExtractor, className }: TableProps<T>) {
  return (
    <div className={clsx('overflow-auto', className)}>
      <table className="w-full">
        <thead className="sticky top-0 bg-[#1A2230] z-10">
          <tr>
            {columns.map((col) => (
              <th key={col.key} className={clsx('text-left text-[11px] font-medium text-[#5E6A7A] tracking-[0.01em] uppercase px-4 py-3 border-b border-[#1E2A3A]', col.className)}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr key={keyExtractor(row)} className="transition-all duration-150 ease-in-out hover:bg-[#232E3F]">
              {columns.map((col) => (
                <td key={col.key} className={clsx('px-4 py-3 text-[13px] border-b border-[#1E2A3A]/50', col.className)}>
                  {col.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
