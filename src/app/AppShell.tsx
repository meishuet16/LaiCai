import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useApp } from './AppContext';
import { navItems, timelinePath, type Section } from './routes';
import type { Currency, DataMode, Horizon, Role } from '../domain/customer';
import { CommandCenterPage } from '../features/CommandCenterPage';
import { DecisionCasesPage } from '../features/DecisionCasesPage';
import { DecisionCaseDetailPage } from '../features/DecisionCaseDetailPage';
import { IntegrationHealthPage } from '../features/IntegrationHealthPage';
import { PredictionRadarPage } from '../features/PredictionRadarPage';
import { PredictionDetailPage } from '../features/PredictionDetailPage';
import { TimelinePage } from '../features/TimelinePage';

type PrimarySection = 'command-center' | 'integrations' | 'predictions' | 'cases' | 'timeline';
const subtitles: Record<PrimarySection, string> = {
  'command-center': '',
  integrations: 'Source connectivity, synchronization, freshness and data quality',
  predictions: 'Multi-horizon risk with reliability and account-level evidence',
  cases: 'Prioritized retention work, human decisions and scenario planning',
  timeline: 'Customer profile, prediction, decisions and observed evidence',
};

function NavGlyph({ section }: { section: Section }) {
  const common = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  const paths: Record<string, ReactNode> = {
    integrations: <><path d="M8 3v5M16 3v5M6 8h12v3a6 6 0 0 1-12 0V8Z"/><path d="M12 17v4m-3 0h6"/></>,
    predictions: <><circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><path d="m12 12 6-6M15 6h3v3"/></>,
    cases: <><path d="M4 7.5h6l2 2H20v9H4z"/><path d="M4 7.5v-2h6l2 2"/><path d="m9 14 2 2 4-4"/></>,
    'command-center': <><rect x="3.5" y="3.5" width="7" height="7" rx="1.3"/><rect x="13.5" y="3.5" width="7" height="4" rx="1.3"/><rect x="13.5" y="10.5" width="7" height="10" rx="1.3"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.3"/></>,
    timeline: <><path d="M5 5h14M5 12h14M5 19h14"/><circle cx="8" cy="5" r="1.5"/><circle cx="15" cy="12" r="1.5"/><circle cx="10" cy="19" r="1.5"/></>,
  };
  return <svg aria-hidden="true" focusable="false" viewBox="0 0 24 24" {...common}>{paths[section] ?? paths['command-center']}</svg>;
}

function RouteDrawer({ eyebrow, title, onClose, children, centered = false }: { eyebrow: string; title: string; onClose: () => void; children: ReactNode; centered?: boolean }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); onClose(); }
      if (event.key !== 'Tab') return;
      const focusable = drawerRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])');
      if (!focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      if (returnFocus?.isConnected) returnFocus.focus();
    };
  }, [onClose]);
  return <div className={`detail-overlay route-overlay${centered ? ' route-overlay--center' : ''}`} onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
    <section ref={drawerRef} className={`route-drawer${centered ? ' route-drawer--center' : ''}`} role="dialog" aria-modal="true" aria-label={title}>
      <header className="drawer-head"><div><p className="drawer-eyebrow">{eyebrow}</p><h2>{title}</h2></div><button ref={closeRef} className="btn outline" onClick={onClose} aria-label={`Close ${title}`}>Close</button></header>
      <div className="drawer-scroll">{children}</div>
    </section>
  </div>;
}

export function AppShell() {
  const { route, navigate, closeDrawer, role, setRole, horizon, setHorizon, currency, setCurrency, dataMode, setDataMode } = useApp();
  const mainRef = useRef<HTMLElement>(null);
  const previousPageKey = useRef('');
  const scrollByPage = useRef<Record<string, number>>({});
  const [timelineCustomerId, setTimelineCustomerId] = useState(() => route.section === 'timeline' ? route.customerId : 'c01');

  const activePage: PrimarySection = route.section === 'prediction-detail' ? 'predictions' : route.section === 'case-detail' ? 'cases' : route.section;
  const displayedTimelineCustomerId = route.section === 'timeline' ? route.customerId : timelineCustomerId;
  useEffect(() => { if (route.section === 'timeline') setTimelineCustomerId(route.customerId); }, [route]);
  const pageKey = activePage === 'timeline' ? `${activePage}:${displayedTimelineCustomerId}` : activePage;
  useEffect(() => {
    if (previousPageKey.current && mainRef.current) scrollByPage.current[previousPageKey.current] = mainRef.current.scrollTop;
    if (mainRef.current) mainRef.current.scrollTo(0, scrollByPage.current[pageKey] ?? 0);
    previousPageKey.current = pageKey;
  }, [pageKey]);

  const drawerOpen = route.section === 'prediction-detail' || route.section === 'case-detail';
  const title = navItems.find(item => item.section === activePage)?.label ?? 'Business Overview';
  const pages: { section: PrimarySection; content: ReactNode }[] = [
    { section: 'command-center', content: <CommandCenterPage /> },
    { section: 'integrations', content: <IntegrationHealthPage /> },
    { section: 'predictions', content: <PredictionRadarPage /> },
    { section: 'cases', content: <DecisionCasesPage /> },
    { section: 'timeline', content: <TimelinePage customerId={displayedTimelineCustomerId} /> },
  ];

  return <div className="app">
    <aside className="sidebar">
      <a className="logo" href="/command-center" aria-label="RetainIQ — Business Overview" onClick={event => { if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) { event.preventDefault(); navigate('/command-center'); } }}><span>R</span><b>RetainIQ</b></a>
      <nav aria-label="Main navigation">
        {navItems.map(item => {
          const active = activePage === item.section;
          const href = item.section === 'timeline' ? timelinePath(displayedTimelineCustomerId) : item.href;
          return <a key={item.section} href={href} aria-current={active ? 'page' : undefined} className={`nav-link${active ? ' active' : ''}`} onClick={event => { if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) { event.preventDefault(); navigate(href); } }}><NavGlyph section={item.section} /><span>{item.label}</span></a>;
        })}
      </nav>
    </aside>
    <div className="main">
      <header className="topbar">
        <div className="page-heading"><h1>{title}</h1>{subtitles[activePage] && <p className="subtitle">{subtitles[activePage]}</p>}</div>
        <div className="topbar-tools">
          <label className="header-control">Data source<select value={dataMode} onChange={event => setDataMode(event.target.value as DataMode)}><option value="connected">Connected · unavailable</option><option value="demo_fixture">Sample data</option></select></label>
          {activePage === 'predictions' || activePage === 'cases' ? <label className="header-control">Currency<select value={currency} onChange={event => setCurrency(event.target.value as Currency | 'All')}><option>All</option><option>MYR</option><option>USD</option><option>SGD</option></select></label> : null}
          {activePage === 'predictions' || activePage === 'timeline' ? <div className="horizon-control"><span>Horizon</span><div className="seg" aria-label="Prediction horizon">{([7, 14, 30] as Horizon[]).map(days => <button aria-pressed={horizon === days} className={horizon === days ? 'on' : ''} onClick={() => setHorizon(days)} key={days}>{days}d</button>)}</div></div> : null}
          {activePage === 'cases' || activePage === 'timeline' ? <label className="header-control">Role preview<select aria-label="Role preview (not authentication)" value={role} onChange={event => setRole(event.target.value as Role)}><option>Manager</option><option>CSM</option><option>Admin</option><option>Viewer</option></select></label> : null}
        </div>
      </header>
      <main ref={mainRef}>
        <div className="page-stack">
          {pages.map(page => <section key={page.section} className="page-view" hidden={activePage !== page.section} aria-hidden={activePage !== page.section} inert={activePage !== page.section || drawerOpen} aria-label={navItems.find(item => item.section === page.section)?.label}>{page.content}</section>)}
        </div>
        {route.section === 'prediction-detail' && <RouteDrawer eyebrow="Churn Prediction · Account evidence" title="Prediction details" onClose={closeDrawer}><PredictionDetailPage predictionId={route.predictionId} /></RouteDrawer>}
        {route.section === 'case-detail' && <RouteDrawer eyebrow="Retention Actions" title="Retention case details" onClose={closeDrawer} centered><DecisionCaseDetailPage key={route.caseId} caseId={route.caseId} /></RouteDrawer>}
      </main>
    </div>
  </div>;
}
