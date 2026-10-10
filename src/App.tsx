import { AppShell } from './app/AppShell';
import { AppProvider } from './app/AppContext';
export default function App() { return <AppProvider><AppShell /></AppProvider>; }
