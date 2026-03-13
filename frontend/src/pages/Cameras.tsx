import { useState } from 'react';
import { Camera, Grid2x2, Grid3x3, LayoutGrid } from 'lucide-react';
import clsx from 'clsx';
import PageContainer from '../components/ui/PageContainer';
import { cameras } from '../data/mock';
import type { Camera as CameraType } from '../data/mock';

type GridSize = '2x2' | '3x3' | '4x4';
const gridClasses: Record<GridSize, string> = { '2x2': 'grid-cols-2', '3x3': 'grid-cols-3', '4x4': 'grid-cols-4' };
const statusConfig = {
  online: { dot: 'bg-[#4EA8A6]', label: 'Online' },
  offline: { dot: 'bg-[#E85D5D]', label: 'Offline' },
  degraded: { dot: 'bg-[#D4915E]', label: 'Degraded' },
};
const gridIcons: { size: GridSize; icon: typeof Grid2x2 }[] = [
  { size: '2x2', icon: Grid2x2 }, { size: '3x3', icon: Grid3x3 }, { size: '4x4', icon: LayoutGrid },
];

export default function Cameras() {
  const [gridSize, setGridSize] = useState<GridSize>('3x3');
  const online = cameras.filter((c) => c.status === 'online').length;
  const degraded = cameras.filter((c) => c.status === 'degraded').length;
  const offline = cameras.filter((c) => c.status === 'offline').length;
  return (
    <PageContainer className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h2 className="text-[22px] font-semibold tracking-[-0.02em] text-[#F4F5F7]">{cameras.length} Cameras</h2>
          <div className="flex items-center gap-3 text-[11px] font-medium">
            <span className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-[#4EA8A6]" /><span className="text-[#9BA3B0]">{online} Online</span></span>
            <span className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-[#D4915E]" /><span className="text-[#9BA3B0]">{degraded} Degraded</span></span>
            <span className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-[#E85D5D]" /><span className="text-[#9BA3B0]">{offline} Offline</span></span>
          </div>
        </div>
        <div className="flex items-center gap-1 bg-[#1A2230] rounded-lg p-1 border border-[#1E2A3A]">
          {gridIcons.map(({ size, icon: Icon }) => (
            <button key={size} onClick={() => setGridSize(size)}
              className={clsx('p-2 rounded-md transition-all duration-150 ease-in-out', gridSize === size ? 'bg-[#232E3F] text-[#D4915E]' : 'text-[#5E6A7A] hover:text-[#9BA3B0]')}>
              <Icon size={16} />
            </button>
          ))}
        </div>
      </div>
      <div className={clsx('grid gap-4', gridClasses[gridSize])}>
        {cameras.map((cam: CameraType) => {
          const sc = statusConfig[cam.status];
          return (
            <div key={cam.id} className="bg-[#1A2230] border border-[#1E2A3A] rounded-xl overflow-hidden transition-all duration-150 ease-in-out hover:border-[#2A3A4E]">
              <div className="aspect-video bg-[#111820] flex items-center justify-center relative">
                <Camera size={32} className="text-[#232E3F]" />
                <div className="absolute top-3 left-3 flex items-center gap-1.5 bg-[rgba(17,24,32,0.7)] backdrop-blur-sm px-2 py-1 rounded-md">
                  <span className={clsx('w-1.5 h-1.5 rounded-full', sc.dot)} />
                  <span className="text-[11px] font-medium text-[#9BA3B0]">{sc.label}</span>
                </div>
              </div>
              <div className="p-3">
                <p className="text-[13px] font-medium text-[#F4F5F7]">{cam.name}</p>
                <p className="text-[11px] text-[#5E6A7A] mt-0.5">{cam.segmentName} · {cam.lastFrame}</p>
              </div>
            </div>
          );
        })}
      </div>
    </PageContainer>
  );
}