import { useEffect, useState } from 'react';
import { Card } from '../components/common/Card';
import { Spinner } from '../components/common/Spinner';
import client from '../api/client';

export function Settings() {
  const [config, setConfig] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    client.get('/api/v1/settings/config')
      .then((res) => setConfig(res.data))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center py-20"><Spinner size="lg" /></div>;

  return (
    <div>
      <h2 className="text-2xl font-bold text-text font-[Manrope] mb-6">Settings</h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="System Configuration">
          <pre className="text-xs text-text-muted overflow-auto">
            {JSON.stringify(config, null, 2)}
          </pre>
        </Card>

        <Card title="Notifications">
          <p className="text-sm text-text-muted">
            Notification settings will be configurable here.
          </p>
        </Card>
      </div>
    </div>
  );
}
