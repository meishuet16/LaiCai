export type Section = 'command-center' | 'integrations' | 'predictions' | 'prediction-detail' | 'cases' | 'case-detail' | 'timeline';
export type AppRoute = { section: 'command-center' | 'integrations' | 'predictions' | 'cases' } | { section: 'timeline'; customerId: string } | { section: 'prediction-detail'; predictionId: string } | { section: 'case-detail'; caseId: string };
export const navItems = [
  { section: 'command-center', label: 'Business Overview', href: '/command-center' },
  { section: 'integrations', label: 'Data Integration', href: '/integrations' },
  { section: 'predictions', label: 'Churn Prediction', href: '/predictions' },
  { section: 'cases', label: 'Retention Actions', href: '/cases' },
  { section: 'timeline', label: 'Customer Insights', href: '/customers/c01/timeline' },
] as const;
export const timelinePath = (customerId: string) => `/customers/${encodeURIComponent(customerId)}/timeline`;
export const predictionPath = (predictionId: string) => `/predictions/${encodeURIComponent(predictionId)}`;
export const casePath = (caseId: string) => `/cases/${encodeURIComponent(caseId)}`;
export function routeFromPath(pathname: string): AppRoute {
  const caseMatch = pathname.match(/^\/cases\/([^/]+)\/?$/);
  if (caseMatch) {
    try { return { section: 'case-detail', caseId: decodeURIComponent(caseMatch[1]) }; }
    catch { return { section: 'cases' }; }
  }
  const prediction = pathname.match(/^\/predictions\/([^/]+)\/?$/);
  if (prediction) {
    try { return { section: 'prediction-detail', predictionId: decodeURIComponent(prediction[1]) }; }
    catch { return { section: 'predictions' }; }
  }
  const match = pathname.match(/^\/customers\/([^/]+)\/timeline\/?$/);
  if (match) {
    try { return { section: 'timeline', customerId: decodeURIComponent(match[1]) }; }
    catch { return { section: 'command-center' }; }
  }
  const section = navItems.find(item => item.href === pathname.replace(/\/$/, ''))?.section;
  return { section: section && section !== 'timeline' ? section : 'command-center' };
}
