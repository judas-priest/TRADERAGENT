import { Outlet } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { ErrorBoundary } from '../common/ErrorBoundary';
import { ToastContainer } from '../common/Toast';

export function AppLayout() {
  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <Header />
      <main className="ml-0 md:ml-60 pt-14 p-4 md:p-6">
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </main>
      <ToastContainer />
    </div>
  );
}
