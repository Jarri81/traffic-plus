export interface Segment {
  id: string; name: string; location: string;
  riskLevel: 'critical' | 'high' | 'medium' | 'low';
  riskScore: number; cameraCount: number; lastUpdated: string; trafficDensity: number;
}
export interface Alert {
  id: string; severity: 'critical' | 'high' | 'medium' | 'low';
  segmentName: string; description: string; timestamp: string;
  status: 'active' | 'acknowledged' | 'resolved';
}
export interface Camera {
  id: string; name: string; segmentName: string;
  status: 'online' | 'offline' | 'degraded'; lastFrame: string;
}
export interface WeatherData {
  temperature: number; humidity: number; windSpeed: number;
  visibility: number; precipitation: number; condition: string;
}
export interface TrafficFlowPoint { time: string; flow: number; predicted: number; }
export interface RiskFactor { name: string; value: number; maxValue: number; }
export interface ForecastPoint { time: string; temp: number; precipitation: number; windSpeed: number; riskImpact: number; }

export const segments: Segment[] = [
  { id: 'seg-001', name: 'I-405 Northbound', location: 'Los Angeles, CA', riskLevel: 'critical', riskScore: 87, cameraCount: 6, lastUpdated: '2 min ago', trafficDensity: 94 },
  { id: 'seg-002', name: 'US-101 Hollywood', location: 'Los Angeles, CA', riskLevel: 'high', riskScore: 72, cameraCount: 4, lastUpdated: '1 min ago', trafficDensity: 81 },
  { id: 'seg-003', name: 'I-10 Santa Monica', location: 'Santa Monica, CA', riskLevel: 'high', riskScore: 68, cameraCount: 5, lastUpdated: '3 min ago', trafficDensity: 76 },
  { id: 'seg-004', name: 'SR-134 Eagle Rock', location: 'Glendale, CA', riskLevel: 'medium', riskScore: 45, cameraCount: 3, lastUpdated: '1 min ago', trafficDensity: 52 },
  { id: 'seg-005', name: 'I-5 Burbank Blvd', location: 'Burbank, CA', riskLevel: 'medium', riskScore: 41, cameraCount: 4, lastUpdated: '5 min ago', trafficDensity: 48 },
  { id: 'seg-006', name: 'I-110 Downtown', location: 'Los Angeles, CA', riskLevel: 'low', riskScore: 23, cameraCount: 3, lastUpdated: '2 min ago', trafficDensity: 31 },
  { id: 'seg-007', name: 'PCH Malibu', location: 'Malibu, CA', riskLevel: 'low', riskScore: 18, cameraCount: 2, lastUpdated: '4 min ago', trafficDensity: 22 },
  { id: 'seg-008', name: 'I-710 Long Beach', location: 'Long Beach, CA', riskLevel: 'high', riskScore: 65, cameraCount: 5, lastUpdated: '1 min ago', trafficDensity: 73 },
  { id: 'seg-009', name: 'SR-2 Glendale Fwy', location: 'Glendale, CA', riskLevel: 'medium', riskScore: 39, cameraCount: 2, lastUpdated: '6 min ago', trafficDensity: 44 },
  { id: 'seg-010', name: 'I-605 Whittier', location: 'Whittier, CA', riskLevel: 'low', riskScore: 15, cameraCount: 3, lastUpdated: '3 min ago', trafficDensity: 19 },
  { id: 'seg-011', name: 'US-101 Ventura Fwy', location: 'Sherman Oaks, CA', riskLevel: 'critical', riskScore: 91, cameraCount: 7, lastUpdated: '1 min ago', trafficDensity: 97 },
  { id: 'seg-012', name: 'I-405 Sepulveda Pass', location: 'Bel Air, CA', riskLevel: 'high', riskScore: 74, cameraCount: 4, lastUpdated: '2 min ago', trafficDensity: 85 },
];

export const alerts: Alert[] = [
  { id: 'alt-001', severity: 'critical', segmentName: 'I-405 Northbound', description: 'Multi-vehicle collision detected — lanes 2 & 3 blocked. Emergency response dispatched.', timestamp: '2026-03-11T22:03:00Z', status: 'active' },
  { id: 'alt-002', severity: 'critical', segmentName: 'US-101 Ventura Fwy', description: 'Traffic density exceeding 95% capacity. Congestion cascade risk imminent.', timestamp: '2026-03-11T21:58:00Z', status: 'active' },
  { id: 'alt-003', severity: 'high', segmentName: 'US-101 Hollywood', description: 'Speed variance spike detected — potential erratic driving behavior in lanes 1-3.', timestamp: '2026-03-11T21:45:00Z', status: 'active' },
  { id: 'alt-004', severity: 'high', segmentName: 'I-710 Long Beach', description: 'Heavy vehicle concentration above threshold. Road wear risk elevated.', timestamp: '2026-03-11T21:30:00Z', status: 'acknowledged' },
  { id: 'alt-005', severity: 'medium', segmentName: 'SR-134 Eagle Rock', description: 'Visibility dropping below 500m due to fog. Weather-adjusted risk increasing.', timestamp: '2026-03-11T21:15:00Z', status: 'acknowledged' },
  { id: 'alt-006', severity: 'medium', segmentName: 'I-10 Santa Monica', description: 'Unusual traffic pattern detected — possible event-related surge.', timestamp: '2026-03-11T20:50:00Z', status: 'active' },
  { id: 'alt-007', severity: 'low', segmentName: 'I-110 Downtown', description: 'Camera CAM-110-02 intermittent signal — switching to backup feed.', timestamp: '2026-03-11T20:30:00Z', status: 'resolved' },
  { id: 'alt-008', severity: 'high', segmentName: 'I-405 Sepulveda Pass', description: 'Rapid deceleration wave detected — stop-and-go pattern forming.', timestamp: '2026-03-11T22:01:00Z', status: 'active' },
  { id: 'alt-009', severity: 'low', segmentName: 'PCH Malibu', description: 'Scheduled maintenance zone ahead — speed reduction advisory active.', timestamp: '2026-03-11T19:00:00Z', status: 'resolved' },
  { id: 'alt-010', severity: 'medium', segmentName: 'I-5 Burbank Blvd', description: 'Construction zone proximity alert — merging traffic above normal levels.', timestamp: '2026-03-11T21:00:00Z', status: 'acknowledged' },
];

export const cameras: Camera[] = [
  { id: 'cam-001', name: 'CAM-405-N01', segmentName: 'I-405 Northbound', status: 'online', lastFrame: '2s ago' },
  { id: 'cam-002', name: 'CAM-405-N02', segmentName: 'I-405 Northbound', status: 'online', lastFrame: '1s ago' },
  { id: 'cam-003', name: 'CAM-405-N03', segmentName: 'I-405 Northbound', status: 'degraded', lastFrame: '8s ago' },
  { id: 'cam-004', name: 'CAM-101-H01', segmentName: 'US-101 Hollywood', status: 'online', lastFrame: '2s ago' },
  { id: 'cam-005', name: 'CAM-101-H02', segmentName: 'US-101 Hollywood', status: 'online', lastFrame: '1s ago' },
  { id: 'cam-006', name: 'CAM-10-SM01', segmentName: 'I-10 Santa Monica', status: 'online', lastFrame: '3s ago' },
  { id: 'cam-007', name: 'CAM-10-SM02', segmentName: 'I-10 Santa Monica', status: 'offline', lastFrame: '5 min ago' },
  { id: 'cam-008', name: 'CAM-134-ER01', segmentName: 'SR-134 Eagle Rock', status: 'online', lastFrame: '2s ago' },
  { id: 'cam-009', name: 'CAM-5-BB01', segmentName: 'I-5 Burbank Blvd', status: 'online', lastFrame: '1s ago' },
  { id: 'cam-010', name: 'CAM-110-DT01', segmentName: 'I-110 Downtown', status: 'online', lastFrame: '2s ago' },
  { id: 'cam-011', name: 'CAM-110-DT02', segmentName: 'I-110 Downtown', status: 'degraded', lastFrame: '12s ago' },
  { id: 'cam-012', name: 'CAM-PCH-M01', segmentName: 'PCH Malibu', status: 'online', lastFrame: '3s ago' },
  { id: 'cam-013', name: 'CAM-710-LB01', segmentName: 'I-710 Long Beach', status: 'online', lastFrame: '1s ago' },
  { id: 'cam-014', name: 'CAM-710-LB02', segmentName: 'I-710 Long Beach', status: 'online', lastFrame: '2s ago' },
  { id: 'cam-015', name: 'CAM-101-VF01', segmentName: 'US-101 Ventura Fwy', status: 'online', lastFrame: '1s ago' },
  { id: 'cam-016', name: 'CAM-405-SP01', segmentName: 'I-405 Sepulveda Pass', status: 'offline', lastFrame: '12 min ago' },
];

export const currentWeather: WeatherData = { temperature: 14, humidity: 72, windSpeed: 18, visibility: 6.2, precipitation: 0.3, condition: 'Partly Cloudy' };

export const trafficFlow: TrafficFlowPoint[] = [
  { time: '00:00', flow: 145, predicted: 140 }, { time: '01:00', flow: 120, predicted: 125 },
  { time: '02:00', flow: 98, predicted: 105 }, { time: '03:00', flow: 85, predicted: 90 },
  { time: '04:00', flow: 110, predicted: 108 }, { time: '05:00', flow: 180, predicted: 175 },
  { time: '06:00', flow: 420, predicted: 410 }, { time: '07:00', flow: 860, predicted: 840 },
  { time: '08:00', flow: 950, predicted: 920 }, { time: '09:00', flow: 880, predicted: 870 },
  { time: '10:00', flow: 520, predicted: 530 }, { time: '11:00', flow: 480, predicted: 490 },
  { time: '12:00', flow: 550, predicted: 540 }, { time: '13:00', flow: 510, predicted: 520 },
  { time: '14:00', flow: 490, predicted: 500 }, { time: '15:00', flow: 580, predicted: 570 },
  { time: '16:00', flow: 920, predicted: 900 }, { time: '17:00', flow: 1050, predicted: 1020 },
  { time: '18:00', flow: 980, predicted: 960 }, { time: '19:00', flow: 750, predicted: 740 },
  { time: '20:00', flow: 420, predicted: 430 }, { time: '21:00', flow: 310, predicted: 320 },
  { time: '22:00', flow: 210, predicted: 215 }, { time: '23:00', flow: 165, predicted: 160 },
];

export const riskFactors: RiskFactor[] = [
  { name: 'Traffic Density', value: 82, maxValue: 100 },
  { name: 'Speed Variance', value: 67, maxValue: 100 },
  { name: 'Incident History', value: 54, maxValue: 100 },
  { name: 'Weather Impact', value: 38, maxValue: 100 },
  { name: 'Time Patterns', value: 71, maxValue: 100 },
  { name: 'Road Geometry', value: 29, maxValue: 100 },
  { name: 'Maintenance Status', value: 45, maxValue: 100 },
];

export const riskDistribution = [
  { name: 'Critical', value: 2, color: '#E85D5D' },
  { name: 'High', value: 4, color: '#E8A44C' },
  { name: 'Medium', value: 3, color: '#D4C24E' },
  { name: 'Low', value: 3, color: '#4EA86A' },
];

export const historicalRisk = [
  { day: 'Mar 1', score: 52 }, { day: 'Mar 2', score: 48 }, { day: 'Mar 3', score: 55 },
  { day: 'Mar 4', score: 61 }, { day: 'Mar 5', score: 58 }, { day: 'Mar 6', score: 67 },
  { day: 'Mar 7', score: 72 }, { day: 'Mar 8', score: 65 }, { day: 'Mar 9', score: 59 },
  { day: 'Mar 10', score: 54 }, { day: 'Mar 11', score: 51 }, { day: 'Mar 12', score: 47 },
  { day: 'Mar 13', score: 53 }, { day: 'Mar 14', score: 62 }, { day: 'Mar 15', score: 68 },
  { day: 'Mar 16', score: 74 }, { day: 'Mar 17', score: 71 }, { day: 'Mar 18', score: 66 },
  { day: 'Mar 19', score: 58 }, { day: 'Mar 20', score: 55 }, { day: 'Mar 21', score: 49 },
  { day: 'Mar 22', score: 52 }, { day: 'Mar 23', score: 60 }, { day: 'Mar 24', score: 64 },
  { day: 'Mar 25', score: 70 }, { day: 'Mar 26', score: 75 }, { day: 'Mar 27', score: 69 },
  { day: 'Mar 28', score: 63 }, { day: 'Mar 29', score: 57 }, { day: 'Mar 30', score: 64 },
];

export const forecast: ForecastPoint[] = [
  { time: '+0h', temp: 14, precipitation: 0.3, windSpeed: 18, riskImpact: 32 },
  { time: '+2h', temp: 13, precipitation: 0.5, windSpeed: 20, riskImpact: 38 },
  { time: '+4h', temp: 12, precipitation: 1.2, windSpeed: 22, riskImpact: 45 },
  { time: '+6h', temp: 11, precipitation: 2.1, windSpeed: 25, riskImpact: 58 },
  { time: '+8h', temp: 10, precipitation: 2.8, windSpeed: 28, riskImpact: 67 },
  { time: '+10h', temp: 10, precipitation: 3.2, windSpeed: 30, riskImpact: 72 },
  { time: '+12h', temp: 11, precipitation: 2.5, windSpeed: 27, riskImpact: 61 },
  { time: '+14h', temp: 12, precipitation: 1.8, windSpeed: 24, riskImpact: 52 },
  { time: '+16h', temp: 14, precipitation: 0.8, windSpeed: 20, riskImpact: 40 },
  { time: '+18h', temp: 15, precipitation: 0.2, windSpeed: 16, riskImpact: 28 },
  { time: '+20h', temp: 14, precipitation: 0.0, windSpeed: 14, riskImpact: 22 },
  { time: '+22h', temp: 13, precipitation: 0.0, windSpeed: 12, riskImpact: 18 },
  { time: '+24h', temp: 12, precipitation: 0.1, windSpeed: 15, riskImpact: 24 },
  { time: '+26h', temp: 11, precipitation: 0.4, windSpeed: 18, riskImpact: 30 },
  { time: '+28h', temp: 11, precipitation: 0.9, windSpeed: 21, riskImpact: 42 },
  { time: '+30h', temp: 10, precipitation: 1.5, windSpeed: 24, riskImpact: 50 },
  { time: '+32h', temp: 10, precipitation: 2.0, windSpeed: 26, riskImpact: 56 },
  { time: '+34h', temp: 11, precipitation: 1.6, windSpeed: 23, riskImpact: 48 },
  { time: '+36h', temp: 12, precipitation: 1.0, windSpeed: 20, riskImpact: 38 },
  { time: '+38h', temp: 13, precipitation: 0.4, windSpeed: 17, riskImpact: 29 },
  { time: '+40h', temp: 14, precipitation: 0.1, windSpeed: 15, riskImpact: 23 },
  { time: '+42h', temp: 15, precipitation: 0.0, windSpeed: 13, riskImpact: 19 },
  { time: '+44h', temp: 14, precipitation: 0.0, windSpeed: 12, riskImpact: 17 },
  { time: '+46h', temp: 13, precipitation: 0.2, windSpeed: 14, riskImpact: 21 },
  { time: '+48h', temp: 12, precipitation: 0.5, windSpeed: 16, riskImpact: 27 },
];

export const sparklineData = (seed: number) => [
  { v: seed }, { v: seed + 3 }, { v: seed - 2 }, { v: seed + 5 },
  { v: seed + 1 }, { v: seed + 8 }, { v: seed + 4 }, { v: seed + 10 },
  { v: seed + 6 }, { v: seed + 12 }, { v: seed + 9 }, { v: seed + 15 },
];

export const systemRiskScore = 64;

export const stats = {
  activeSegments: 12, averageRisk: 53, openAlerts: 7,
  camerasOnline: 13, totalCameras: 16,
};