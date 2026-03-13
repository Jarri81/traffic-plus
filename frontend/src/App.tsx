import { BrowserRouter, Routes, Route } from 'react-router-dom';
import MainLayout from './layouts/MainLayout';
import Dashboard from './pages/Dashboard';
import Segments from './pages/Segments';
import RiskAnalysis from './pages/RiskAnalysis';
import Cameras from './pages/Cameras';
import Alerts from './pages/Alerts';
import Weather from './pages/Weather';
import Settings from './pages/Settings';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<MainLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/segments" element={<Segments />} />
          <Route path="/risk" element={<RiskAnalysis />} />
          <Route path="/cameras" element={<Cameras />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/weather" element={<Weather />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}