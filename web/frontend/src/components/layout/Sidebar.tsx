import { NavLink } from 'react-router-dom';

const navItems = [
  { path: '/', label: 'Dashboard', icon: '◉' },
  { path: '/bots', label: 'Bots', icon: '⚙' },
  { path: '/strategies', label: 'Strategies', icon: '◎' },
  { path: '/portfolio', label: 'Portfolio', icon: '◈' },
  { path: '/backtesting', label: 'Backtesting', icon: '▶' },
  { path: '/settings', label: 'Settings', icon: '☰' },
];

export function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 h-full w-60 bg-surface border-r border-border flex flex-col z-10">
      <div className="p-5 border-b border-border">
        <h1 className="text-xl font-bold text-text font-[Manrope]">
          <span className="text-primary">TRADER</span>AGENT
        </h1>
        <p className="text-xs text-text-muted mt-1">v2.0 Dashboard</p>
      </div>

      <nav className="flex-1 py-4">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `flex items-center gap-3 px-5 py-3 text-sm transition-colors ${
                isActive
                  ? 'bg-primary/20 text-primary border-r-2 border-primary'
                  : 'text-text-muted hover:bg-surface-hover hover:text-text'
              }`
            }
          >
            <span className="text-lg">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-border">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-profit animate-pulse" />
          <span className="text-xs text-text-muted">System Online</span>
        </div>
      </div>
    </aside>
  );
}
