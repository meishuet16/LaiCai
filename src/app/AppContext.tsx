import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import type { Currency, Horizon, Role } from '../domain/customer';
import { routeFromPath, type AppRoute } from './routes';

type AppState = {
  dataMode: 'connected' | 'demo_fixture'; setDataMode: (mode: 'connected' | 'demo_fixture') => void;
  route: AppRoute;
  navigate: (path: string) => void;
  closeDrawer: () => void;
  query: string; setQuery: (query: string) => void;
  horizon: Horizon; setHorizon: (horizon: Horizon) => void;
  currency: Currency | 'All'; setCurrency: (currency: Currency | 'All') => void;
  role: Role; setRole: (role: Role) => void;
};
const Context = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [dataMode, setDataMode] = useState<AppState['dataMode']>('demo_fixture');
  const [route, setRoute] = useState<AppRoute>(() => routeFromPath(window.location.pathname));
  const [query, setQuery] = useState('');
  const [horizon, setHorizon] = useState<Horizon>(30);
  const [currency, setCurrency] = useState<Currency | 'All'>('All');
  const [role, setRole] = useState<Role>('Manager');

  useEffect(() => {
    const onPopState = () => setRoute(routeFromPath(window.location.pathname));
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  const navigate = useCallback((path: string) => {
    if (window.location.pathname !== path) window.history.pushState({ retainIQInternal: true }, '', path);
    setRoute(routeFromPath(path));
  }, []);

  const closeDrawer = useCallback(() => {
    if (window.history.state?.retainIQInternal && window.history.length > 1) {
      window.history.back();
      return;
    }
    if (route.section === 'prediction-detail') navigate('/predictions');
    else if (route.section === 'case-detail') navigate('/cases');
  }, [navigate, route.section]);

  return <Context.Provider value={{ dataMode, setDataMode, route, navigate, closeDrawer, query, setQuery, horizon, setHorizon, currency, setCurrency, role, setRole }}>{children}</Context.Provider>;
}
export function useApp() { const value = useContext(Context); if (!value) throw new Error('Missing AppProvider'); return value; }
