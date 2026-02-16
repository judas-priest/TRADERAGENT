import { useAuthStore } from '../../stores/authStore';

export function Header() {
  const { user, logout } = useAuthStore();

  return (
    <header className="h-14 bg-surface border-b border-border flex items-center justify-between px-6 ml-60">
      <div />
      <div className="flex items-center gap-4">
        {user && (
          <>
            <span className="text-sm text-text-muted">{user.username}</span>
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
