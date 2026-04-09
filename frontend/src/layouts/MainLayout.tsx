import { Outlet } from 'react-router-dom';
import Sidebar from '../components/ui/Sidebar';
import Topbar from '../components/ui/Topbar';

export default function MainLayout() {
  return (
    <div className="h-screen overflow-hidden bg-[#0B0F14]">
      <Sidebar />
      <div className="ml-[72px] flex flex-col h-screen">
        <Topbar />
        <main className="flex-1 overflow-auto"><Outlet /></main>
      </div>
    </div>
  );
}