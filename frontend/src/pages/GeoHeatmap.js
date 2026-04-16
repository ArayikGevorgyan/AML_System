import React, { useState, useEffect } from 'react';
import { ComposableMap, Geographies, Geography, ZoomableGroup } from 'react-simple-maps';
import { scaleLinear } from 'd3-scale';
import { MdRefresh, MdPublic, MdZoomIn, MdZoomOut } from 'react-icons/md';
import client from '../api/client';

const GEO_URL = 'https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json';

// ISO numeric → ISO alpha-2 mapping (subset covering seeded countries)
const NUMERIC_TO_ALPHA2 = {
  840: 'US', 826: 'GB', 276: 'DE', 250: 'FR', 364: 'IR', 408: 'KP',
  760: 'SY', 643: 'RU', 156: 'CN', 392: 'JP', 36: 'AU', 124: 'CA',
  484: 'MX', 76: 'BR', 566: 'NG', 710: 'ZA', 784: 'AE', 682: 'SA',
  356: 'IN', 586: 'PK', 4: 'AF', 368: 'IQ', 434: 'LY', 736: 'SD',
  112: 'BY', 804: 'UA', 616: 'PL', 380: 'IT', 724: 'ES', 528: 'NL',
  756: 'CH', 752: 'SE', 578: 'NO', 208: 'DK', 246: 'FI', 376: 'IL',
  792: 'TR', 818: 'EG', 504: 'MA', 404: 'KE', 170: 'CO', 862: 'VE',
  32: 'AR', 152: 'CL', 410: 'KR', 764: 'TH', 702: 'SG', 458: 'MY',
  360: 'ID', 608: 'PH', 704: 'VN', 50: 'BD',
};

const COUNTRY_NAMES = {
  US: 'United States', GB: 'United Kingdom', DE: 'Germany', FR: 'France',
  IR: 'Iran', KP: 'North Korea', SY: 'Syria', RU: 'Russia',
  CN: 'China', JP: 'Japan', AU: 'Australia', CA: 'Canada',
  MX: 'Mexico', BR: 'Brazil', NG: 'Nigeria', ZA: 'South Africa',
  AE: 'UAE', SA: 'Saudi Arabia', IN: 'India', PK: 'Pakistan',
  AF: 'Afghanistan', IQ: 'Iraq', LY: 'Libya', SD: 'Sudan',
  BY: 'Belarus', UA: 'Ukraine', PL: 'Poland', IT: 'Italy',
  ES: 'Spain', NL: 'Netherlands', CH: 'Switzerland', SE: 'Sweden',
  NO: 'Norway', DK: 'Denmark', FI: 'Finland', IL: 'Israel',
  TR: 'Turkey', EG: 'Egypt', MA: 'Morocco', KE: 'Kenya',
  CO: 'Colombia', VE: 'Venezuela', AR: 'Argentina', CL: 'Chile',
  KR: 'South Korea', TH: 'Thailand', SG: 'Singapore', MY: 'Malaysia',
  ID: 'Indonesia', PH: 'Philippines', VN: 'Vietnam', BD: 'Bangladesh',
};

const HIGH_RISK = new Set(['IR', 'KP', 'SY', 'SD', 'LY', 'AF', 'IQ', 'BY']);

const normalScale = scaleLinear().domain([0, 1]).range(['#064E3B', '#10B981']);
const highRiskScale = scaleLinear().domain([0, 1]).range(['#7F1D1D', '#F87171']);

export default function GeoHeatmap() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tooltip, setTooltip] = useState(null);
  const [zoom, setZoom] = useState(1);

  const load = async () => {
    setLoading(true);
    try {
      const res = await client.get('/transactions/by-country');
      setData(res.data.sort((a, b) => b.count - a.count));
    } catch (e) { } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const countryMap = {};
  data.forEach(d => { countryMap[d.country] = d; });
  const maxCount = data.length ? Math.max(...data.map(d => d.count)) : 1;

  const getFill = (alpha2) => {
    const d = countryMap[alpha2];
    if (!d) return 'var(--bg-hover)';
    const intensity = d.count / maxCount;
    return HIGH_RISK.has(alpha2) ? highRiskScale(intensity) : normalScale(intensity);
  };

  const totalVolume = data.reduce((s, d) => s + d.volume, 0);
  const totalCount = data.reduce((s, d) => s + d.count, 0);
  const totalFlagged = data.reduce((s, d) => s + d.flagged_count, 0);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h2 className="page-title" style={{ marginBottom: 0 }}>Geographic Risk Heatmap</h2>
        <button className="btn btn-secondary" onClick={load}><MdRefresh size={16} /> Refresh</button>
      </div>

      {/* KPI row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 16, marginBottom: 20 }}>
        {[
          { label: 'Total Transactions', value: totalCount },
          { label: 'Total Volume', value: `$${totalVolume.toLocaleString('en', { maximumFractionDigits: 0 })}` },
          { label: 'Flagged Transactions', value: totalFlagged },
        ].map(kpi => (
          <div key={kpi.label} className="card" style={{ textAlign: 'center', padding: 20 }}>
            <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--text-primary)' }}>{kpi.value}</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{kpi.label}</div>
          </div>
        ))}
      </div>

      {/* Map */}
      <div className="card" style={{ padding: 16, marginBottom: 20, position: 'relative' }}>
        {/* Legend */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 20, marginBottom: 12, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
            <div style={{ width: 12, height: 12, borderRadius: 3, background: '#10B981' }} />
            <span style={{ color: 'var(--text-subtle)' }}>Normal (darker = more volume)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
            <div style={{ width: 12, height: 12, borderRadius: 3, background: '#F87171' }} />
            <span style={{ color: 'var(--text-subtle)' }}>High-risk country</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
            <div style={{ width: 12, height: 12, borderRadius: 3, background: 'var(--bg-hover)', border: '1px solid var(--border)' }} />
            <span style={{ color: 'var(--text-subtle)' }}>No transactions</span>
          </div>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            <button className="btn btn-secondary" style={{ padding: '4px 8px' }} onClick={() => setZoom(z => Math.min(z + 0.5, 5))}><MdZoomIn size={16} /></button>
            <button className="btn btn-secondary" style={{ padding: '4px 8px' }} onClick={() => setZoom(z => Math.max(z - 0.5, 1))}><MdZoomOut size={16} /></button>
          </div>
        </div>

        <div style={{ background: 'var(--bg-primary)', borderRadius: 8, overflow: 'hidden', position: 'relative' }}>
          {loading && (
            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.3)', zIndex: 10, borderRadius: 8 }}>
              <span style={{ color: 'var(--text-primary)' }}>Loading...</span>
            </div>
          )}
          <ComposableMap
            projection="geoMercator"
            style={{ width: '100%', height: '780px' }}
            projectionConfig={{ scale: 165, center: [10, 20] }}
          >
            <ZoomableGroup zoom={zoom} minZoom={1} maxZoom={8} filterZoomEvent={evt => evt.type !== 'wheel' || evt.ctrlKey}>
              <Geographies geography={GEO_URL}>
                {({ geographies }) =>
                  geographies.map(geo => {
                    const numericId = parseInt(geo.id, 10);
                    const alpha2 = NUMERIC_TO_ALPHA2[numericId];
                    const d = alpha2 ? countryMap[alpha2] : null;
                    return (
                      <Geography
                        key={geo.rsmKey}
                        geography={geo}
                        fill={getFill(alpha2)}
                        stroke="var(--border)"
                        strokeWidth={0.3}
                        style={{
                          default: { outline: 'none' },
                          hover: { outline: 'none', fill: alpha2 && d ? (HIGH_RISK.has(alpha2) ? '#FCA5A5' : '#34D399') : 'var(--border-light)', cursor: d ? 'pointer' : 'default' },
                          pressed: { outline: 'none' },
                        }}
                        onMouseEnter={(e) => {
                          if (!d) return;
                          setTooltip({
                            x: e.clientX,
                            y: e.clientY,
                            name: COUNTRY_NAMES[alpha2] || alpha2,
                            alpha2,
                            count: d.count,
                            volume: d.volume,
                            flagged: d.flagged_count,
                            flagRate: ((d.flagged_count / d.count) * 100).toFixed(1),
                            isHighRisk: HIGH_RISK.has(alpha2),
                          });
                        }}
                        onMouseMove={(e) => {
                          if (tooltip) setTooltip(t => t ? { ...t, x: e.clientX, y: e.clientY } : null);
                        }}
                        onMouseLeave={() => setTooltip(null)}
                      />
                    );
                  })
                }
              </Geographies>
            </ZoomableGroup>
          </ComposableMap>
        </div>

        {/* Tooltip */}
        {tooltip && (
          <div style={{
            position: 'fixed',
            left: tooltip.x + 14,
            top: tooltip.y - 10,
            background: 'var(--bg-card)',
            border: `1px solid ${tooltip.isHighRisk ? '#F87171' : 'var(--border)'}`,
            borderRadius: 8,
            padding: '10px 14px',
            pointerEvents: 'none',
            zIndex: 9999,
            minWidth: 180,
            boxShadow: 'var(--shadow)',
          }}>
            <div style={{ fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6 }}>
              {tooltip.isHighRisk && <span style={{ color: '#F87171', fontSize: 10, fontWeight: 700, marginRight: 6 }}>⚠ HIGH RISK</span>}
              {tooltip.name} <span style={{ color: 'var(--text-muted)', fontWeight: 400, fontSize: 11 }}>({tooltip.alpha2})</span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-subtle)', lineHeight: 1.8 }}>
              <div>Transactions: <strong style={{ color: 'var(--text-primary)' }}>{tooltip.count}</strong></div>
              <div>Volume: <strong style={{ color: 'var(--text-primary)' }}>${tooltip.volume.toLocaleString('en', { maximumFractionDigits: 0 })}</strong></div>
              <div>Flagged: <strong style={{ color: tooltip.flagged > 0 ? '#F97316' : 'var(--text-primary)' }}>{tooltip.flagged}</strong></div>
              <div>Flag Rate: <strong style={{ color: parseFloat(tooltip.flagRate) > 20 ? '#F87171' : 'var(--text-primary)' }}>{tooltip.flagRate}%</strong></div>
            </div>
          </div>
        )}
      </div>

      {/* Country details table */}
      <div className="card">
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Country Details</h3>
        <div className="table-container">
          <table>
            <thead>
              <tr><th>Country</th><th>Transactions</th><th>Volume</th><th>Flagged</th><th>Flag Rate</th><th>Risk</th></tr>
            </thead>
            <tbody>
              {data.map(d => (
                <tr key={d.country}>
                  <td><strong>{COUNTRY_NAMES[d.country] || d.country}</strong> <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>({d.country})</span></td>
                  <td>{d.count}</td>
                  <td>${d.volume.toLocaleString('en', { maximumFractionDigits: 0 })}</td>
                  <td>{d.flagged_count}</td>
                  <td>{d.count > 0 ? ((d.flagged_count / d.count) * 100).toFixed(1) : 0}%</td>
                  <td>{HIGH_RISK.has(d.country) ? <span className="badge badge-high">HIGH RISK</span> : <span className="badge badge-low">NORMAL</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
