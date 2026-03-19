import { useState, useCallback } from 'react';
import Map, { Source, Layer, Popup, NavigationControl } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { MapLayerMouseEvent } from 'react-map-gl/maplibre';
import type { GeoJSON } from 'geojson';
import type { SegmentFeatureProps } from '../../api/geojson';
import { useSegmentsGeoJSON } from '../../hooks/useSegmentMap';
import Spinner from './Spinner';

const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

const RISK_COLORS: Record<string, string> = {
  critical: '#E85D5D',
  high:     '#E8A44C',
  medium:   '#D4C24E',
  low:      '#4EA86A',
};

interface PopupInfo {
  longitude: number;
  latitude: number;
  properties: SegmentFeatureProps;
}

export default function SegmentMap({ pilot, className = '' }: { pilot?: string; className?: string }) {
  const { data: geojson, isLoading } = useSegmentsGeoJSON(pilot);
  const [popup, setPopup] = useState<PopupInfo | null>(null);

  const onClick = useCallback((e: MapLayerMouseEvent) => {
    const feature = e.features?.[0];
    if (!feature?.geometry || feature.geometry.type !== 'LineString') return;
    const coords = feature.geometry.coordinates;
    const mid = coords[Math.floor(coords.length / 2)];
    setPopup({
      longitude: mid[0],
      latitude: mid[1],
      properties: feature.properties as SegmentFeatureProps,
    });
  }, []);

  if (isLoading) return <div className={`flex items-center justify-center bg-[#111820] rounded-xl ${className}`}><Spinner /></div>;

  // Build a color-expression for the line layer
  const lineColor = [
    'match', ['get', 'level'],
    'critical', RISK_COLORS.critical,
    'high',     RISK_COLORS.high,
    'medium',   RISK_COLORS.medium,
    /* default */ RISK_COLORS.low,
  ];

  return (
    <div className={`rounded-xl overflow-hidden ${className}`}>
      <Map
        initialViewState={{ longitude: -3.7038, latitude: 40.4168, zoom: 11 }}
        style={{ width: '100%', height: '100%' }}
        mapStyle={MAP_STYLE}
        interactiveLayerIds={['segments-line']}
        onClick={onClick}
        onMouseLeave={() => setPopup(null)}
      >
        <NavigationControl position="top-right" />

        {geojson && geojson.features.length > 0 && (
          <Source id="segments" type="geojson" data={geojson as unknown as GeoJSON}>
            {/* Glow / halo */}
            <Layer
              id="segments-halo"
              type="line"
              paint={{
                'line-color': lineColor as unknown as string,
                'line-width': 8,
                'line-opacity': 0.15,
              }}
            />
            {/* Main line */}
            <Layer
              id="segments-line"
              type="line"
              paint={{
                'line-color': lineColor as unknown as string,
                'line-width': 3,
                'line-opacity': 0.9,
              }}
            />
          </Source>
        )}

        {geojson && geojson.features.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <span className="text-[13px] text-[#5E6A7A] bg-[#111820]/80 px-4 py-2 rounded-lg">
              No segments with geometry yet. Add road segments to see them on the map.
            </span>
          </div>
        )}

        {popup && (
          <Popup
            longitude={popup.longitude}
            latitude={popup.latitude}
            closeButton={false}
            anchor="bottom"
            offset={10}
          >
            <div className="bg-[#1A2230] border border-[#1E2A3A] rounded-lg p-3 min-w-[180px]">
              <p className="text-[13px] font-semibold text-white mb-1">{popup.properties.name}</p>
              <div className="flex items-center gap-2 mb-2">
                <span
                  className="text-[11px] font-medium px-2 py-0.5 rounded capitalize"
                  style={{
                    backgroundColor: RISK_COLORS[popup.properties.level] + '25',
                    color: RISK_COLORS[popup.properties.level],
                  }}
                >
                  {popup.properties.level}
                </span>
                <span className="text-[13px] font-bold" style={{ color: RISK_COLORS[popup.properties.level] }}>
                  {popup.properties.score}
                </span>
              </div>
              <div className="text-[11px] text-[#9BA3B0] space-y-0.5">
                {popup.properties.speed_limit_kmh && <p>Limit: {popup.properties.speed_limit_kmh} km/h</p>}
                {popup.properties.lanes && <p>Lanes: {popup.properties.lanes}</p>}
                {popup.properties.length_m && <p>Length: {(popup.properties.length_m / 1000).toFixed(1)} km</p>}
              </div>
            </div>
          </Popup>
        )}
      </Map>
    </div>
  );
}
