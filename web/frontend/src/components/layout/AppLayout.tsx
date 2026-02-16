import { Outlet } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';

export function AppLayout() {
  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <Header />
      <main className="ml-60 pt-14 p-6">
        <Outlet />
      </main>
    </div>
  );
}
