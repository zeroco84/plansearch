'use client';

import { useState, useEffect, useMemo } from 'react';
import {
  ComposableMap,
  Geographies,
  Geography,
  ZoomableGroup,
} from 'react-simple-maps';

const GEO_URL = '/data/ireland-counties.json';

// Teal colour scale (5 stops)
const COLOR_SCALE = [
  '#e0f7fa', // lightest
  '#80cbc4',
  '#26a69a',
  '#00897b',
  '#004d40', // darkest
];
const NO_DATA_COLOR = '#e2e8f0';

function getQuantileColor(value: number, min: number, max: number): string {
  if (max === min) return COLOR_SCALE[2];
  const t = (value - min) / (max - min);
  const idx = Math.min(Math.floor(t * COLOR_SCALE.length), COLOR_SCALE.length - 1);
  return COLOR_SCALE[idx];
}

interface IrelandMapProps {
  /** Map from county name → numeric value */
  data: Record<string, number>;
  /** Label for the value in the tooltip, e.g. "Applications" */
  valueLabel?: string;
  /** Format function for the value, e.g. (v) => `${v}%` */
  formatValue?: (v: number) => string;
  /** Height of the map container */
  height?: number;
}

export default function IrelandMap({
  data,
  valueLabel = 'Value',
  formatValue: fmtValue = (v) => v.toLocaleString('en-IE'),
  height = 500,
}: IrelandMapProps) {
  const [tooltip, setTooltip] = useState<{ name: string; value: number; x: number; y: number } | null>(null);

  const { min, max } = useMemo(() => {
    const values = Object.values(data).filter((v) => v > 0);
    return {
      min: values.length > 0 ? Math.min(...values) : 0,
      max: values.length > 0 ? Math.max(...values) : 1,
    };
  }, [data]);

  return (
    <div style={{ position: 'relative', width: '100%', maxWidth: 500, margin: '0 auto' }}>
      <ComposableMap
        projection="geoMercator"
        projectionConfig={{
          center: [-7.5, 53.5],
          scale: 4500,
        }}
        width={400}
        height={height}
        style={{ width: '100%', height: 'auto' }}
      >
        <Geographies geography={GEO_URL}>
          {({ geographies }: { geographies: any[] }) =>
            geographies.map((geo: any) => {
              const name = geo.properties.name;
              const value = data[name];
              const fillColor =
                value !== undefined && value > 0
                  ? getQuantileColor(value, min, max)
                  : NO_DATA_COLOR;

              return (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  fill={fillColor}
                  stroke="#fff"
                  strokeWidth={0.5}
                  style={{
                    default: { outline: 'none' },
                    hover: { outline: 'none', fill: '#14b8a6', cursor: 'pointer' },
                    pressed: { outline: 'none' },
                  }}
                  onMouseEnter={(evt: React.MouseEvent) => {
                    setTooltip({
                      name,
                      value: value ?? 0,
                      x: evt.clientX,
                      y: evt.clientY,
                    });
                  }}
                  onMouseLeave={() => setTooltip(null)}
                />
              );
            })
          }
        </Geographies>
      </ComposableMap>

      {/* Tooltip */}
      {tooltip && (
        <div
          style={{
            position: 'fixed',
            left: tooltip.x + 12,
            top: tooltip.y - 40,
            background: '#0f172a',
            color: '#fff',
            padding: '0.5rem 0.75rem',
            borderRadius: 8,
            fontSize: '0.8rem',
            pointerEvents: 'none',
            zIndex: 100,
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
            whiteSpace: 'nowrap',
          }}
        >
          <div style={{ fontWeight: 600 }}>{tooltip.name}</div>
          <div>
            {valueLabel}: {fmtValue(tooltip.value)}
          </div>
        </div>
      )}

      {/* Legend */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.25rem', marginTop: '0.5rem' }}>
        <span style={{ fontSize: '0.7rem', color: '#64748b' }}>Low</span>
        {COLOR_SCALE.map((c, i) => (
          <div key={i} style={{ width: 24, height: 12, background: c, borderRadius: 2 }} />
        ))}
        <span style={{ fontSize: '0.7rem', color: '#64748b' }}>High</span>
      </div>
    </div>
  );
}
