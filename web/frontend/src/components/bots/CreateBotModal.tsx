import { useState } from 'react';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { useToastStore } from '../common/Toast';
import { botsApi, type BotCreatePayload } from '../../api/bots';

interface StrategyType {
  name: string;
  description: string;
  config_schema: Record<string, unknown>;
  coming_soon: boolean;
}

interface CreateBotModalProps {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
  strategyTypes: StrategyType[];
  /** Pre-selected strategy name (e.g. from "Copy Template" flow) */
  presetStrategy?: string;
  /** Pre-filled config values from a copied template */
  presetConfig?: Record<string, unknown>;
}

type Step = 'select-strategy' | 'configure';

const STRATEGY_LABELS: Record<string, string> = {
  grid: 'Grid Trading',
  dca: 'DCA',
  trend_follower: 'Trend Follower',
  smc: 'SMC',
};

/** Render a JSON Schema property as a form field */
function SchemaField({
  fieldKey,
  schema,
  value,
  onChange,
}: {
  fieldKey: string;
  schema: Record<string, unknown>;
  value: unknown;
  onChange: (v: string) => void;
}) {
  const label = (schema.title as string) || fieldKey.replace(/_/g, ' ');
  const type = schema.type as string;
  const description = schema.description as string | undefined;
  const minimum = schema.minimum as number | undefined;
  const maximum = schema.maximum as number | undefined;
  const isBoolean = type === 'boolean';

  if (isBoolean) {
    return (
      <label className="flex items-center gap-2 text-sm text-text cursor-pointer">
        <input
          type="checkbox"
          className="w-4 h-4 accent-primary"
          checked={value === true || value === 'true'}
          onChange={(e) => onChange(String(e.target.checked))}
        />
        <span>{label}</span>
      </label>
    );
  }

  return (
    <div>
      <label className="block text-xs text-text-muted mb-1 capitalize">{label}</label>
      <input
        type={type === 'integer' || type === 'number' ? 'number' : 'text'}
        className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-primary focus:outline-none"
        value={String(value ?? '')}
        min={minimum}
        max={maximum}
        onChange={(e) => onChange(e.target.value)}
      />
      {description && <p className="text-xs text-text-muted mt-0.5">{description}</p>}
    </div>
  );
}

/** Build default values from a JSON Schema */
function buildDefaults(schema: Record<string, unknown>, preset?: Record<string, unknown>): Record<string, unknown> {
  const props = (schema.properties as Record<string, Record<string, unknown>>) || {};
  const defaults: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(props)) {
    if (k === 'enabled') {
      defaults[k] = preset?.[k] ?? (v.default ?? true);
    } else {
      defaults[k] = preset?.[k] ?? (v.default ?? '');
    }
  }
  return defaults;
}

export function CreateBotModal({
  open,
  onClose,
  onCreated,
  strategyTypes,
  presetStrategy,
  presetConfig,
}: CreateBotModalProps) {
  const toast = useToastStore((s) => s.add);

  const [step, setStep] = useState<Step>(presetStrategy ? 'configure' : 'select-strategy');
  const [selectedStrategy, setSelectedStrategy] = useState<StrategyType | null>(
    presetStrategy ? (strategyTypes.find((t) => t.name === presetStrategy) ?? null) : null,
  );

  // Step 2 fields
  const [botName, setBotName] = useState('');
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [exchangeId, setExchangeId] = useState('binance');
  const [sandbox, setSandbox] = useState(true);
  const [dryRun, setDryRun] = useState(true);
  const [strategyConfig, setStrategyConfig] = useState<Record<string, unknown>>({});
  const [submitting, setSubmitting] = useState(false);

  const handleSelectStrategy = (type: StrategyType) => {
    setSelectedStrategy(type);
    // Build initial config from schema defaults + preset
    const defaults = buildDefaults(type.config_schema, presetConfig);
    setStrategyConfig(defaults);
    setStep('configure');
  };

  const handleBack = () => {
    setStep('select-strategy');
    setSelectedStrategy(null);
    setStrategyConfig({});
  };

  const handleClose = () => {
    setStep(presetStrategy ? 'configure' : 'select-strategy');
    setSelectedStrategy(null);
    setStrategyConfig({});
    setBotName('');
    onClose();
  };

  const handleSubmit = async () => {
    if (!selectedStrategy) return;
    if (!botName.trim()) {
      toast('Bot name is required', 'error');
      return;
    }
    if (!symbol.trim()) {
      toast('Trading pair is required', 'error');
      return;
    }

    setSubmitting(true);
    try {
      const payload: BotCreatePayload = {
        name: botName.trim(),
        symbol: symbol.trim(),
        strategy: selectedStrategy.name,
        exchange: {
          exchange_id: exchangeId,
          credentials_name: 'default',
          sandbox,
          rate_limit: true,
        },
        risk_management: {
          max_position_size: '1000',
          max_daily_loss: '100',
          stop_loss_percentage: '5',
        },
        dry_run: dryRun,
        auto_start: false,
      };

      // Attach strategy-specific config
      if (selectedStrategy.name === 'grid') payload.grid = strategyConfig;
      else if (selectedStrategy.name === 'dca') payload.dca = strategyConfig;
      else if (selectedStrategy.name === 'trend_follower') payload.trend_follower = strategyConfig;

      await botsApi.create(payload);
      toast(`Bot "${botName}" created successfully`, 'success');
      handleClose();
      onCreated();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Failed to create bot';
      toast(msg, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const schemaProps =
    (selectedStrategy?.config_schema?.properties as Record<string, Record<string, unknown>>) || {};

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title={step === 'select-strategy' ? 'Create Bot — Select Strategy' : 'Create Bot — Configure'}
      maxWidth="max-w-lg"
    >
      {step === 'select-strategy' && (
        <div className="grid grid-cols-1 gap-3">
          {strategyTypes.map((type) => (
            <button
              key={type.name}
              disabled={type.coming_soon}
              onClick={() => handleSelectStrategy(type)}
              className={`text-left p-4 rounded-lg border transition-colors ${
                type.coming_soon
                  ? 'border-border bg-background opacity-50 cursor-not-allowed'
                  : 'border-border bg-background hover:border-primary cursor-pointer'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-semibold text-text">
                  {STRATEGY_LABELS[type.name] || type.name}
                </span>
                {type.coming_soon && (
                  <Badge variant="default">Coming Soon</Badge>
                )}
              </div>
              <p className="text-xs text-text-muted">{type.description}</p>
            </button>
          ))}
        </div>
      )}

      {step === 'configure' && selectedStrategy && (
        <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-1">
          {/* Basic fields */}
          <div>
            <label className="block text-xs text-text-muted mb-1">Bot Name</label>
            <input
              type="text"
              placeholder="my-grid-bot"
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-primary focus:outline-none"
              value={botName}
              onChange={(e) => setBotName(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-xs text-text-muted mb-1">Trading Pair</label>
            <input
              type="text"
              placeholder="BTC/USDT"
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-primary focus:outline-none"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-xs text-text-muted mb-1">Exchange</label>
            <select
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-text focus:border-primary focus:outline-none"
              value={exchangeId}
              onChange={(e) => setExchangeId(e.target.value)}
            >
              <option value="binance">Binance</option>
              <option value="bybit">Bybit</option>
              <option value="okx">OKX</option>
            </select>
          </div>

          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-text cursor-pointer">
              <input
                type="checkbox"
                className="w-4 h-4 accent-primary"
                checked={sandbox}
                onChange={(e) => setSandbox(e.target.checked)}
              />
              <span>Sandbox / Testnet</span>
            </label>
            <label className="flex items-center gap-2 text-sm text-text cursor-pointer">
              <input
                type="checkbox"
                className="w-4 h-4 accent-primary"
                checked={dryRun}
                onChange={(e) => setDryRun(e.target.checked)}
              />
              <span>Dry Run</span>
            </label>
          </div>

          {/* Dynamic strategy config */}
          {Object.keys(schemaProps).length > 0 && (
            <>
              <hr className="border-border" />
              <p className="text-xs font-semibold text-text-muted uppercase tracking-wide">
                {STRATEGY_LABELS[selectedStrategy.name] || selectedStrategy.name} Parameters
              </p>
              {Object.entries(schemaProps).map(([key, fieldSchema]) => (
                <SchemaField
                  key={key}
                  fieldKey={key}
                  schema={fieldSchema}
                  value={strategyConfig[key]}
                  onChange={(v) => setStrategyConfig((prev) => ({ ...prev, [key]: v }))}
                />
              ))}
            </>
          )}
        </div>
      )}

      <div className="flex items-center justify-between mt-6">
        {step === 'configure' && !presetStrategy ? (
          <Button variant="ghost" size="sm" onClick={handleBack}>
            ← Back
          </Button>
        ) : (
          <span />
        )}
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={handleClose}>
            Cancel
          </Button>
          {step === 'configure' && (
            <Button variant="primary" size="sm" onClick={handleSubmit} disabled={submitting}>
              {submitting ? 'Creating…' : 'Create Bot'}
            </Button>
          )}
        </div>
      </div>
    </Modal>
  );
}
