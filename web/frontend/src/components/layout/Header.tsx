import { useAuthStore } from '../../stores/authStore';
import { useUIStore } from '../../stores/uiStore';

export function Header() {
  const { user, logout } = useAuthStore();
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);

  return (
    <header className="h-14 bg-surface border-b border-border flex items-center justify-between px-4 md:px-6 ml-0 md:ml-60">
      <button
        onClick={toggleSidebar}
        className="md:hidden text-text-muted hover:text-text transition-colors p-1"
        aria-label="Toggle menu"
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M3 5h14M3 10h14M3 15h14" />
        </svg>
      </button>
      <div className="hidden md:block" />
      <div className="flex items-center gap-4">
        {user && (
          <>
            <span className="text-sm text-text-muted hidden sm:inline">{user.username}</span>
            {user.is_admin && (
              <span className="text-xs px-2 py-0.5 bg-primary/20 text-primary rounded">
                Admin
              </span>
            )}
            <button
              onClick={logout}
              className="text-sm text-text-muted hover:text-text transition-colors"
            >
              Logout
            </button>
          </>
        )}
      </div>
    </header>
  );
}
