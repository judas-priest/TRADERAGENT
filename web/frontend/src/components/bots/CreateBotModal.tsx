import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Modal } from '../common/Modal';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { Toggle } from '../common/Toggle';
import { Skeleton } from '../common/Skeleton';
import { botsApi, type BotCreateRequest } from '../../api/bots';
import { useToastStore } from '../common/Toast';
import client from '../../api/client';

interface StrategyType {
  name: string;
  description: string;
  config_schema: Record<string, unknown>;
}

interface SchemaProperty {
  type?: string;
  title?: string;
  description?: string;
  default?: unknown;
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  exclusiveMaximum?: number;
  enum?: string[];
}

interface CreateBotModalProps {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
  presetStrategy?: string;
  presetConfig?: Record<string, unknown>;
}

const STRATEGY_ICONS: Record<string, string> = {
  grid: '⚡',
  dca: '📉',
  trend_follower: '📈',
  smc: '🏦',
};

const STRATEGY_DISPLAY_NAMES: Record<string, string> = {
  grid: 'Grid',
  dca: 'DCA',
  trend_follower: 'Trend Follower',
  smc: 'SMC',
};

function StrategyCard({
  strategy,
  selected,
  disabled,
  onClick,
}: {
  strategy: StrategyType;
  selected: boolean;
  disabled: boolean;
  onClick: () => void;
}) {
  const displayName = STRATEGY_DISPLAY_NAMES[strategy.name] ?? strategy.name;
  const icon = STRATEGY_ICONS[strategy.name] ?? '🤖';

  return (
    <motion.button
      type="button"
      whileHover={disabled ? {} : { scale: 1.02 }}
      onClick={disabled ? undefined : onClick}
      className={`relative w-full text-left p-4 rounded-xl border transition-colors ${
        disabled
          ? 'opacity-50 cursor-not-allowed border-border bg-surface'
          : selected
          ? 'border-primary bg-primary/10 cursor-pointer'
          : 'border-border bg-surface hover:border-primary/50 cursor-pointer'
      }`}
    >
      {disabled && (
        <span className="absolute top-2 right-2">
          <Badge variant="default">Soon</Badge>
        </span>
      )}
      <div className="flex items-start gap-3">
        <span className="text-2xl">{icon}</span>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-text">{displayName}</p>
          <p className="text-xs text-text-muted mt-0.5 leading-snug">{strategy.description}</p>
        </div>
      </div>
    </motion.button>
  );
}

function DynamicField({
  name,
  prop,
  value,
  onChange,
}: {
  name: string;
  prop: SchemaProperty;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  const label = prop.title ?? name.replace(/_/g, ' ');
  const description = prop.description;

  if (prop.type === 'boolean') {
    return (
      <div className="flex items-center justify-between py-2">
        <div>
          <p className="text-sm text-text capitalize">{label}</p>
          {description && <p className="text-xs text-text-muted">{description}</p>}
        </div>
        <Toggle checked={Boolean(value)} onChange={onChange} />
      </div>
    );
  }

  if (prop.enum) {
    return (
      <div>
        <label className="block text-xs text-text-muted mb-1 capitalize">{label}</label>
        {description && <p className="text-xs text-text-muted mb-1">{description}</p>}
        <select
          value={String(value ?? '')}
          onChange={(e) => onChange(e.target.value)}
          className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
        >
          {prop.enum.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      </div>
    );
  }

  const isNumeric = prop.type === 'number' || prop.type === 'integer';
  const min = prop.minimum ?? prop.exclusiveMinimum;
  const max = prop.maximum ?? prop.exclusiveMaximum;

  return (
    <div>
      <label className="block text-xs text-text-muted mb-1 capitalize">{label}</label>
      {description && <p className="text-xs text-text-muted mb-1">{description}</p>}
      <input
        type={isNumeric ? 'number' : 'text'}
        value={String(value ?? '')}
        min={min}
        max={max}
        step={prop.type === 'integer' ? 1 : 'any'}
        onChange={(e) =>
          onChange(isNumeric ? (e.target.value === '' ? '' : Number(e.target.value)) : e.target.value)
        }
        className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
      />
    </div>
  );
}

function buildDefaultParams(schema: Record<string, unknown>): Record<string, unknown> {
  const properties = (schema.properties ?? {}) as Record<string, SchemaProperty>;
  const result: Record<string, unknown> = {};
  for (const [key, prop] of Object.entries(properties)) {
    if (key === 'enabled') continue;
    if (prop.default !== undefined) {
      result[key] = prop.default;
    } else if (prop.type === 'boolean') {
      result[key] = false;
    } else if (prop.type === 'integer') {
      result[key] = prop.minimum ?? 0;
    } else if (prop.type === 'number') {
      result[key] = 0;
    } else {
      result[key] = '';
    }
  }
  return result;
}

export function CreateBotModal({ open, onClose, onCreated, presetStrategy, presetConfig }: CreateBotModalProps) {
  const [step, setStep] = useState<1 | 2>(1);
  const [strategies, setStrategies] = useState<StrategyType[]>([]);
  const [loadingStrategies, setLoadingStrategies] = useState(false);
  const [selectedStrategy, setSelectedStrategy] = useState<StrategyType | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const toast = useToastStore((s) => s.add);

  // Step 2 form state
  const [botName, setBotName] = useState('');
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [exchange, setExchange] = useState('binance');
  const [dryRun, setDryRun] = useState(true);
  const [strategyParams, setStrategyParams] = useState<Record<string, unknown>>({});

  // Reset state when modal opens
  useEffect(() => {
    if (open) {
      setBotName('');
      setSymbol('BTC/USDT');
      setExchange('binance');
      setDryRun(true);
      if (presetStrategy) {
        // Skip step 1 when a preset strategy is provided
        setStep(2);
        setStrategyParams(presetConfig ?? {});
      } else {
        setStep(1);
        setSelectedStrategy(null);
        setStrategyParams({});
      }
    }
  }, [open, presetStrategy, presetConfig]);

  // Load strategies on mount
  useEffect(() => {
    if (!open) return;
    setLoadingStrategies(true);
    client
      .get<StrategyType[]>('/api/v1/strategies/types')
      .then((res) => {
        setStrategies(res.data);
        if (presetStrategy) {
          const preset = res.data.find((s) => s.name === presetStrategy);
          if (preset) {
            setSelectedStrategy(preset);
            // Merge preset config over schema defaults
            setStrategyParams((prev) => ({
              ...buildDefaultParams(preset.config_schema),
              ...prev,
            }));
          }
        }
      })
      .catch(() => toast('Failed to load strategies', 'error'))
      .finally(() => setLoadingStrategies(false));
  }, [open, presetStrategy, toast]);

  const handleSelectStrategy = (strategy: StrategyType) => {
    setSelectedStrategy(strategy);
    setStrategyParams(buildDefaultParams(strategy.config_schema));
    setStep(2);
  };

  const handleBack = () => {
    if (presetStrategy) {
      // Close modal instead of going back when strategy was preset
      onClose();
    } else {
      setStep(1);
      setSelectedStrategy(null);
    }
  };

  const handleParamChange = (key: string, value: unknown) => {
    setStrategyParams((prev) => ({ ...prev, [key]: value }));
  };

  const handleCreate = async () => {
    if (!selectedStrategy) return;
    if (!botName.trim()) {
      toast('Bot name is required', 'error');
      return;
    }

    setSubmitting(true);
    try {
      const strategyKey = selectedStrategy.name as 'grid' | 'dca' | 'trend_follower' | 'smc';
      const paramsWithEnabled = { enabled: true, ...strategyParams };

      const payload: BotCreateRequest = {
        name: botName.trim(),
        symbol: symbol.trim(),
        strategy: strategyKey,
        exchange_id: exchange,
        credentials_name: 'default',
        dry_run: dryRun,
        risk_management: { max_position_size: 1000 },
        [strategyKey]: paramsWithEnabled,
      };

      await botsApi.create(payload);
      toast(`Bot "${botName}" created successfully`, 'success');
      onCreated();
      onClose();
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast(detail ?? 'Failed to create bot', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const schemaProperties = selectedStrategy
    ? ((selectedStrategy.config_schema.properties ?? {}) as Record<string, SchemaProperty>)
    : {};

  const editableProperties = Object.entries(schemaProperties).filter(
    ([key]) => key !== 'enabled',
  );

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={step === 1 ? 'Select Strategy' : 'Configure Bot'}
      maxWidth="max-w-2xl"
    >
      {/* Step indicator — hidden when strategy is preset (step 1 is skipped) */}
      {!presetStrategy && (
        <div className="flex items-center gap-2 mb-5">
          {[1, 2].map((s) => (
            <div key={s} className="flex items-center gap-2">
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold transition-colors ${
                  step === s
                    ? 'bg-primary text-white'
                    : s < step
                    ? 'bg-profit text-white'
                    : 'bg-border text-text-muted'
                }`}
              >
                {s < step ? '✓' : s}
              </div>
              <span
                className={`text-xs ${step === s ? 'text-text font-medium' : 'text-text-muted'}`}
              >
                {s === 1 ? 'Strategy' : 'Settings'}
              </span>
              {s < 2 && <div className="w-6 h-px bg-border mx-1" />}
            </div>
          ))}
        </div>
      )}

      {/* Step 1: Strategy selection */}
      {step === 1 && (
        <div>
          {loadingStrategies ? (
            <div className="grid grid-cols-2 gap-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="p-4 rounded-xl border border-border bg-surface">
                  <div className="flex items-start gap-3">
                    <Skeleton className="h-8 w-8 rounded" />
                    <div className="flex-1">
                      <Skeleton className="h-4 w-20 mb-2" />
                      <Skeleton className="h-3 w-full" />
                      <Skeleton className="h-3 w-3/4 mt-1" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              {strategies.map((strategy) => (
                <StrategyCard
                  key={strategy.name}
                  strategy={strategy}
                  selected={selectedStrategy?.name === strategy.name}
                  disabled={strategy.name === 'smc'}
                  onClick={() => handleSelectStrategy(strategy)}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Step 2: Configuration */}
      {step === 2 && selectedStrategy && (
        <div className="space-y-4">
          {/* Basic settings */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-text-muted mb-1">Bot Name</label>
              <input
                type="text"
                value={botName}
                onChange={(e) => setBotName(e.target.value)}
                placeholder="my-grid-bot"
                className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">Trading Pair</label>
              <input
                type="text"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                placeholder="BTC/USDT"
                className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1">Exchange</label>
              <select
                value={exchange}
                onChange={(e) => setExchange(e.target.value)}
                className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm text-text focus:outline-none focus:border-primary"
              >
                <option value="binance">Binance</option>
                <option value="bybit">Bybit</option>
                <option value="okx">OKX</option>
              </select>
            </div>
            <div className="flex items-center">
              <Toggle
                checked={dryRun}
                onChange={setDryRun}
                label="Dry Run (simulation)"
              />
            </div>
          </div>

          {/* Strategy-specific params */}
          {editableProperties.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-3">
                {STRATEGY_DISPLAY_NAMES[selectedStrategy.name] ?? selectedStrategy.name} Parameters
              </p>
              <div className="max-h-64 overflow-y-auto space-y-3 pr-1">
                {editableProperties.map(([key, prop]) => (
                  <DynamicField
                    key={key}
                    name={key}
                    prop={prop}
                    value={strategyParams[key]}
                    onChange={(v) => handleParamChange(key, v)}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-between pt-2 border-t border-border">
            <Button variant="ghost" onClick={handleBack}>
              {presetStrategy ? '← Cancel' : '← Back'}
            </Button>
            <Button onClick={handleCreate} disabled={submitting || !botName.trim()}>
              {submitting ? 'Creating…' : 'Create Bot'}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
