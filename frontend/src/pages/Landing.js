import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../context/ThemeContext';
import { MdLightMode, MdDarkMode } from 'react-icons/md';
import {
  MdSecurity, MdSearch, MdNotifications, MdFolder,
  MdBarChart, MdPublic, MdPeople, MdVerifiedUser,
  MdArrowForward, MdShield, MdSpeed, MdLock,
  MdEmail, MdPhone, MdBusiness, MdChat, MdClose, MdSend,
} from 'react-icons/md';
import { chatAPI } from '../api/client';
import './Landing.css';

const FEATURES = [
  { icon: MdNotifications, title: 'Real-Time Alert Engine',     desc: '8+ AML detection rules running on every transaction — structuring, layering, smurfing, velocity, and more.' },
  { icon: MdSearch,        title: 'OFAC Sanctions Screening',   desc: 'Fuzzy-match names against the full OFAC SDN list using Jaro-Winkler + Soundex composite scoring.' },
  { icon: MdFolder,        title: 'Case Management',            desc: 'Open, assign, escalate, and close investigation cases with a full audit trail on every action.' },
  { icon: MdBarChart,      title: 'Compliance Dashboard',       desc: 'Live KPI cards, 30-day trend charts, alert severity breakdown, and top triggered rules.' },
  { icon: MdPublic,        title: 'Geographic Risk Heatmap',    desc: 'Visualise transaction volume and flag rates by country to identify high-risk corridors instantly.' },
  { icon: MdPeople,        title: 'Role-Based Access Control',  desc: 'Three roles — Admin, Analyst, Supervisor — each with tailored permissions and views.' },
  { icon: MdVerifiedUser,  title: 'Audit Logging',              desc: 'Every user action is timestamped and stored. Full compliance trail for regulators and auditors.' },
  { icon: MdLock,          title: 'Session Management',         desc: 'Admins can view all active sessions and force-logout any suspicious device instantly.' },
];

const STATS = [
  { value: '8+',   label: 'AML Detection Rules' },
  { value: '3',    label: 'User Roles' },
  { value: '40+',  label: 'Countries Monitored' },
  { value: '100%', label: 'Audit Coverage' },
];

function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hi! I\'m the AML Monitor assistant. Ask me anything about AML compliance, how the platform works, or what suspicious patterns to look for.' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    if (open) bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, open]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    const history = messages.map(m => ({ role: m.role, content: m.content }));
    const next = [...messages, { role: 'user', content: text }];
    setMessages(next);
    setInput('');
    setLoading(true);
    try {
      const r = await chatAPI.send(text, history);
      setMessages(prev => [...prev, { role: 'assistant', content: r.data.reply }]);
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, I\'m having trouble connecting. Please try again.' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ position: 'fixed', bottom: 28, right: 28, zIndex: 9999 }}>
      {open && (
        <div style={{
          width: 400, height: 560, background: 'var(--bg-card)', border: '1px solid var(--border)',
          borderRadius: 16, boxShadow: '0 8px 40px rgba(0,0,0,0.18)', display: 'flex',
          flexDirection: 'column', marginBottom: 14, overflow: 'hidden',
        }}>
          <div style={{
            padding: '14px 18px', background: 'linear-gradient(135deg, #3D7A98, #2A5A72)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'rgba(255,255,255,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <MdChat size={17} color="#fff" />
              </div>
              <div>
                <div style={{ color: '#fff', fontWeight: 600, fontSize: 14 }}>AML Assistant</div>
                <div style={{ color: 'rgba(255,255,255,0.7)', fontSize: 11 }}>Ask me anything</div>
              </div>
            </div>
            <button onClick={() => setOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.8)', padding: 4 }}>
              <MdClose size={18} />
            </button>
          </div>

          <div style={{ flex: 1, overflowY: 'auto', padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
            {messages.map((m, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start' }}>
                <div style={{
                  maxWidth: '82%', padding: '9px 13px', borderRadius: m.role === 'user' ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
                  background: m.role === 'user' ? 'linear-gradient(135deg, #3D7A98, #2A5A72)' : 'var(--bg-hover)',
                  color: m.role === 'user' ? '#fff' : 'var(--text-primary)',
                  fontSize: 13, lineHeight: 1.5,
                }}>
                  {m.content}
                </div>
              </div>
            ))}
            {loading && (
              <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                <div style={{ padding: '9px 14px', background: 'var(--bg-hover)', borderRadius: '14px 14px 14px 4px', fontSize: 13, color: 'var(--text-muted)' }}>
                  Thinking...
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div style={{ padding: '10px 12px', borderTop: '1px solid var(--border)', display: 'flex', gap: 8 }}>
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && send()}
              placeholder="Ask about AML..."
              style={{
                flex: 1, padding: '9px 13px', borderRadius: 20, border: '1px solid var(--border)',
                background: 'var(--bg-input)', color: 'var(--text-primary)', fontSize: 13, outline: 'none',
              }}
            />
            <button onClick={send} disabled={!input.trim() || loading} style={{
              width: 36, height: 36, borderRadius: '50%', border: 'none', cursor: 'pointer',
              background: input.trim() ? 'linear-gradient(135deg, #3D7A98, #2A5A72)' : 'var(--bg-hover)',
              color: input.trim() ? '#fff' : 'var(--text-muted)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
              transition: 'background 0.2s',
            }}>
              <MdSend size={16} />
            </button>
          </div>
        </div>
      )}

      <button onClick={() => setOpen(o => !o)} style={{
        width: 52, height: 52, borderRadius: '50%', border: 'none', cursor: 'pointer',
        background: 'linear-gradient(135deg, #3D7A98, #2A5A72)',
        boxShadow: '0 4px 20px rgba(61,122,152,0.45)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        transition: 'transform 0.2s',
      }}>
        {open ? <MdClose size={22} color="#fff" /> : <MdChat size={22} color="#fff" />}
      </button>
    </div>
  );
}

export default function Landing() {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const [demoForm, setDemoForm]       = useState({ institution: '', email: '' });
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoSuccess, setDemoSuccess] = useState(false);
  const [demoError, setDemoError]     = useState('');

  const handleDemoSubmit = async (e) => {
    e.preventDefault();
    setDemoLoading(true);
    setDemoError('');
    try {
      await fetch('http://localhost:8000/api/v1/demo/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ institution: demoForm.institution, email: demoForm.email }),
      });
      setDemoSuccess(true);
    } catch {
      setDemoError('Failed to send request. Please try again.');
    } finally {
      setDemoLoading(false);
    }
  };

  return (
    <div className="landing">

      {/* ── Navbar ── */}
      <nav className="landing-nav">
        <div className="landing-nav-inner">
          <div className="landing-logo">
            <div className="landing-logo-icon"><MdShield size={22} /></div>
            <div>
              <span className="landing-logo-name">AML Monitor</span>
              <span className="landing-logo-sub">Compliance System</span>
            </div>
          </div>
          <div className="landing-nav-links">
            <a href="#features" className="landing-nav-link">Features</a>
            <a href="#stats"    className="landing-nav-link">Stats</a>
            <a href="#about"    className="landing-nav-link" onClick={e => { e.preventDefault(); document.getElementById('contact').scrollIntoView({ behavior: 'smooth' }); }}>About</a>
          </div>
          <div className="landing-nav-actions">
            <button className="landing-btn-outline" onClick={() => document.getElementById('contact').scrollIntoView({ behavior: 'smooth' })}>Contact Us</button>
            <button className="landing-btn-solid"   onClick={() => document.getElementById('demo').scrollIntoView({ behavior: 'smooth' })}>Request Demo</button>
            <button className="landing-theme-toggle" onClick={toggleTheme} title="Toggle theme">
              {theme === 'dark' ? <MdLightMode size={18} /> : <MdDarkMode size={18} />}
            </button>
            <button className="landing-nav-signin"  onClick={() => navigate('/login')}>Sign In</button>
          </div>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="landing-hero">
        <div className="hero-bg">
          <div className="hero-blob b1" />
          <div className="hero-blob b2" />
          <div className="hero-blob b3" />
        </div>
        <div className="hero-logo-visual">
          <div className="hero-logo-ring hero-logo-ring-3" />
          <div className="hero-logo-ring hero-logo-ring-2" />
          <div className="hero-logo-ring hero-logo-ring-1" />
          <div className="hero-logo-icon">
            <MdSecurity size={140} color="#fff" />
          </div>
        </div>
        <div className="hero-content">
          <div className="hero-badge"><MdSecurity size={14} /> AML Compliance Platform</div>
          <h1 className="hero-title">
            Detect Money Laundering<br />
            <span className="hero-title-accent">Before It Happens</span>
          </h1>
          <p className="hero-desc">
            An Anti-Money Laundering transaction monitoring system built on
            real FinCEN, FATF, and BSA regulations. Monitor transactions, screen sanctions,
            manage investigations — all in one place.
          </p>
          <div className="hero-actions">
            <button className="landing-btn-solid hero-cta" onClick={() => document.getElementById('demo').scrollIntoView({ behavior: 'smooth' })}>
              Request Demo <MdArrowForward size={18} />
            </button>
            <button className="landing-btn-outline hero-cta" onClick={() => document.getElementById('contact').scrollIntoView({ behavior: 'smooth' })}>
              Contact Us
            </button>
          </div>

        </div>
      </section>

      {/* ── Stats ── */}
      <section className="landing-stats" id="stats">
        <div className="landing-section-inner">
          <div className="stats-grid">
            {STATS.map((s, i) => (
              <div key={i} className="stat-card">
                <div className="stat-value">{s.value}</div>
                <div className="stat-label">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section className="landing-features" id="features">
        <div className="landing-section-inner">
          <div className="section-header">
            <h2 className="section-title">Everything you need for AML compliance</h2>
            <p className="section-desc">
              Built for compliance analysts, supervisors, and administrators in financial institutions.
            </p>
          </div>
          <div className="features-grid">
            {FEATURES.map((f, i) => (
              <div key={i} className="feature-card">
                <div className="feature-icon"><f.icon size={22} /></div>
                <h3 className="feature-title">{f.title}</h3>
                <p className="feature-desc">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Request Demo ── */}
      <section className="landing-cta" id="demo">
        <div className="landing-section-inner">
          <div className="cta-card">
            <MdSpeed size={40} className="cta-icon" />
            <h2 className="cta-title">Request a Demo</h2>
            <p className="cta-desc">
              See how AML Monitor helps compliance teams at banks and financial institutions
              detect suspicious activity, screen sanctions, and manage investigations in real time.
            </p>
            {demoSuccess ? (
              <div className="demo-success">
                ✓ Request received! We'll contact <strong>{demoForm.email}</strong> shortly to schedule your demo.
              </div>
            ) : (
              <form className="demo-form" onSubmit={handleDemoSubmit}>
                <div className="demo-form-row">
                  <div className="demo-field">
                    <MdBusiness size={16} className="demo-field-icon" />
                    <input className="demo-input" type="text" placeholder="Institution / Bank Name"
                      value={demoForm.institution} onChange={e => setDemoForm({ ...demoForm, institution: e.target.value })} required />
                  </div>
                  <div className="demo-field">
                    <MdEmail size={16} className="demo-field-icon" />
                    <input className="demo-input" type="email" placeholder="Work Email Address"
                      value={demoForm.email} onChange={e => setDemoForm({ ...demoForm, email: e.target.value })} required />
                  </div>
                </div>
                {demoError && <div className="demo-error">{demoError}</div>}
                <button type="submit" className="landing-btn-solid hero-cta"
                  style={{ width: '100%', justifyContent: 'center' }} disabled={demoLoading}>
                  {demoLoading ? 'Sending Request...' : <> Request Demo Access <MdArrowForward size={18} /> </>}
                </button>
              </form>
            )}
          </div>
        </div>
      </section>

      {/* ── Contact Us ── */}
      <section className="landing-contact" id="contact">
        <div className="landing-section-inner">
          <div className="section-header">
            <h2 className="section-title">Contact Us</h2>
            <p className="section-desc">Have questions? Our compliance team is ready to help.</p>
          </div>
          <div className="contact-grid">
            <div className="contact-card">
              <div className="contact-icon"><MdEmail size={22} /></div>
              <div className="contact-label">Email</div>
              <div className="contact-value">aml.monitoring.system@gmail.com</div>
            </div>
            <div className="contact-card">
              <div className="contact-icon"><MdPhone size={22} /></div>
              <div className="contact-label">Phone</div>
              <div className="contact-value">+374 98 248 000</div>
            </div>
            <div className="contact-card">
              <div className="contact-icon"><MdBusiness size={22} /></div>
              <div className="contact-label">Headquarters</div>
              <div className="contact-value">Yerevan, Armenia</div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="landing-footer">
        <div className="landing-section-inner">
          <div className="footer-inner">
            <div className="landing-logo">
              <div className="landing-logo-icon"><MdShield size={18} /></div>
              <div>
                <span className="landing-logo-name">AML Monitor</span>
                <span className="landing-logo-sub">Compliance System</span>
              </div>
            </div>
            <p className="footer-copy">
              © 2026 AML Monitor. Built for academic research based on FinCEN · FATF · BSA · OFAC regulations.
            </p>
            <div className="footer-links">
              <button className="footer-link" onClick={() => navigate('/login')}>Sign In</button>
              <button className="footer-link" onClick={() => document.getElementById('contact').scrollIntoView({ behavior: 'smooth' })}>Contact Us</button>
            </div>
          </div>
        </div>
      </footer>

      <ChatWidget />
    </div>
  );
}
