import { useEffect, useState } from 'react';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Toggle } from '../components/common/Toggle';
import { Modal } from '../components/common/Modal';
import { PageTransition } from '../components/common/PageTransition';
import { SkeletonCard } from '../components/common/Skeleton';
import { useToastStore } from '../components/common/Toast';
import { useAuthStore } from '../stores/authStore';
import client from '../api/client';

interface NotificationConfig {
  telegram_configured: boolean;
  notify_on_trade: boolean;
  notify_on_error: boolean;
  notify_on_alert: boolean;
}

interface APIKey {
  id: string;
  exchange: string;
  label: string;
  key_preview: string;
  created_at: string;
}

export function Settings() {
  const [config, setConfig] = useState<Record<string, unknown> | null>(null);
  const [notifications, setNotifications] = useState<NotificationConfig | null>(null);
  const [apiKeys, setApiKeys] = useState<APIKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [addKeyModal, setAddKeyModal] = useState(false);
  const [newKey, setNewKey] = useState({ exchange: 'bybit', label: '', api_key: '', api_secret: '' });
  const toast = useToastStore((s) => s.add);
  const { user } = useAuthStore();

  useEffect(() => {
    Promise.all([
      client.get('/api/v1/settings/config'),
      client.get('/api/v1/settings/notifications'),
    ]).then(([configRes, notifRes]) => {
      setConfig(configRes.data);
      setNotifications(notifRes.data);
    }).catch(() => {})
    .finally(() => setLoading(false));
  }, []);

  const handleNotificationToggle = async (key: keyof NotificationConfig, value: boolean) => {
    if (!notifications) return;
    const updated = { ...notifications, [key]: value };
    setNotifications(updated);
    try {
      await client.put('/api/v1/settings/notifications', updated);
      toast('Notification settings updated', 'success');
    } catch {
      setNotifications(notifications);
      toast('Failed to update notifications', 'error');
    }
  };

  const handleAddKey = async () => {
    if (!newKey.label || !newKey.api_key || !newKey.api_secret) {
      toast('Please fill all fields', 'warning');
      return;
    }
    // In a real implementation this would call the API
    const mockKey: APIKey = {
      id: String(Date.now()),
      exchange: newKey.exchange,
      label: newKey.label,
      key_preview: newKey.api_key.slice(0, 8) + '...',
      created_at: new Date().toISOString(),
    };
    setApiKeys([...apiKeys, mockKey]);
    setNewKey({ exchange: 'bybit', label: '', api_key: '', api_secret: '' });
    setAddKeyModal(false);
    toast('API key added', 'success');
  };

  const handleRemoveKey = (id: string) => {
    setApiKeys(apiKeys.filter((k) => k.id !== id));
    toast('API key removed', 'info');
  };

  const inputClass = 'w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary transition-colors';

  if (loading) {
    return (
      <div>
        <div className="h-7 w-28 animate-pulse bg-border/50 rounded mb-6" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      </div>
    );
  }

  return (
    <PageTransition>
      <h2 className="text-2xl font-bold text-text font-[Manrope] mb-6">Settings</h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Profile */}
        <Card title="Profile">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-text-muted">Username</span>
              <span className="text-sm text-text font-medium">{user?.username}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-text-muted">Email</span>
              <span className="text-sm text-text font-medium">{user?.email || 'Not set'}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-text-muted">Role</span>
              <span className={`text-xs px-2 py-0.5 rounded ${user?.is_admin ? 'bg-primary/20 text-primary' : 'bg-border text-text-muted'}`}>
                {user?.is_admin ? 'Admin' : 'User'}
              </span>
            </div>
          </div>
        </Card>

        {/* Notifications */}
        <Card title="Notifications">
          {notifications && (
            <div className="space-y-4">
              <Toggle
                checked={notifications.notify_on_trade}
                onChange={(v) => handleNotificationToggle('notify_on_trade', v)}
                label="Notify on trade execution"
              />
              <Toggle
                checked={notifications.notify_on_error}
                onChange={(v) => handleNotificationToggle('notify_on_error', v)}
                label="Notify on errors"
              />
              <Toggle
                checked={notifications.notify_on_alert}
                onChange={(v) => handleNotificationToggle('notify_on_alert', v)}
                label="Notify on price alerts"
              />
              <div className="pt-2 border-t border-border">
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${notifications.telegram_configured ? 'bg-profit' : 'bg-loss'}`} />
                  <span className="text-xs text-text-muted">
                    Telegram {notifications.telegram_configured ? 'connected' : 'not configured'}
                  </span>
                </div>
              </div>
            </div>
          )}
        </Card>

        {/* API Keys */}
        <Card title="Exchange API Keys" className="lg:col-span-2">
          {apiKeys.length > 0 ? (
            <div className="space-y-2 mb-4">
              {apiKeys.map((key) => (
                <div key={key.id} className="flex items-center justify-between py-3 px-4 bg-background rounded-lg border border-border">
                  <div className="flex items-center gap-3">
                    <span className="text-xs px-2 py-0.5 bg-blue/20 text-blue rounded uppercase font-medium">
                      {key.exchange}
                    </span>
                    <div>
                      <p className="text-sm text-text font-medium">{key.label}</p>
                      <p className="text-xs text-text-muted font-mono">{key.key_preview}</p>
                    </div>
                  </div>
                  <Button variant="danger" size="sm" onClick={() => handleRemoveKey(key.id)}>
                    Remove
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-text-muted mb-4">No API keys configured. Add your exchange credentials to start trading.</p>
          )}
          <Button size="sm" onClick={() => setAddKeyModal(true)}>Add API Key</Button>
        </Card>

        {/* System Config */}
        <Card title="System Configuration" className="lg:col-span-2">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {config && Object.entries(config).map(([section, values]) => (
              <div key={section} className="bg-background rounded-lg p-4 border border-border">
                <h4 className="text-xs font-semibold text-text-muted uppercase mb-2">{section}</h4>
                {typeof values === 'object' && values !== null && Object.entries(values as Record<string, unknown>).map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between py-1">
                    <span className="text-xs text-text-muted">{k}</span>
                    <span className="text-xs text-text font-mono">{String(v)}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Add API Key Modal */}
      <Modal open={addKeyModal} onClose={() => setAddKeyModal(false)} title="Add Exchange API Key">
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-text-muted mb-1">Exchange</label>
            <select
              value={newKey.exchange}
              onChange={(e) => setNewKey({ ...newKey, exchange: e.target.value })}
              className={inputClass}
            >
              <option value="bybit">Bybit</option>
              <option value="binance">Binance</option>
              <option value="okx">OKX</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">Label</label>
            <input
              type="text"
              value={newKey.label}
              onChange={(e) => setNewKey({ ...newKey, label: e.target.value })}
              className={inputClass}
              placeholder="e.g., Main Trading Account"
            />
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">API Key</label>
            <input
              type="text"
              value={newKey.api_key}
              onChange={(e) => setNewKey({ ...newKey, api_key: e.target.value })}
              className={inputClass}
              placeholder="Enter your API key"
            />
          </div>
          <div>
            <label className="block text-xs text-text-muted mb-1">API Secret</label>
            <input
              type="password"
              value={newKey.api_secret}
              onChange={(e) => setNewKey({ ...newKey, api_secret: e.target.value })}
              className={inputClass}
              placeholder="Enter your API secret"
            />
          </div>
          <div className="flex gap-3 pt-2">
            <Button onClick={handleAddKey} className="flex-1">Add Key</Button>
            <Button variant="ghost" onClick={() => setAddKeyModal(false)} className="flex-1">Cancel</Button>
          </div>
        </div>
      </Modal>
    </PageTransition>
  );
}
