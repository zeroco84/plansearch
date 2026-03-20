'use client';

import React, { useState, useEffect, useRef, useCallback, useMemo, Component } from 'react';
import dynamic from 'next/dynamic';

const IrelandMap = dynamic(() => import('@/components/analytics/IrelandMap'), { ssr: false });
import Link from 'next/link';
import {
  Database, Search, Map as MapIcon, TrendingUp, BookOpen, Bell, UserCircle, BarChart3,
  ChevronDown, ExternalLink, Share2, Twitter, Linkedin, Info,
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  LineChart, Line, AreaChart, Area, Treemap, Cell, ReferenceLine,
} from 'recharts';
import {
  getStats, formatValue, CATEGORY_LABELS,
  getAnalyticsPipelineGap, getAnalyticsPermissionsByYear,
  getAnalyticsLifecycleFunnel, getAnalyticsRefusalRates,
  getAnalyticsValueByCounty, getAnalyticsDataCentres,
  getAnalyticsRenewablesByCounty, getAnalyticsTopApplications,
  getAnalyticsExtensionsTrend, getAnalyticsCommencementLag,
} from '@/lib/api';

// ── Error Boundary (catches render crashes and shows the real error) ──
class ChartErrorBoundary extends Component<
  { children: React.ReactNode },
  { hasError: boolean; error: string }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: '' };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error: `${error.name}: ${error.message}\n${error.stack}` };
  }
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('Analytics crash:', error, info);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '2rem', fontFamily: 'monospace', fontSize: '0.85rem', background: '#fef2f2', color: '#991b1b', borderRadius: 8, margin: '1rem', whiteSpace: 'pre-wrap', maxHeight: '50vh', overflow: 'auto' }}>
          <strong>Analytics page crashed:</strong>
          <br />{this.state.error}
        </div>
      );
    }
    return this.props.children;
  }
}

// ── Colours ────────────────────────────────────────────────────────────
const TEAL = '#2dd4bf';
const DARK_NAVY = '#0f172a';
const NAVY_800 = '#1e293b';
const CHART_TEAL = '#14b8a6';
const CHART_BLUE = '#3b82f6';
const CHART_RED = '#ef4444';
const CHART_GREY = '#94a3b8';
const CHART_GREEN = '#22c55e';
const CHART_PURPLE = '#8b5cf6';
const BG_WHITE = '#ffffff';
const BG_LIGHT = '#f8fafc';

const TREEMAP_COLORS = [
  '#0d9488', '#0891b2', '#0284c7', '#7c3aed', '#c026d3',
  '#e11d48', '#ea580c', '#d97706', '#65a30d', '#059669',
];

// ── Animated Counter Hook ──────────────────────────────────────────────
function useAnimatedCounter(target: number, duration = 2000, active = true) {
  const [value, setValue] = useState(0);
  const ref = useRef<HTMLDivElement>(null);
  const animated = useRef(false);
  const prevTarget = useRef(0);

  useEffect(() => {
    if (!active || !target || target === prevTarget.current) return;
    prevTarget.current = target;
    animated.current = true;
    let cancelled = false;
    const el = ref.current;
    if (!el) {
      setValue(target);
      return;
    }
    const obs = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting && !cancelled) {
        const start = performance.now();
        const step = (now: number) => {
          if (cancelled) return;
          const t = Math.min((now - start) / duration, 1);
          const ease = 1 - Math.pow(1 - t, 4);
          setValue(Math.floor(ease * target));
          if (t < 1) requestAnimationFrame(step);
          else setValue(target);
        };
        requestAnimationFrame(step);
        obs.disconnect();
      }
    }, { threshold: 0.3 });
    obs.observe(el);
    return () => { cancelled = true; obs.disconnect(); };
  }, [target, duration, active]);

  return { value, ref };
}

// ── Section Wrapper ────────────────────────────────────────────────────
function Section({ id, number, title, intro, children, bg = BG_WHITE }: {
  id: string; number: number; title: string; intro: string; children: React.ReactNode; bg?: string;
}) {
  const [showMethodology, setShowMethodology] = useState(false);
  const url = `https://plansearch.cc/analytics#${id}`;
  const tweetText = encodeURIComponent(`${intro} — See the data → ${url}`);
  return (
    <section id={id} style={{ background: bg, padding: '4rem 1.5rem' }}>
      <div style={{ maxWidth: '1100px', margin: '0 auto' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
          <div style={{ width: 36, height: 36, borderRadius: '50%', background: CHART_TEAL, color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '0.9rem', flexShrink: 0 }}>{number}</div>
          <div style={{ flex: 1, minWidth: 200 }}>
            <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#0f172a', margin: 0, fontFamily: "'Playfair Display', serif" }}>{title}</h2>
            <p style={{ fontSize: '1rem', color: '#64748b', margin: '0.5rem 0 0', lineHeight: 1.6, fontStyle: 'italic' }}>{intro}</p>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <a href={`https://twitter.com/intent/tweet?text=${tweetText}`} target="_blank" rel="noopener" style={{ color: '#94a3b8' }}><Twitter size={18} /></a>
            <a href={`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`} target="_blank" rel="noopener" style={{ color: '#94a3b8' }}><Linkedin size={18} /></a>
          </div>
        </div>
        {children}
        <button onClick={() => setShowMethodology(!showMethodology)} style={{ marginTop: '1.5rem', background: 'none', border: 'none', color: '#94a3b8', fontSize: '0.8rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
          <Info size={14} /> Methodology <ChevronDown size={14} style={{ transform: showMethodology ? 'rotate(180deg)' : 'none', transition: '0.2s' }} />
        </button>
        {showMethodology && (
          <div style={{ marginTop: '0.5rem', padding: '1rem', background: '#f1f5f9', borderRadius: 8, fontSize: '0.8rem', color: '#64748b', lineHeight: 1.7 }}>
            <strong>Data source:</strong> PlanSearch database aggregated from NPAD (30 ROI councils), Cork County ePlan, and OpenDataNI.<br />
            <strong>Value estimates:</strong> Mitchell McDermott InfoCard benchmarks — construction cost only, excludes VAT, site, professional fees.<br />
            <strong>Update frequency:</strong> NPAD synced continuously, BCMS synced weekly, NI data updated annually.
          </div>
        )}
      </div>
    </section>
  );
}

// ── Loading Skeleton ───────────────────────────────────────────────────
function ChartSkeleton({ height = 300 }: { height?: number }) {
  return (
    <div style={{ height, background: 'linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%)', backgroundSize: '200% 100%', animation: 'shimmer 1.5s infinite', borderRadius: 12 }} />
  );
}

// ── Format helpers ─────────────────────────────────────────────────────
function fmtNum(n: number) { return n?.toLocaleString('en-IE') ?? '—'; }
function fmtBn(n: number) { if (!n) return '€0'; if (n >= 1e9) return `€${(n/1e9).toFixed(1)}bn`; if (n >= 1e6) return `€${(n/1e6).toFixed(0)}m`; return `€${(n/1e3).toFixed(0)}k`; }
function shortAuthority(a: string) { return a?.replace(/ County Council| City Council| City & County Council/g, '') ?? ''; }

// ══════════════════════════════════════════════════════════════════════
// MAIN PAGE
// ══════════════════════════════════════════════════════════════════════

function AnalyticsPageInner() {
  const [stats, setStats] = useState<any>(null);
  const [pipelineGap, setPipelineGap] = useState<any[]>([]);
  const [permsByYear, setPermsByYear] = useState<any[]>([]);
  const [funnel, setFunnel] = useState<any[]>([]);
  const [refusalRates, setRefusalRates] = useState<any[]>([]);
  const [valueByCounty, setValueByCounty] = useState<any[]>([]);
  const [dataCentres, setDataCentres] = useState<any[]>([]);
  const [renewables, setRenewables] = useState<any[]>([]);
  const [topApps, setTopApps] = useState<any[]>([]);
  const [extensions, setExtensions] = useState<any[]>([]);
  const [commencementLag, setCommencementLag] = useState<any[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [authorityToCounty, setAuthorityToCounty] = useState<Record<string, string>>({});
  const [countyPop, setCountyPop] = useState<Record<string, number>>({});

  useEffect(() => {
    // Load static JSON
    fetch('/data/authority-to-county.json').then(r => r.json()).then(setAuthorityToCounty).catch(() => {});
    fetch('/data/county-populations.json').then(r => r.json()).then(setCountyPop).catch(() => {});
    // Load analytics
    Promise.allSettled([
      getStats().then(setStats),
      getAnalyticsPipelineGap().then(r => setPipelineGap(r.data)),
      getAnalyticsPermissionsByYear().then(r => setPermsByYear(r.data)),
      getAnalyticsLifecycleFunnel().then(r => setFunnel(r.data)),
      getAnalyticsRefusalRates().then(r => setRefusalRates(r.data)),
      getAnalyticsValueByCounty().then(r => setValueByCounty(r.data)),
      getAnalyticsDataCentres().then(r => setDataCentres(r.data)),
      getAnalyticsRenewablesByCounty().then(r => setRenewables(r.data)),
      getAnalyticsTopApplications().then(r => setTopApps(r.data)),
      getAnalyticsExtensionsTrend().then(r => setExtensions(r.data)),
      getAnalyticsCommencementLag().then(r => setCommencementLag(r.data)),
    ]).finally(() => setLoaded(true));
  }, []);

  // ── Derived data (all memoised to prevent infinite re-render) ──
  const totalApps = useMemo(() => stats?.total_applications ?? 0, [stats]);
  const funnelMap = useMemo(() => Object.fromEntries(funnel.map((f: any) => [f.stage, f.count])), [funnel]);
  const underConstruction = useMemo(() => funnelMap['commenced'] ?? 0, [funnelMap]);
  const completed = useMemo(() => funnelMap['completed'] ?? 0, [funnelMap]);
  const totalUnbuiltValue = useMemo(() => pipelineGap.reduce((s: number, r: any) => s + Number(r.unbuilt_value || 0), 0), [pipelineGap]);

  // Hero counters
  const c1 = useAnimatedCounter(totalApps, 2000, loaded);
  const c2 = useAnimatedCounter(underConstruction, 2000, loaded);
  const c3 = useAnimatedCounter(completed, 2000, loaded);
  const c4Val = totalUnbuiltValue;

  // Permissions by year: reshape for grouped bar
  const yearData = useMemo(() => {
    const years: Record<string, any> = {};
    permsByYear.forEach((r: any) => {
      if (!years[r.year]) years[r.year] = { year: r.year };
      const cat = r.dev_category === 'residential_apartments' ? 'Apartments' :
                  r.dev_category === 'residential_houses' ? 'Houses' : null;
      if (cat) years[r.year][cat] = (years[r.year][cat] || 0) + Number(r.count || 0);
    });
    return Object.values(years).sort((a: any, b: any) => a.year - b.year);
  }, [permsByYear]);

  // Refusal rates: aggregate by authority for overall
  const refusalByAuthority = useMemo(() => {
    const map: Record<string, { granted: number; refused: number; total: number }> = {};
    refusalRates.forEach((r: any) => {
      if (!map[r.planning_authority]) map[r.planning_authority] = { granted: 0, refused: 0, total: 0 };
      map[r.planning_authority].granted += Number(r.granted || 0);
      map[r.planning_authority].refused += Number(r.refused || 0);
      map[r.planning_authority].total += Number(r.total || 0);
    });
    return Object.entries(map).map(([auth, v]) => ({
      authority: shortAuthority(auth),
      refusal_rate: v.total > 0 ? Math.round(v.refused / v.total * 1000) / 10 : 0,
      ...v,
    })).sort((a, b) => b.refusal_rate - a.refusal_rate);
  }, [refusalRates]);

  // Value by county: aggregate for treemap
  const valueTreemap = useMemo(() => {
    const map: Record<string, number> = {};
    valueByCounty.forEach((r: any) => {
      const k = shortAuthority(r.planning_authority);
      map[k] = (map[k] || 0) + Number(r.total_value || 0);
    });
    return Object.entries(map).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value).slice(0, 25);
  }, [valueByCounty]);

  // Extensions: reshape for area chart
  const extByYear = useMemo(() => {
    const years: Record<number, number> = {};
    extensions.forEach((r: any) => { years[r.year] = (years[r.year] || 0) + Number(r.count || 0); });
    return Object.entries(years).map(([y, c]) => ({ year: +y, count: c })).sort((a, b) => a.year - b.year);
  }, [extensions]);

  // Data centres by year
  const dcByYear = useMemo(() => {
    const years: Record<number, { granted: number; refused: number; pending: number }> = {};
    dataCentres.forEach((r: any) => {
      const y = r.year || 0;
      if (!years[y]) years[y] = { granted: 0, refused: 0, pending: 0 };
      const d = (r.decision || '').toLowerCase();
      if (d.includes('grant') || d.includes('conditional')) years[y].granted++;
      else if (d.includes('refus')) years[y].refused++;
      else years[y].pending++;
    });
    return Object.entries(years).filter(([y]) => +y >= 2015).map(([y, v]) => ({ year: +y, ...v })).sort((a, b) => a.year - b.year);
  }, [dataCentres]);

  // Pipeline gap: top 15
  const pipelineTop15 = useMemo(() => pipelineGap.slice(0, 15).map((r: any) => ({
    authority: shortAuthority(r.planning_authority),
    count: Number(r.unbuilt_count || 0),
    value: Number(r.unbuilt_value || 0),
  })), [pipelineGap]);

  // ── Section 3: Where Ireland Builds (per capita by county) ──
  const appsPerCapita = useMemo(() => {
    const byCounty: Record<string, number> = {};
    permsByYear.forEach((r: any) => {
      const county = authorityToCounty[r.planning_authority || ''];
      if (county) byCounty[county] = (byCounty[county] || 0) + Number(r.count || 0);
    });
    const result: Record<string, number> = {};
    Object.entries(byCounty).forEach(([c, count]) => {
      const pop = countyPop[c];
      if (pop) result[c] = Math.round(count / pop * 1000);
    });
    return result;
  }, [permsByYear, authorityToCounty, countyPop]);

  // ── Section 5: One-off house grant rate by county ──
  const oneOffByCounty = useMemo(() => {
    const map: Record<string, { granted: number; total: number }> = {};
    refusalRates.filter((r: any) => r.dev_category === 'residential_new_build').forEach((r: any) => {
      const county = authorityToCounty[r.planning_authority || ''];
      if (!county) return;
      if (!map[county]) map[county] = { granted: 0, total: 0 };
      map[county].granted += Number(r.granted || 0);
      map[county].total += Number(r.total || 0);
    });
    return Object.entries(map).map(([county, v]) => ({
      county,
      grant_rate: v.total > 0 ? Math.round(v.granted / v.total * 1000) / 10 : 0,
      ...v,
    })).sort((a, b) => b.grant_rate - a.grant_rate);
  }, [refusalRates, authorityToCounty]);
  const oneOffMap = useMemo(() => {
    const m: Record<string, number> = {};
    oneOffByCounty.forEach(r => { m[r.county] = r.grant_rate; });
    return m;
  }, [oneOffByCounty]);

  // ── Section 8: Renewables by county (aggregate) ──
  const renewablesByCounty = useMemo(() => {
    const map: Record<string, { granted: number; total: number }> = {};
    renewables.forEach((r: any) => {
      const county = authorityToCounty[r.planning_authority || ''];
      if (!county) return;
      if (!map[county]) map[county] = { granted: 0, total: 0 };
      map[county].granted += Number(r.granted || 0);
      map[county].total += Number(r.total || 0);
    });
    return Object.entries(map).map(([county, v]) => ({
      county,
      total: v.total,
      grant_rate: v.total > 0 ? Math.round(v.granted / v.total * 1000) / 10 : 0,
    })).sort((a, b) => b.total - a.total);
  }, [renewables, authorityToCounty]);
  const renewableCountMap = useMemo(() => {
    const m: Record<string, number> = {};
    renewablesByCounty.forEach(r => { m[r.county] = r.total; });
    return m;
  }, [renewablesByCounty]);
  // Renewables by year
  const renewablesByYear = useMemo(() => {
    const years: Record<number, number> = {};
    renewables.forEach((r: any) => { if (r.year >= 2015) years[r.year] = (years[r.year] || 0) + Number(r.total || 0); });
    return Object.entries(years).map(([y, c]) => ({ year: +y, count: c })).sort((a, b) => a.year - b.year);
  }, [renewables]);

  return (
    <div style={{ background: BG_WHITE, minHeight: '100vh', fontFamily: "'Inter', -apple-system, sans-serif" }}>
      {/* NAV */}
      <nav style={{ background: DARK_NAVY, borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 64, padding: '0 2rem', width: '100%' }}>
          <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'white', textDecoration: 'none' }}>
            <Database className="w-5 h-5" style={{ color: TEAL }} />
            <span style={{ color: 'white', fontSize: '1.125rem', fontWeight: 600, fontFamily: "'Playfair Display', serif" }}>PlanSearch</span>
          </Link>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            <Link href="/" className="nav-link"><Search className="w-5 h-5" /><span className="hidden sm:inline">Search</span></Link>
            <Link href="/map" className="nav-link"><MapIcon className="w-5 h-5" /><span className="hidden sm:inline">Map</span></Link>
            <Link href="/significant" className="nav-link"><TrendingUp className="w-5 h-5" /><span className="hidden sm:inline">Significant</span></Link>
            <Link href="/analytics" className="nav-link" style={{ color: TEAL }}><BarChart3 className="w-5 h-5" /><span className="hidden sm:inline">Analytics</span></Link>
            <Link href="/alerts" className="nav-link"><Bell className="w-5 h-5" /><span className="hidden sm:inline">Alerts</span></Link>
            <Link href="/blog" className="nav-link"><BookOpen className="w-5 h-5" /><span className="hidden sm:inline">Blog</span></Link>
          </div>
        </div>
      </nav>

      {/* ═══ HERO STATS BAR ═══ */}
      <div ref={c1.ref} style={{ background: `linear-gradient(135deg, ${DARK_NAVY}, ${NAVY_800})`, padding: '3rem 1.5rem' }}>
        <div style={{ maxWidth: 1100, margin: '0 auto', textAlign: 'center' }}>
          <h1 style={{ color: '#fff', fontSize: '2rem', fontWeight: 700, margin: '0 0 0.5rem', fontFamily: "'Playfair Display', serif" }}>Ireland Planning Analytics</h1>
          <p style={{ color: '#94a3b8', fontSize: '1rem', margin: '0 0 2.5rem' }}>Live data from {fmtNum(totalApps)} planning applications across 43 local authorities</p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '2rem' }}>
            {[
              { val: fmtNum(c1.value), label: 'Planning Applications' },
              { val: fmtNum(c2.value), label: 'Under Construction' },
              { val: fmtNum(c3.value), label: 'Schemes Completed' },
              { val: fmtBn(c4Val), label: 'Unbuilt Pipeline Value' },
              { val: '43', label: 'Local Authorities' },
            ].map((s, i) => (
              <div key={i}>
                <div style={{ color: TEAL, fontSize: '2.2rem', fontWeight: 700, letterSpacing: '-0.02em' }}>{s.val}</div>
                <div style={{ color: '#94a3b8', fontSize: '0.8rem', marginTop: '0.3rem' }}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ═══ SECTION 1: Pipeline Gap ═══ */}
      <Section id="section-1" number={1} title="The Housing Pipeline Gap" intro="Tens of thousands of homes have planning permission but have never broken ground. Here is where they are." bg={BG_WHITE}>
        {!loaded ? <ChartSkeleton /> : (
          <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: '2rem', alignItems: 'start' }}>
            {/* Funnel */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {[
                { label: 'All Residential', count: funnelMap['all_residential'], color: CHART_BLUE, width: '100%' },
                { label: 'Granted', count: funnelMap['granted'], color: CHART_GREEN, width: '66%' },
                { label: 'Commenced', count: funnelMap['commenced'], color: CHART_TEAL, width: '38%' },
                { label: 'Completed', count: funnelMap['completed'], color: '#0d9488', width: '12%' },
              ].map((s, i) => (
                <div key={i} style={{ textAlign: 'center' }}>
                  <div style={{ background: s.color, color: '#fff', padding: '0.7rem 1rem', borderRadius: 8, width: s.width, margin: '0 auto', fontSize: '0.85rem', fontWeight: 600 }}>
                    {fmtNum(s.count || 0)}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.2rem' }}>{s.label}</div>
                </div>
              ))}
              <p style={{ fontSize: '0.8rem', color: CHART_TEAL, fontWeight: 600, textAlign: 'center', marginTop: '0.5rem' }}>
                Only 1 in 20 residential permissions<br />results in a completed home
              </p>
            </div>
            {/* Bar chart */}
            <ResponsiveContainer width="100%" height={400}>
              <BarChart data={pipelineTop15} layout="vertical" margin={{ left: 10, right: 30 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis type="number" tick={{ fontSize: 12 }} />
                <YAxis dataKey="authority" type="category" width={120} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v: any) => fmtNum(v)} />
                <Bar dataKey="count" fill={CHART_TEAL} radius={[0, 4, 4, 0]} name="Unbuilt Permissions" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Section>

      {/* ═══ SECTION 2: Apartment vs House ═══ */}
      <Section id="section-2" number={2} title="Apartment vs House: A Decade of Permissions" intro="Apartment permissions crashed 39% in 2024 — the steepest fall since the financial crisis. They are recovering but the damage to the pipeline is already done." bg={BG_LIGHT}>
        {!loaded ? <ChartSkeleton /> : (
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={yearData} margin={{ top: 20, right: 30, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="year" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              <ReferenceLine x={2022} stroke="#f59e0b" strokeDasharray="3 3" label={{ value: 'SHD abolished', position: 'top', fontSize: 11, fill: '#f59e0b' }} />
              <Bar dataKey="Apartments" fill={CHART_TEAL} radius={[4, 4, 0, 0]} />
              <Bar dataKey="Houses" fill={CHART_BLUE} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </Section>

      {/* ═══ SECTION 3: Where Ireland Builds ═══ */}
      <Section id="section-3" number={3} title="Where Ireland Builds" intro="A county-by-county map of planning applications per 1,000 people reveals where Ireland is building — and where it isn't." bg={BG_WHITE}>
        {!loaded ? <ChartSkeleton height={500} /> : (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', alignItems: 'start' }}>
            <IrelandMap data={appsPerCapita} valueLabel="Applications per 1,000 people" />
            <div>
              <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#0f172a', margin: '0 0 1rem' }}>Applications Per Capita (per 1,000)</h3>
              {Object.entries(appsPerCapita).sort(([,a],[,b]) => b - a).slice(0, 15).map(([county, val], i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
                  <span style={{ width: 100, fontSize: '0.8rem', color: '#334155' }}>{county}</span>
                  <div style={{ flex: 1, background: '#f1f5f9', borderRadius: 4, height: 18 }}>
                    <div style={{ width: `${Math.min(val / 50 * 100, 100)}%`, background: CHART_TEAL, borderRadius: 4, height: '100%' }} />
                  </div>
                  <span style={{ fontSize: '0.75rem', color: '#64748b', width: 30, textAlign: 'right' }}>{val}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </Section>

      {/* ═══ SECTION 4: Data Centre Republic ═══ */}
      <Section id="section-4" number={4} title="Data Centre Republic" intro={`Ireland hosts ${dataCentres.length} data centre planning applications since 2015 — the overwhelming majority clustered around Dublin.`} bg={BG_WHITE}>
        {!loaded ? <ChartSkeleton /> : (
          <>
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={dcByYear} margin={{ top: 20, right: 30, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="year" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <ReferenceLine x={2022} stroke="#f59e0b" strokeDasharray="3 3" label={{ value: 'EirGrid moratorium', position: 'top', fontSize: 11, fill: '#f59e0b' }} />
                <Bar dataKey="granted" fill={CHART_TEAL} stackId="a" name="Granted" />
                <Bar dataKey="refused" fill={CHART_RED} stackId="a" name="Refused" />
                <Bar dataKey="pending" fill={CHART_GREY} stackId="a" name="Pending" />
              </BarChart>
            </ResponsiveContainer>
            {/* Top 10 data centres table */}
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, margin: '2rem 0 1rem', color: '#0f172a' }}>Top Data Centres by Estimated Value</h3>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid #e2e8f0' }}>
                    {['Ref', 'Location', 'Applicant', 'Value', 'Decision', 'Stage'].map(h => (
                      <th key={h} style={{ padding: '0.6rem 0.8rem', textAlign: 'left', color: '#64748b', fontWeight: 600 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {dataCentres.filter((d: any) => d.est_value_high).slice(0, 10).map((d: any, i: number) => (
                    <tr key={i} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '0.6rem 0.8rem' }}><Link href={`/application/${encodeURIComponent(d.reg_ref)}`} style={{ color: CHART_TEAL, textDecoration: 'none' }}>{d.reg_ref}</Link></td>
                      <td style={{ padding: '0.6rem 0.8rem', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.location || '—'}</td>
                      <td style={{ padding: '0.6rem 0.8rem' }}>{d.applicant_name || '—'}</td>
                      <td style={{ padding: '0.6rem 0.8rem', fontWeight: 600 }}>{formatValue(d.est_value_high)}</td>
                      <td style={{ padding: '0.6rem 0.8rem' }}>{d.decision || '—'}</td>
                      <td style={{ padding: '0.6rem 0.8rem' }}>{d.lifecycle_stage || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Section>

      {/* ═══ SECTION 5: The One-Off House Divide ═══ */}
      <Section id="section-5" number={5} title="The One-Off House Divide" intro="Which councils grant one-off rural houses and which refuse them? The political debate is intense — the data tells a different story." bg={BG_LIGHT}>
        {!loaded ? <ChartSkeleton /> : (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', alignItems: 'start' }}>
            <div>
              <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#0f172a', margin: '0 0 1rem' }}>Grant Rate for Residential by County</h3>
              <ResponsiveContainer width="100%" height={400}>
                <BarChart data={oneOffByCounty.slice(0, 20)} layout="vertical" margin={{ left: 10, right: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} />
                  <YAxis dataKey="county" type="category" width={90} tick={{ fontSize: 10 }} />
                  <Tooltip formatter={(v: any) => `${v}%`} />
                  <Bar dataKey="grant_rate" fill={CHART_GREEN} radius={[0, 4, 4, 0]} name="Grant Rate" />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <IrelandMap data={oneOffMap} valueLabel="Grant Rate" formatValue={(v) => `${v}%`} />
          </div>
        )}
      </Section>

      {/* ═══ SECTION 6: Permission to Construction ═══ */}
      <Section id="section-6" number={6} title="From Permission to Construction: The Reality" intro="Our BCMS data shows exactly what happens between planning permission and construction starting." bg={BG_LIGHT}>
        {!loaded ? <ChartSkeleton /> : (
          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={commencementLag.filter((r: any) => r.months_lag >= 0 && r.months_lag <= 60)} margin={{ top: 20, right: 30, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="months_lag" tick={{ fontSize: 12 }} label={{ value: 'Months from grant to commencement', position: 'bottom', offset: 0, fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip labelFormatter={(v) => `${v} months`} />
              <Bar dataKey="count" fill={CHART_TEAL} radius={[4, 4, 0, 0]} name="Applications" />
            </BarChart>
          </ResponsiveContainer>
        )}
      </Section>

      {/* ═══ SECTION 7: Extensions Boom ═══ */}
      <Section id="section-7" number={7} title="The Extensions Boom" intro="Home extensions are the hidden story of Irish planning. With housing unaffordable, people are extending instead." bg={BG_WHITE}>
        {!loaded ? <ChartSkeleton /> : (
          <ResponsiveContainer width="100%" height={350}>
            <AreaChart data={extByYear} margin={{ top: 20, right: 30, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="year" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Area type="monotone" dataKey="count" stroke={CHART_TEAL} fill={CHART_TEAL} fillOpacity={0.3} name="Extension Applications" />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </Section>

      {/* ═══ SECTION 8: Renewable Energy Frontier ═══ */}
      <Section id="section-8" number={8} title="Renewable Energy Frontier" intro="Ireland has committed to 80% renewable electricity by 2030. Our planning data shows where wind and solar applications are being fought — and where they are winning." bg={BG_WHITE}>
        {!loaded ? <ChartSkeleton /> : (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', alignItems: 'start', marginBottom: '2rem' }}>
              <IrelandMap data={renewableCountMap} valueLabel="Renewable Applications" />
              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#0f172a', margin: '0 0 1rem' }}>Grant Rate by County</h3>
                <ResponsiveContainer width="100%" height={350}>
                  <BarChart data={renewablesByCounty.slice(0, 15)} layout="vertical" margin={{ left: 10, right: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} />
                    <YAxis dataKey="county" type="category" width={90} tick={{ fontSize: 10 }} />
                    <Tooltip formatter={(v: any) => `${v}%`} />
                    <Bar dataKey="grant_rate" fill={CHART_GREEN} radius={[0, 4, 4, 0]} name="Grant Rate" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#0f172a', margin: '0 0 1rem' }}>Renewable Energy Applications Over Time</h3>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={renewablesByYear} margin={{ top: 10, right: 30, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="year" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <ReferenceLine x={2019} stroke="#f59e0b" strokeDasharray="3 3" label={{ value: 'Climate Action Plan', position: 'top', fontSize: 10, fill: '#f59e0b' }} />
                <Line type="monotone" dataKey="count" stroke={CHART_GREEN} strokeWidth={2} dot={{ r: 3 }} name="Applications" />
              </LineChart>
            </ResponsiveContainer>
          </>
        )}
      </Section>

      {/* ═══ SECTION 9: Refusal League Table ═══ */}
      <Section id="section-9" number={9} title="The Refusal League Table" intro="Not all planning authorities are equal. Some councils grant 85% of applications. Others refuse nearly half." bg={BG_LIGHT}>
        {!loaded ? <ChartSkeleton height={600} /> : (
          <>
            <p style={{ fontSize: '0.8rem', color: '#f59e0b', margin: '0 0 1rem', padding: '0.6rem 1rem', background: '#fffbeb', borderRadius: 8, border: '1px solid #fef3c7' }}>
              ⚠️ Refusal rates vary partly due to application mix — councils receiving more complex applications will naturally have higher rates. This chart shows raw data, not adjusted rates.
            </p>
            <ResponsiveContainer width="100%" height={Math.max(refusalByAuthority.length * 22, 500)}>
              <BarChart data={refusalByAuthority} layout="vertical" margin={{ left: 10, right: 30 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis type="number" tick={{ fontSize: 11 }} domain={[0, 50]} unit="%" />
                <YAxis dataKey="authority" type="category" width={140} tick={{ fontSize: 10 }} />
                <Tooltip formatter={(v: any) => `${v}%`} />
                <Bar dataKey="refusal_rate" name="Refusal Rate" radius={[0, 4, 4, 0]}>
                  {refusalByAuthority.map((entry, i) => (
                    <Cell key={i} fill={entry.refusal_rate > 25 ? CHART_RED : entry.refusal_rate > 15 ? '#f59e0b' : CHART_GREEN} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </>
        )}
      </Section>

      {/* ═══ SECTION 10: Construction Value ═══ */}
      <Section id="section-10" number={10} title="Construction Value by County" intro="Where is the construction investment going? Our value estimates reveal the geographic concentration of Ireland's building boom." bg={BG_WHITE}>
        {!loaded ? <ChartSkeleton /> : (
          <>
            <ResponsiveContainer width="100%" height={400}>
              <Treemap data={valueTreemap} dataKey="value" aspectRatio={4/3} stroke="#fff" isAnimationActive={false}>
                {valueTreemap.map((_, i) => (
                  <Cell key={i} fill={TREEMAP_COLORS[i % TREEMAP_COLORS.length]} />
                ))}
                <Tooltip formatter={(v: any) => fmtBn(v)} />
              </Treemap>
            </ResponsiveContainer>
            {/* Top 20 highest value table */}
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, margin: '2.5rem 0 1rem', color: '#0f172a' }}>Highest Value Applications — Last 12 Months</h3>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid #e2e8f0' }}>
                    {['Ref', 'Location', 'Applicant', 'Category', 'Value', 'Stage'].map(h => (
                      <th key={h} style={{ padding: '0.6rem 0.8rem', textAlign: 'left', color: '#64748b', fontWeight: 600 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {topApps.slice(0, 20).map((a: any, i: number) => (
                    <tr key={i} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '0.6rem 0.8rem' }}><Link href={`/application/${encodeURIComponent(a.reg_ref)}`} style={{ color: CHART_TEAL, textDecoration: 'none' }}>{a.reg_ref}</Link></td>
                      <td style={{ padding: '0.6rem 0.8rem', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.location || '—'}</td>
                      <td style={{ padding: '0.6rem 0.8rem' }}>{a.applicant_name || '—'}</td>
                      <td style={{ padding: '0.6rem 0.8rem' }}>{CATEGORY_LABELS[a.dev_category] || a.dev_category || '—'}</td>
                      <td style={{ padding: '0.6rem 0.8rem', fontWeight: 600, color: CHART_TEAL }}>{formatValue(a.est_value_high)}</td>
                      <td style={{ padding: '0.6rem 0.8rem' }}>{a.lifecycle_stage || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Section>

      {/* ═══ FOOTER ═══ */}
      <footer style={{ background: DARK_NAVY, padding: '3rem 1.5rem', textAlign: 'center' }}>
        <p style={{ color: '#64748b', fontSize: '0.85rem', maxWidth: 600, margin: '0 auto', lineHeight: 1.7 }}>
          Data from PlanSearch — Ireland&apos;s national planning intelligence platform.<br />
          All data sourced from public records via NPAD, Cork County ePlan, and OpenDataNI.<br />
          Value estimates based on Mitchell McDermott InfoCard construction cost benchmarks.
        </p>
        <div style={{ marginTop: '1.5rem', display: 'flex', justifyContent: 'center', gap: '1.5rem' }}>
          <Link href="/" style={{ color: '#94a3b8', fontSize: '0.8rem', textDecoration: 'none' }}>Search</Link>
          <Link href="/map" style={{ color: '#94a3b8', fontSize: '0.8rem', textDecoration: 'none' }}>Map</Link>
          <Link href="/blog" style={{ color: '#94a3b8', fontSize: '0.8rem', textDecoration: 'none' }}>Blog</Link>
          <Link href="/pricing" style={{ color: '#94a3b8', fontSize: '0.8rem', textDecoration: 'none' }}>Pricing</Link>
          <Link href="/developer" style={{ color: '#94a3b8', fontSize: '0.8rem', textDecoration: 'none' }}>API</Link>
        </div>
        <p style={{ color: '#475569', fontSize: '0.75rem', marginTop: '1.5rem' }}>© 2026 PlanSearch. All rights reserved.</p>
      </footer>

      <style jsx>{`
        @keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
      `}</style>
    </div>
  );
}

// Wrapper so the error boundary catches crashes from hooks/render inside the inner component
export default function AnalyticsPage() {
  return (
    <ChartErrorBoundary>
      <AnalyticsPageInner />
    </ChartErrorBoundary>
  );
}
