'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import Link from 'next/link';
import {
  Database, Settings, Search, Filter,
  Map as MapIcon, TrendingUp, BookOpen
} from 'lucide-react';
import { CATEGORY_LABELS, getDecisionColor } from '@/lib/api';

const API_BASE = process.env.NODE_ENV === 'production'
  ? 'https://api.plansearch.cc'
  : 'http://localhost:8000';

const DECISIONS = [
  { value: '', label: 'All Decisions' },
  { value: 'granted', label: 'Granted' },
  { value: 'refused', label: 'Refused' },
  { value: 'pending', label: 'Pending' },
];

interface MapPin {
  reg_ref: string;
  lat: number;
  lng: number;
  decision: string | null;
  dev_category: string | null;
  proposal: string | null;
  location: string | null;
  apn_date: string | null;
  est_value_high: number | null;
  planning_authority: string | null;
}

interface PinResponse {
  pins: MapPin[];
  total: number;
  capped: boolean;
}

function formatValue(v: number): string {
  if (v >= 1000000) return `€${(v / 1000000).toFixed(1)}m`;
  if (v >= 1000) return `€${Math.round(v / 1000)}k`;
  return `€${v.toLocaleString()}`;
}

function getDecisionColorLocal(decision: string | null): string {
  if (!decision) return '#3b82f6';
  const upper = decision.toUpperCase();
  if (upper.includes('GRANT')) return '#10b981';
  if (upper.includes('REFUS')) return '#ef4444';
  if (upper.includes('FURTHER') || upper.includes('INFO')) return '#f59e0b';
  if (upper.includes('SPLIT')) return '#8b5cf6';
  if (upper.includes('WITHDRAW') || upper.includes('INVALID')) return '#6b7280';
  return '#3b82f6';
}

export default function MapPage() {
  const [isClient, setIsClient] = useState(false);
  const [category, setCategory] = useState('');
  const [decision, setDecision] = useState('');
  const [pinCount, setPinCount] = useState(0);
  const [capped, setCapped] = useState(false);
  const [loading, setLoading] = useState(false);

  const mapRef = useRef<any>(null);
  const clusterGroupRef = useRef<any>(null);
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const fetchTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const Lref = useRef<any>(null);

  // Track filter state in a ref so the moveend handler sees latest values
  const filtersRef = useRef({ category: '', decision: '' });
  filtersRef.current = { category, decision };

  useEffect(() => {
    setIsClient(true);
  }, []);

  const fetchPins = useCallback(async (map: any) => {
    if (!map) return;
    const bounds = map.getBounds();
    const zoom = map.getZoom();

    // Guard: if bounds are invalid (map not yet sized), skip
    const north = bounds.getNorth();
    const south = bounds.getSouth();
    const east = bounds.getEast();
    const west = bounds.getWest();
    if (isNaN(north) || isNaN(south) || isNaN(east) || isNaN(west)) {
      console.warn('Map bounds not ready yet, skipping pin fetch');
      return;
    }

    const limit = zoom < 8 ? 200 : zoom < 11 ? 500 : zoom < 14 ? 1000 : 2000;
    const { category: cat, decision: dec } = filtersRef.current;

    const params = new URLSearchParams({
      north: north.toString(),
      south: south.toString(),
      east: east.toString(),
      west: west.toString(),
      limit: limit.toString(),
    });
    if (cat) params.set('dev_category', cat);
    if (dec) params.set('decision', dec);

    setLoading(true);
    try {
      const url = `${API_BASE}/api/map/pins?${params}`;
      console.log('Fetching map pins:', url);
      const resp = await fetch(url);
      const data: PinResponse = await resp.json();

      setPinCount(data.total);
      setCapped(data.capped);

      // Rebuild cluster group
      const L = Lref.current;
      if (!L || !clusterGroupRef.current) return;

      clusterGroupRef.current.clearLayers();

      data.pins.forEach((pin: MapPin) => {
        const color = getDecisionColorLocal(pin.decision);
        const marker = L.circleMarker([pin.lat, pin.lng], {
          radius: 7,
          fillColor: color,
          color: '#fff',
          weight: 1.5,
          fillOpacity: 0.85,
        });

        const categoryLabel = pin.dev_category
          ? (CATEGORY_LABELS[pin.dev_category] || pin.dev_category.replace(/_/g, ' '))
          : '';
        const valueStr = pin.est_value_high ? formatValue(pin.est_value_high) : '';

        marker.bindPopup(`
          <div style="max-width:260px;font-family:Inter,-apple-system,sans-serif;">
            <div style="font-weight:700;font-size:13px;margin-bottom:4px;">${pin.reg_ref}</div>
            ${pin.location ? `<div style="font-size:11px;color:#666;margin-bottom:4px;">${pin.location}</div>` : ''}
            ${pin.proposal ? `<div style="font-size:11px;color:#888;margin-bottom:6px;">${pin.proposal}</div>` : ''}
            <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px;">
              ${pin.decision ? `<span style="font-size:10px;padding:1px 6px;border-radius:8px;background:${color}22;color:${color};font-weight:600;">${pin.decision}</span>` : ''}
              ${categoryLabel ? `<span style="font-size:10px;padding:1px 6px;border-radius:8px;background:rgba(29,158,117,0.1);color:#0a8a63;font-weight:600;">${categoryLabel}</span>` : ''}
              ${valueStr ? `<span style="font-size:10px;padding:1px 6px;border-radius:8px;background:rgba(16,185,129,0.1);color:#059669;font-weight:600;">${valueStr}</span>` : ''}
            </div>
            ${pin.apn_date ? `<div style="font-size:10px;color:#999;">${pin.apn_date}</div>` : ''}
            <a href="/application/${encodeURIComponent(pin.reg_ref)}" style="font-size:11px;color:#1d9e75;font-weight:600;text-decoration:none;display:inline-block;margin-top:4px;">View details →</a>
          </div>
        `);

        clusterGroupRef.current.addLayer(marker);
      });
    } catch (err) {
      console.error('Failed to fetch map pins:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Init map
  useEffect(() => {
    if (!isClient || !mapContainerRef.current || mapRef.current) return;

    let cancelled = false;

    (async () => {
      // Load Leaflet
      const leafletModule = await import('leaflet');
      // Dynamic import returns module — get default export
      const L = leafletModule.default || leafletModule;
      await import('leaflet/dist/leaflet.css');

      // CRITICAL: leaflet.markercluster expects `L` on the global scope
      // It references `L.FeatureGroup.extend(...)` directly
      (window as any).L = L;

      // Load MarkerCluster CSS via link tags (avoids TS module resolution issues)
      const mcCss1 = document.createElement('link');
      mcCss1.rel = 'stylesheet';
      mcCss1.href = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.css';
      document.head.appendChild(mcCss1);
      const mcCss2 = document.createElement('link');
      mcCss2.rel = 'stylesheet';
      mcCss2.href = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.Default.css';
      document.head.appendChild(mcCss2);

      // Load MarkerCluster JS — must come AFTER window.L is set
      await import('leaflet.markercluster');

      if (cancelled) return;

      Lref.current = L;

      const map = L.map(mapContainerRef.current!, {
        center: [53.5, -7.5],  // Centre of Ireland
        zoom: 7,
        zoomControl: true,
        attributionControl: true,
      });

      L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
        maxZoom: 19,
      }).addTo(map);

      // Create cluster group
      const clusterGroup = (L as any).markerClusterGroup({
        maxClusterRadius: 60,
        spiderfyOnMaxZoom: true,
        showCoverageOnHover: false,
        zoomToBoundsOnClick: true,
        disableClusteringAtZoom: 16,
        iconCreateFunction: (cluster: any) => {
          const count = cluster.getChildCount();
          const size = count < 10 ? 'small' : count < 100 ? 'medium' : 'large';
          return L.divIcon({
            html: `<div class="cluster-${size}">${count.toLocaleString()}</div>`,
            className: 'marker-cluster',
            iconSize: L.point(40, 40),
          });
        },
      });

      map.addLayer(clusterGroup);
      clusterGroupRef.current = clusterGroup;
      mapRef.current = map;

      // Wait for the map to be fully ready before fetching pins
      // This ensures getBounds() returns valid coordinates
      map.whenReady(() => {
        // Force a resize calculation in case the container wasn't sized yet
        map.invalidateSize();

        // Small delay to let the map settle after invalidateSize
        setTimeout(() => {
          fetchPins(map);
        }, 100);
      });

      // Reload on viewport change (debounced)
      map.on('moveend', () => {
        if (fetchTimerRef.current) clearTimeout(fetchTimerRef.current);
        fetchTimerRef.current = setTimeout(() => {
          fetchPins(map);
        }, 300);
      });
    })();

    return () => {
      cancelled = true;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, [isClient, fetchPins]);

  // Reload when filters change
  useEffect(() => {
    if (mapRef.current) {
      fetchPins(mapRef.current);
    }
  }, [category, decision, fetchPins]);

  return (
    <main style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Nav */}
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

      {/* Filter bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.5rem 2rem', background: '#111827', borderBottom: '1px solid rgba(255,255,255,0.06)', flexShrink: 0 }}>
        <Filter style={{ width: '14px', height: '14px', color: 'rgba(255,255,255,0.4)' }} />

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

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginLeft: 'auto' }}>
          {loading && (
            <span style={{ color: 'rgba(29,158,117,0.7)', fontSize: '0.75rem', animation: 'pulse 1.5s infinite' }}>Loading...</span>
          )}
          <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.75rem' }}>
            {pinCount.toLocaleString()} pins
          </span>
          {capped && (
            <span style={{
              fontSize: '0.7rem',
              padding: '1px 8px',
              borderRadius: '10px',
              background: 'rgba(245,158,11,0.15)',
              color: '#f59e0b',
              fontWeight: 600,
            }}>
              Zoom in for more
            </span>
          )}
        </div>
      </div>

      {/* Map container */}
      <div style={{ flex: 1, position: 'relative' }}>
        {!isClient ? (
          <div style={{ width: '100%', height: '100%', background: 'var(--charcoal)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ color: 'rgba(255,255,255,0.5)' }}>Loading map...</span>
          </div>
        ) : (
          <div ref={mapContainerRef} style={{ width: '100%', height: '100%' }} />
        )}

        {/* Legend */}
        <div style={{
          position: 'absolute', bottom: '1.5rem', right: '1.5rem',
          background: 'rgba(13,17,23,0.9)', backdropFilter: 'blur(8px)',
          borderRadius: '12px', border: '1px solid rgba(255,255,255,0.1)',
          padding: '0.75rem 1rem', fontSize: '0.7rem', zIndex: 1000,
          color: 'rgba(255,255,255,0.7)',
        }}>
          <div style={{ fontWeight: 600, marginBottom: '0.5rem', color: 'rgba(255,255,255,0.4)', fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Decision Status</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><div style={{ width: 10, height: 10, borderRadius: '50%', background: '#10b981' }} /> Granted</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><div style={{ width: 10, height: 10, borderRadius: '50%', background: '#ef4444' }} /> Refused</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><div style={{ width: 10, height: 10, borderRadius: '50%', background: '#f59e0b' }} /> Further Info</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><div style={{ width: 10, height: 10, borderRadius: '50%', background: '#3b82f6' }} /> Pending</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><div style={{ width: 10, height: 10, borderRadius: '50%', background: '#6b7280' }} /> Other</div>
          </div>
        </div>
      </div>
    </main>
  );
}
