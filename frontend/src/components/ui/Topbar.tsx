import { useLocation } from 'react-router-dom';
import { Search, Bell, User, ChevronDown } from 'lucide-react';
import { useState } from 'react';
import clsx from 'clsx';

const pageTitles: Record<string, string> = {
  '/': 'Dashboard', '/segments': 'Segments', '/risk': 'Risk Analysis',
  '/cameras': 'Cameras', '/alerts': 'Alerts', '/weather': 'Weather', '/settings': 'Settings',
};

export default function Topbar() {
  const location = useLocation();
  const title = pageTitles[location.pathname] || 'Dashboard';
  const [searchFocused, setSearchFocused] = useState(false);
  return (
    <header className="h-16 border-b border-[#1E2A3A] bg-[#111820] flex items-center justify-between px-6">
      <h1 className="text-[18px] font-semibold tracking-[-0.02em] text-[#F4F5F7]">{title}</h1>
      <div className="flex items-center gap-2 flex-1 max-w-md mx-8">
        <div className={clsx('flex items-center gap-2 flex-1 bg-[#1A2230] border rounded-lg px-3 py-2 transition-all duration-150 ease-in-out', searchFocused ? 'border-[#D4915E]' : 'border-[#1E2A3A]')}>
          <Search size={16} className="text-[#5E6A7A] shrink-0" />
          <input type="text" placeholder="Search segments, alerts..." className="bg-transparent text-[13px] text-[#F4F5F7] placeholder-[#5E6A7A] outline-none w-full"
            onFocus={() => setSearchFocused(true)} onBlur={() => setSearchFocused(false)} />
        </div>
      </div>
      <div className="flex items-center gap-4">
        <button className="relative p-2 rounded-lg transition-all duration-150 ease-in-out hover:bg-[#1A2230]">
          <Bell size={18} className="text-[#9BA3B0]" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-[#E85D5D] rounded-full" />
        </button>
        <button className="flex items-center gap-2 p-2 rounded-lg transition-all duration-150 ease-in-out hover:bg-[#1A2230]">
          <div className="w-7 h-7 rounded-full bg-[#232E3F] flex items-center justify-center">
            <User size={14} className="text-[#9BA3B0]" />
          </div>
          <ChevronDown size={14} className="text-[#5E6A7A]" />
        </button>
      </div>
    </header>
  );
}