'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import {
  Database, Settings, Search, Filter, ArrowLeft,
  Map as MapIcon, List, TrendingUp, BookOpen
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
    <main style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Nav — consistent with all pages */}
      <nav style={{ background: '#0d1117', borderBottom: '1px solid rgba(255,255,255,0.06)', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: '64px', padding: '0 2rem', width: '100%' }}>
          <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'white', textDecoration: 'none' }}>
            <Database className="w-5 h-5 text-[var(--teal)]" />
            <span style={{ color: 'white', fontSize: '1.125rem', fontWeight: '600', letterSpacing: '-0.01em', fontFamily: "'Playfair Display', serif" }}>PlanSearch</span>
          </Link>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            <Link href="/" className="nav-link">
              <Search className="w-5 h-5" />
              <span className="hidden sm:inline">Search</span>
            </Link>
            <Link href="/map" className="nav-link" style={{ color: 'var(--teal)' }}>
              <MapIcon className="w-5 h-5" />
              <span className="hidden sm:inline">Map</span>
            </Link>
            <Link href="/significant" className="nav-link">
              <TrendingUp className="w-5 h-5" />
              <span className="hidden sm:inline">Significant</span>
            </Link>
            <Link href="/insights" className="nav-link">
              <BookOpen className="w-5 h-5" />
              <span className="hidden sm:inline">Insights</span>
            </Link>
            <Link href="/admin" className="nav-link">
              <Settings className="w-5 h-5" />
              <span className="hidden sm:inline">Admin</span>
            </Link>
          </div>
        </div>
      </nav>

      {/* Map filters bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.5rem 2rem', background: '#111827', borderBottom: '1px solid rgba(255,255,255,0.06)', flexShrink: 0 }}>
        <div style={{ position: 'relative' }}>
          <Search style={{ position: 'absolute', left: '0.625rem', top: '50%', transform: 'translateY(-50%)', width: '14px', height: '14px', color: 'rgba(255,255,255,0.4)' }} />
          <input
            type="text"
            placeholder="Filter map..."
            style={{ background: 'rgba(255,255,255,0.08)', color: 'white', fontSize: '0.85rem', border: '1px solid rgba(255,255,255,0.12)', borderRadius: '8px', padding: '0.4rem 0.75rem 0.4rem 2rem', outline: 'none' }}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        <select
          style={{ background: 'rgba(255,255,255,0.08)', color: 'white', fontSize: '0.85rem', border: '1px solid rgba(255,255,255,0.12)', borderRadius: '8px', padding: '0.4rem 0.75rem', outline: 'none' }}
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          <option value="" style={{ color: 'black' }}>All Categories</option>
          {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
            <option key={key} value={key} style={{ color: 'black' }}>{label}</option>
          ))}
        </select>

        <select
          style={{ background: 'rgba(255,255,255,0.08)', color: 'white', fontSize: '0.85rem', border: '1px solid rgba(255,255,255,0.12)', borderRadius: '8px', padding: '0.4rem 0.75rem', outline: 'none' }}
          value={decision}
          onChange={(e) => setDecision(e.target.value)}
        >
          {DECISIONS.map(d => <option key={d.value} value={d.value} style={{ color: 'black' }}>{d.label}</option>)}
        </select>

        {mapData && (
          <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.75rem', marginLeft: '0.25rem' }}>{mapData.total.toLocaleString()} pins</span>
        )}
      </div>

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
            <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full" style={{ background: '#3b82f6' }} /> Pending / Undecided</div>
            <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full" style={{ background: '#6b7280' }} /> Other (withdrawn, invalid)</div>
          </div>
        </div>
      </div>
    </main>
  );
}
