import React, { useState, useEffect, useRef } from 'react';
import { FiSearch, FiShield, FiX, FiChevronDown, FiAlertTriangle } from 'react-icons/fi';
import api from '../api/client';
import './Sanctions.css';

// ── Data ──────────────────────────────────────────────────────────────────────

const ENTITY_TYPES = ['Individual', 'Entity', 'Vessel', 'Aircraft'];

const LISTS = ['OFAC SDN', 'UN Consolidated'];

const PROGRAMS = [
  'BALKANS', 'BELARUS', 'BURMA', 'CAR', 'CUBA', 'CYBER', 'DPRK', 'DPRK2',
  'DPRK3', 'DPRK4', 'DRC', 'DRCONGO', 'EGYPT', 'ETHIOPIA', 'FSE-IR', 'FSE-SY',
  'FTO', 'GLOBAL-MAGNITSKY', 'HIFET', 'HONGKONG-EO13936', 'IFSR', 'IRAN',
  'IRAN-CON-SPRD', 'IRAN-EO13871', 'IRAN-EO13876', 'IRAN-HR', 'IRAN-TRA',
  'IRGC', 'IRAQ2', 'IRAQ3', 'ISIL', 'ISIL-SD', 'KIDA', 'KOSOVO', 'LEBANON',
  'LIBYA', 'LIBYA2', 'MAGNIT', 'MALI', 'MEND', 'MOLDOVA', 'NICARAGUA',
  'NIGERIA', 'NPWMD', 'NS-ISA', 'RUSSIA-EO14024', 'RUSSIA-EO14066',
  'RUSSIA-EO14068', 'RUSSIA-EO14071', 'SDGT', 'SDNTK', 'SOMALIA', 'SOUTH-SUDAN',
  'SUDAN', 'SUDAN2', 'SYRIA', 'SYRIA2', 'SYRIA3', 'TCO', 'TRANSNATIONAL-CRIMINAL-ORG',
  'UKRAINE-EO13685', 'UKRAINE-EO13694', 'VENEZUELA', 'VENEZUELA2', 'WEST-BALKANS',
  'YEMEN', 'ZIMBABWE', 'CYBER2', 'NICARAGUA2', 'CAMEROON', 'HAITI', 'BURMA2',
  'TIGRAY', 'CAR2', 'DRCONGO2', 'IRAQ-SYRIA', 'ETHIOPIA2', 'KENYA', 'LIBYA3',
  'EGYPT2', 'PANAMA', 'CUBA2', 'GLOBAL-MAGNITSKY2', 'RWANDA', 'SENEGAL',
];

const COUNTRIES = [
  'Afghanistan', 'Albania', 'Algeria', 'Andorra', 'Angola', 'Antigua and Barbuda',
  'Argentina', 'Armenia', 'Australia', 'Austria', 'Azerbaijan', 'Bahamas', 'Bahrain',
  'Bangladesh', 'Barbados', 'Belarus', 'Belgium', 'Belize', 'Benin', 'Bhutan',
  'Bolivia', 'Bosnia and Herzegovina', 'Botswana', 'Brazil', 'Brunei', 'Bulgaria',
  'Burkina Faso', 'Burundi', 'Cabo Verde', 'Cambodia', 'Cameroon', 'Canada',
  'Central African Republic', 'Chad', 'Chile', 'China', 'Colombia', 'Comoros',
  'Congo', 'Costa Rica', 'Croatia', 'Cuba', 'Cyprus', 'Czech Republic', 'Denmark',
  'Djibouti', 'Dominica', 'Dominican Republic', 'Ecuador', 'Egypt', 'El Salvador',
  'Equatorial Guinea', 'Eritrea', 'Estonia', 'Eswatini', 'Ethiopia', 'Fiji',
  'Finland', 'France', 'Gabon', 'Gambia', 'Georgia', 'Germany', 'Ghana', 'Greece',
  'Grenada', 'Guatemala', 'Guinea', 'Guinea-Bissau', 'Guyana', 'Haiti', 'Honduras',
  'Hungary', 'Iceland', 'India', 'Indonesia', 'Iran', 'Iraq', 'Ireland', 'Israel',
  'Italy', 'Jamaica', 'Japan', 'Jordan', 'Kazakhstan', 'Kenya', 'Kiribati',
  'Kuwait', 'Kyrgyzstan', 'Laos', 'Latvia', 'Lebanon', 'Lesotho', 'Liberia',
  'Libya', 'Liechtenstein', 'Lithuania', 'Luxembourg', 'Madagascar', 'Malawi',
  'Malaysia', 'Maldives', 'Mali', 'Malta', 'Marshall Islands', 'Mauritania',
  'Mauritius', 'Mexico', 'Micronesia', 'Moldova', 'Monaco', 'Mongolia',
  'Montenegro', 'Morocco', 'Mozambique', 'Myanmar', 'Namibia', 'Nauru', 'Nepal',
  'Netherlands', 'New Zealand', 'Nicaragua', 'Niger', 'Nigeria', 'North Korea',
  'North Macedonia', 'Norway', 'Oman', 'Pakistan', 'Palau', 'Palestine', 'Panama',
  'Papua New Guinea', 'Paraguay', 'Peru', 'Philippines', 'Poland', 'Portugal',
  'Qatar', 'Romania', 'Russia', 'Rwanda', 'Saint Kitts and Nevis', 'Saint Lucia',
  'Saint Vincent and the Grenadines', 'Samoa', 'San Marino', 'Sao Tome and Principe',
  'Saudi Arabia', 'Senegal', 'Serbia', 'Seychelles', 'Sierra Leone', 'Singapore',
  'Slovakia', 'Slovenia', 'Solomon Islands', 'Somalia', 'South Africa', 'South Korea',
  'South Sudan', 'Spain', 'Sri Lanka', 'Sudan', 'Suriname', 'Sweden', 'Switzerland',
  'Syria', 'Taiwan', 'Tajikistan', 'Tanzania', 'Thailand', 'Timor-Leste', 'Togo',
  'Tonga', 'Trinidad and Tobago', 'Tunisia', 'Turkey', 'Turkmenistan', 'Tuvalu',
  'Uganda', 'Ukraine', 'United Arab Emirates', 'United Kingdom', 'United States',
  'Uruguay', 'Uzbekistan', 'Vanuatu', 'Vatican City', 'Venezuela', 'Vietnam',
  'Yemen', 'Zambia', 'Zimbabwe',
];

const EMPTY_FORM = {
  name: '',
  entity_type: '',
  program: '',
  country: '',
  list_name: '',
  min_score: 70,
  max_results: 25,
};

// ── SearchableSelect ──────────────────────────────────────────────────────────

function SearchableSelect({
  value,
  onChange,
  options,
  placeholder = 'Select…',
  allLabel = 'All',
  searchPlaceholder = 'Search…',
  footerSuffix = 'options',
  alignRight = false,
}) {
  const [open, setOpen]     = useState(false);
  const [query, setQuery]   = useState('');
  const wrapRef             = useRef(null);

  const filtered = options.filter(o =>
    o.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    const handler = e => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setOpen(false);
        setQuery('');
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const select = v => {
    onChange(v);
    setOpen(false);
    setQuery('');
  };

  return (
    <div className="prog-wrap" ref={wrapRef}>
      <div
        className={`input-base prog-trigger${open ? ' prog-open' : ''}`}
        onClick={() => setOpen(o => !o)}
        tabIndex={0}
        onKeyDown={e => e.key === 'Enter' && setOpen(o => !o)}
      >
        {value
          ? <span className="prog-value">{value}</span>
          : <span className="prog-placeholder">{placeholder}</span>
        }
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {value && (
            <span
              className="prog-clear"
              onClick={e => { e.stopPropagation(); onChange(''); }}
            >
              <FiX size={12} />
            </span>
          )}
          <span className={`prog-arrow${open ? ' prog-arrow-up' : ''}`}>
            <FiChevronDown size={14} />
          </span>
        </span>
      </div>

      {open && (
        <div className={`prog-dropdown${alignRight ? ' prog-dropdown-right' : ''}`}>
          <div className="prog-search-wrap">
            <FiSearch size={13} className="prog-search-icon" />
            <input
              className="prog-search-input"
              placeholder={searchPlaceholder}
              value={query}
              onChange={e => setQuery(e.target.value)}
              autoFocus
            />
            {query && (
              <span className="prog-search-clear" onClick={() => setQuery('')}>
                <FiX size={12} />
              </span>
            )}
          </div>
          <div className="prog-list">
            <div
              className={`prog-option prog-option-all${!value ? ' prog-option-active' : ''}`}
              onClick={() => select('')}
            >
              {allLabel}
            </div>
            {filtered.length === 0
              ? <div className="prog-empty">No results for "{query}"</div>
              : filtered.map(opt => (
                  <div
                    key={opt}
                    className={`prog-option${value === opt ? ' prog-option-active' : ''}`}
                    onClick={() => select(opt)}
                  >
                    {opt}
                  </div>
                ))
            }
          </div>
          <div className="prog-footer">
            {filtered.length} of {options.length} {footerSuffix}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Score helpers ─────────────────────────────────────────────────────────────

function scoreStyle(score) {
  if (score >= 100) return { bg: 'rgba(239,68,68,0.12)',  color: '#EF4444', label: 'EXACT MATCH' };
  if (score >= 85)  return { bg: 'rgba(240,165,0,0.12)', color: '#F0A500', label: 'STRONG' };
  if (score >= 70)  return { bg: 'rgba(59,130,246,0.12)', color: '#3B82F6', label: 'POSSIBLE' };
  return              { bg: 'rgba(34,197,94,0.12)',  color: '#22C55E', label: 'WEAK' };
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function Sanctions() {
  const [form, setForm]         = useState(EMPTY_FORM);
  const [results, setResults]   = useState([]);
  const [stats, setStats]       = useState(null);
  const [loading, setLoading]   = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError]       = useState('');

  useEffect(() => {
    api.get('/sanctions/stats')
      .then(r => setStats(r.data))
      .catch(() => {});
  }, []);

  const handleSearch = async e => {
    e.preventDefault();
    if (!form.name.trim()) { setError('Please enter a name to search.'); return; }
    setError('');
    setLoading(true);
    setSearched(false);
    try {
      const payload = {
        name:        form.name.trim(),
        entity_type: form.entity_type  || undefined,
        program:     form.program      || undefined,
        country:     form.country      || undefined,
        list_name:   form.list_name    || undefined,
        min_score:   form.min_score,
        max_results: form.max_results,
      };
      const res = await api.post('/sanctions/search', payload);
      setResults(res.data.results || res.data || []);
      setSearched(true);
    } catch (err) {
      setError(err.response?.data?.detail || 'Search failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setForm(EMPTY_FORM);
    setResults([]);
    setSearched(false);
    setError('');
  };

  const field = (key, val) => setForm(f => ({ ...f, [key]: val }));

  return (
    <div className="sanctions-page">
      {/* ── Stats Bar ── */}
      {stats && (
        <div className="sanctions-stats-bar">
          <div className="sanctions-stat">
            <div className="sanctions-stat-val">{(stats.total_entries || 0).toLocaleString()}</div>
            <div className="sanctions-stat-lbl">Total Entries</div>
          </div>
          <div className="sanctions-stat">
            <div className="sanctions-stat-val">{(stats.total_aliases || 0).toLocaleString()}</div>
            <div className="sanctions-stat-lbl">Total Aliases</div>
          </div>
          <div className="sanctions-stat">
            <div className="sanctions-stat-val">
              {(
                stats.ofac_entries ||
                stats.by_list?.['SDN'] ||
                stats.by_list?.['OFAC SDN'] ||
                stats.by_list?.['ofac_sdn'] ||
                Object.entries(stats.by_list || {}).find(([k]) => k.toLowerCase().includes('sdn'))?.[1] ||
                0
              ).toLocaleString()}
            </div>
            <div className="sanctions-stat-lbl">OFAC SDN</div>
          </div>
          <div className="sanctions-stat">
            <div className="sanctions-stat-val">
              {(
                stats.un_entries ||
                stats.by_list?.['UN'] ||
                stats.by_list?.['UN Consolidated'] ||
                stats.by_list?.['un_consolidated'] ||
                Object.entries(stats.by_list || {}).find(([k]) => k.toLowerCase().includes('un'))?.[1] ||
                0
              ).toLocaleString()}
            </div>
            <div className="sanctions-stat-lbl">UN Consolidated</div>
          </div>
          <div className="sanctions-stat">
            <div className="sanctions-stat-val">{stats.programs_count || 86}</div>
            <div className="sanctions-stat-lbl">Programs</div>
          </div>
          <div className="sanctions-stat">
            <div className="sanctions-stat-val">{stats.countries_count || 196}</div>
            <div className="sanctions-stat-lbl">Countries</div>
          </div>
        </div>
      )}

      {/* ── Search Card ── */}
      <div className="card">
        <div className="sanctions-search-header">
          <div className="sanctions-search-icon">
            <FiShield size={20} />
          </div>
          <div>
            <h2>OFAC SDN &amp; UN Sanctions Screening</h2>
            <p>Search against OFAC Specially Designated Nationals and UN Consolidated Sanctions lists.</p>
          </div>
        </div>

        <form onSubmit={handleSearch} className="sf-form">

          {/* ── Row 1: Full Name · Sanctions List · Entity Type ── */}
          <div className="sf-row sf-row-3col">
            <div className="sf-field sf-field-wide">
              <label className="sf-label">Full Name <span className="sf-required">*</span></label>
              <input
                className="sf-input"
                placeholder="e.g. Osama Bin Laden"
                value={form.name}
                onChange={e => field('name', e.target.value)}
              />
            </div>
            <div className="sf-field">
              <label className="sf-label">Sanctions List</label>
              <SearchableSelect
                value={form.list_name}
                onChange={v => field('list_name', v)}
                options={LISTS}
                placeholder="All Lists"
                allLabel="All Lists"
                searchPlaceholder="Search lists…"
                footerSuffix="lists"
              />
            </div>
            <div className="sf-field">
              <label className="sf-label">Entity Type</label>
              <SearchableSelect
                value={form.entity_type}
                onChange={v => field('entity_type', v)}
                options={ENTITY_TYPES}
                placeholder="All Types"
                allLabel="All Types"
                searchPlaceholder="Search types…"
                footerSuffix="types"
                alignRight
              />
            </div>
          </div>

          {/* ── Row 2: Sanctions Program · Country ── */}
          <div className="sf-row sf-row-2col">
            <div className="sf-field">
              <label className="sf-label">Sanctions Program</label>
              <SearchableSelect
                value={form.program}
                onChange={v => field('program', v)}
                options={PROGRAMS}
                placeholder="All Programs"
                allLabel="All Programs"
                searchPlaceholder="Search programs…"
                footerSuffix="programs"
              />
            </div>
            <div className="sf-field">
              <label className="sf-label">Country</label>
              <SearchableSelect
                value={form.country}
                onChange={v => field('country', v)}
                options={COUNTRIES}
                placeholder="All Countries"
                allLabel="All Countries"
                searchPlaceholder="Search countries…"
                footerSuffix="countries"
                alignRight
              />
            </div>
          </div>

          {/* ── Row 3: Score slider · Max Results · Buttons ── */}
          <div className="sf-row sf-row-bottom">
            {/* Slider */}
            <div className="sf-slider-block">
              <div className="sf-slider-top">
                <label className="sf-label" style={{ marginBottom: 0 }}>Min Match Score</label>
                <div className="sf-tier-badges">
                  {[
                    { label: 'WEAK',     color: '#22C55E', min: 50, max: 69  },
                    { label: 'POSSIBLE', color: '#3B82F6', min: 70, max: 84  },
                    { label: 'STRONG',   color: '#F0A500', min: 85, max: 99  },
                    { label: 'EXACT',    color: '#EF4444', min: 100, max: 100 },
                  ].map(b => {
                    const active = form.min_score >= b.min && form.min_score <= b.max;
                    return (
                      <span
                        key={b.label}
                        className={`sf-tier${active ? ' sf-tier-on' : ''}`}
                        style={{ '--tc': b.color }}
                        onClick={() => field('min_score', b.min)}
                        title={`Set threshold to ${b.min}`}
                      >{b.label}</span>
                    );
                  })}
                  <strong className="sf-score-num">{form.min_score}</strong>
                </div>
              </div>
              <input
                type="range" className="sf-range"
                min={50} max={100} step={5}
                value={form.min_score}
                onChange={e => field('min_score', Number(e.target.value))}
              />
              <div className="sf-range-marks">
                {[50,60,70,80,85,90,100].map(n => <span key={n}>{n}</span>)}
              </div>
            </div>

            {/* Max Results */}
            <div className="sf-field sf-field-sm">
              <label className="sf-label">Max Results</label>
              <select
                className="sf-select"
                value={form.max_results}
                onChange={e => field('max_results', Number(e.target.value))}
              >
                {[10, 25, 50, 100].map(n => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </div>

            {/* Buttons */}
            <div className="sf-actions">
              <button type="submit" className="sf-btn-primary" disabled={loading}>
                {loading
                  ? <><span className="sf-spinner" /> Searching…</>
                  : <><FiSearch size={14} /> Search</>}
              </button>
              <button type="button" className="sf-btn-ghost" onClick={handleReset}>
                <FiX size={14} /> Reset
              </button>
            </div>
          </div>

        </form>

        {error && (
          <div className="alert alert-error" style={{ marginTop: 12 }}>
            <FiAlertTriangle size={14} style={{ marginRight: 6 }} />{error}
          </div>
        )}

      </div>

      {/* ── Results ── */}
      {searched && (
        <div className="sanctions-results">
          <div className="sanctions-results-header">
            <div>
              <h3>
                {results.length === 0
                  ? 'No matches found'
                  : `${results.length} result${results.length !== 1 ? 's' : ''} found`}
              </h3>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                {results.length > 0
                  ? `Showing top ${results.length} matches for "${form.name}" with score ≥ ${form.min_score}`
                  : `No sanctions matches found for "${form.name}" above the minimum score threshold.`}
              </p>
            </div>
            {results.length > 0 && (
              <span className="badge badge-warning" style={{ fontSize: 12, padding: '4px 10px' }}>
                {results.filter(r => r.score >= 85).length} HIGH CONFIDENCE
              </span>
            )}
          </div>

          {results.map((r, i) => {
            const ss = scoreStyle(r.score);
            const programs = (() => {
              try { return JSON.parse(r.programs || '[]'); }
              catch { return r.programs ? [r.programs] : []; }
            })();

            return (
              <div key={i} className="sanctions-result-card">
                <div className="sanctions-result-header">
                  <div className="sanctions-result-name">
                    <div>
                      <div className="sanctions-primary-name">{r.primary_name || r.name}</div>
                      {r.matched_alias && r.matched_alias !== r.primary_name && (
                        <div className="sanctions-matched-name">
                          Matched on: <em>"{r.matched_alias}"</em>
                          {r.alias_type && (
                            <span className="alias-type-tag">{r.alias_type}</span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="sanctions-score-block" style={{ background: ss.bg }}>
                    <div className="sanctions-score" style={{ color: ss.color }}>{r.score}</div>
                    <div className="sanctions-score-label" style={{ color: ss.color }}>{ss.label}</div>
                  </div>
                </div>

                <div className="sanctions-result-meta">
                  <div className="sanctions-meta-item">
                    <span>List</span>
                    <span>{r.list_name || '—'}</span>
                  </div>
                  <div className="sanctions-meta-item">
                    <span>Type</span>
                    <span>{r.entity_type || '—'}</span>
                  </div>
                  <div className="sanctions-meta-item">
                    <span>Nationality</span>
                    <span>{r.nationality || r.country || '—'}</span>
                  </div>
                  <div className="sanctions-meta-item">
                    <span>DOB</span>
                    <span>{r.date_of_birth || '—'}</span>
                  </div>
                </div>

                {programs.length > 0 && (
                  <div style={{ marginBottom: 10 }}>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 700, marginBottom: 5 }}>
                      Programs
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                      {programs.map((p, pi) => (
                        <span key={pi} style={{
                          padding: '2px 7px',
                          background: 'rgba(240,165,0,0.08)',
                          border: '1px solid rgba(240,165,0,0.18)',
                          borderRadius: 4,
                          fontSize: 11,
                          color: '#F0A500',
                          fontWeight: 600,
                        }}>{p}</span>
                      ))}
                    </div>
                  </div>
                )}

                {r.aliases && r.aliases.length > 0 && (
                  <div>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 700, marginBottom: 5 }}>
                      Aliases
                    </div>
                    <div className="sanctions-aliases">
                      {r.aliases.slice(0, 12).map((a, ai) => (
                        <span
                          key={ai}
                          className={`sanctions-alias-tag${a.is_primary ? ' primary' : ''}`}
                        >
                          {a.alias_name || a.name || String(a)}
                          {a.alias_type && <em> ({a.alias_type})</em>}
                        </span>
                      ))}
                      {r.aliases.length > 12 && (
                        <span className="sanctions-alias-tag">
                          +{r.aliases.length - 12} more
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
