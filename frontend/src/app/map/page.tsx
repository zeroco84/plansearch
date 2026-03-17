'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import {
  Database, Settings, Search, Filter, ArrowLeft,
  Map as MapIcon, List
} from 'lucide-react';
import {
  getMapPoints, MapFeatureCollection, SearchParams,
  CATEGORY_LABELS, getDecisionColor
} from '@/lib/api';

// Dynamic import for Leaflet (no SSR - requires window)
const MapContainer = dynamic(
  () => import('react-leaflet').then(mod => mod.MapContainer),
  { ssr: false }
);
const TileLayer = dynamic(
  () => import('react-leaflet').then(mod => mod.TileLayer),
  { ssr: false }
);
const CircleMarker = dynamic(
  () => import('react-leaflet').then(mod => mod.CircleMarker),
  { ssr: false }
);
const Popup = dynamic(
  () => import('react-leaflet').then(mod => mod.Popup),
  { ssr: false }
);

const DECISIONS = [
  { value: '', label: 'All Decisions' },
  { value: 'GRANTED', label: 'Granted' },
  { value: 'REFUSED', label: 'Refused' },
  { value: 'FURTHER_INFO', label: 'Further Info' },
];

export default function MapPage() {
  const [mapData, setMapData] = useState<MapFeatureCollection | null>(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');
  const [decision, setDecision] = useState('');
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
    // Import leaflet CSS
    import('leaflet/dist/leaflet.css');
  }, []);

  const loadMapData = useCallback(async () => {
    setLoading(true);
    try {
      const params: SearchParams = { page_size: 5000 };
      if (query) params.q = query;
      if (category) params.category = category;
      if (decision) params.decision = decision;

      const data = await getMapPoints(params);
      setMapData(data);
    } catch (err) {
      console.error('Map data error:', err);
    } finally {
      setLoading(false);
    }
  }, [query, category, decision]);

  useEffect(() => {
    const timer = setTimeout(loadMapData, 500);
    return () => clearTimeout(timer);
  }, [loadMapData]);

  return (
    <main className="h-screen flex flex-col">
      {/* Nav */}
      <nav className="hero-gradient flex-shrink-0" style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div className="max-w-full mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/" className="flex items-center gap-2 text-white no-underline">
              <Database className="w-5 h-5 text-[var(--teal)]" />
              <span className="font-semibold text-lg" style={{ fontFamily: "'Playfair Display', serif" }}>PlanSearch</span>
            </Link>
            <span className="text-white/30">|</span>
            <span className="text-white/70 text-sm flex items-center gap-1"><MapIcon className="w-4 h-4" /> Map View</span>
          </div>

          {/* Map filters */}
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-white/40" />
              <input
                type="text"
                placeholder="Filter map..."
                className="bg-white/10 text-white text-sm border border-white/15 rounded-lg pl-8 pr-3 py-1.5 focus:outline-none focus:border-[var(--teal)] placeholder:text-white/40"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>

            <select
              className="bg-white/10 text-white text-sm border border-white/15 rounded-lg px-3 py-1.5 focus:outline-none [&>option]:text-black"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              <option value="">All Categories</option>
              {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>

            <select
              className="bg-white/10 text-white text-sm border border-white/15 rounded-lg px-3 py-1.5 focus:outline-none [&>option]:text-black"
              value={decision}
              onChange={(e) => setDecision(e.target.value)}
            >
              {DECISIONS.map(d => <option key={d.value} value={d.value}>{d.label}</option>)}
            </select>

            {mapData && (
              <span className="text-white/40 text-xs ml-2">{mapData.total.toLocaleString()} pins</span>
            )}

            <Link href="/" className="nav-link">
              <List className="w-4 h-4" /> List
            </Link>
            <Link href="/admin" className="nav-link">
              <Settings className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </nav>

      {/* Map */}
      <div className="flex-1 relative">
        {!isClient ? (
          <div className="w-full h-full bg-[var(--charcoal)] flex items-center justify-center">
            <span className="text-white/50">Loading map...</span>
          </div>
        ) : (
          <MapContainer
            center={[53.35, -6.26]}
            zoom={12}
            style={{ width: '100%', height: '100%' }}
            zoomControl={true}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
            />
            {mapData?.features.map((feature, i) => {
              const [lng, lat] = feature.geometry.coordinates;
              const color = getDecisionColor(feature.properties.decision);
              return (
                <CircleMarker
                  key={i}
                  center={[lat, lng]}
                  radius={5}
                  pathOptions={{
                    color: color,
                    fillColor: color,
                    fillOpacity: 0.7,
                    weight: 1,
                  }}
                >
                  <Popup>
                    <div style={{ maxWidth: 250 }}>
                      <div className="font-bold text-sm">{feature.properties.reg_ref}</div>
                      {feature.properties.location && (
                        <div className="text-xs text-gray-600 mt-1">{feature.properties.location}</div>
                      )}
                      {feature.properties.proposal && (
                        <div className="text-xs text-gray-500 mt-1">{feature.properties.proposal}</div>
                      )}
                      <Link
                        href={`/application/${encodeURIComponent(feature.properties.reg_ref)}`}
                        className="text-xs text-[var(--teal)] mt-2 inline-block font-medium"
                      >
                        View details →
                      </Link>
                    </div>
                  </Popup>
                </CircleMarker>
              );
            })}
          </MapContainer>
        )}

        {loading && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-[var(--charcoal)] text-white px-4 py-2 rounded-full text-sm shadow-lg z-[1000]">
            <span className="animate-pulse">Loading map data...</span>
          </div>
        )}

        {/* Legend */}
        <div className="absolute bottom-6 right-6 bg-white rounded-lg shadow-lg p-3 text-xs z-[1000]">
          <div className="font-semibold mb-2">Decision Status</div>
          <div className="space-y-1">
            <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full" style={{ background: '#10b981' }} /> Granted</div>
            <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full" style={{ background: '#ef4444' }} /> Refused</div>
            <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full" style={{ background: '#f59e0b' }} /> Further Info</div>
            <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full" style={{ background: '#3b82f6' }} /> Pending</div>
            <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full" style={{ background: '#6b7280' }} /> Other</div>
          </div>
        </div>
      </div>
    </main>
  );
}
