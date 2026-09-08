'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { llmApi, type LLMConfig } from '@/lib/api';
import { Checkbox, Field, TextInput } from '@/components/ui/Field';
import { toast } from '@/lib/toast';

const PROVIDERS = [
  { value: 'claude_code', label: 'Claude Code' },
  { value: 'local', label: 'Local (Ollama)' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'bedrock', label: 'AWS Bedrock' },
];

const SETUP_TOKEN_COMMAND = 'claude setup-token';

/**
 * Claude Code authenticates with an OAuth token rather than an API key, and the
 * token has to be minted from a terminal — Anthropic's browser login cannot be
 * driven from inside a web app. Signing in to Claude Code on your own machine
 * does not help the server either: that credential goes to the OS keychain,
 * which the backend cannot read. So the panel's job is to make the one manual
 * step obvious rather than to hide it.
 */
function ClaudeCodeTokenHelp({ hasToken }: { hasToken: boolean }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(SETUP_TOKEN_COMMAND);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error('Could not copy. Select the command and copy it manually.');
    }
  };

  return (
    <div className="flex flex-col gap-2 rounded border border-line bg-ground-sunken p-3">
      <p className="text-meta text-ink-subtle">
        {hasToken
          ? 'A token is saved. Replace it below if it stops working — tokens can be revoked or expire.'
          : 'Claude Code uses an OAuth token, not an API key. Run this on the machine you sign in from, then paste the result below.'}
      </p>
      <div className="flex items-center gap-2">
        <code className="flex-1 overflow-x-auto rounded bg-surface px-2 py-1 font-mono text-micro">
          {SETUP_TOKEN_COMMAND}
        </code>
        <button type="button" className="btn btn-secondary" onClick={copy}>
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <p className="text-meta text-ink-subtle">
        It opens a browser to sign in. Leave this blank to keep using a{' '}
        <code className="font-mono">CLAUDE_CODE_OAUTH_TOKEN</code> set in the server&rsquo;s
        environment. CV content is still sent to Anthropic, so consent below applies.
      </p>
    </div>
  );
}

export default function LLMSettingsPage() {
  const queryClient = useQueryClient();
  const config = useQuery({ queryKey: ['llm-config'], queryFn: () => llmApi.config() });

  const [form, setForm] = useState<Partial<LLMConfig> & { api_key?: string }>({});
  const [keyTouched, setKeyTouched] = useState(false);

  // Seed the form once the saved config arrives.
  useEffect(() => {
    if (config.data) setForm(config.data);
  }, [config.data]);

  const set = (patch: Partial<LLMConfig> & { api_key?: string }) =>
    setForm((f) => ({ ...f, ...patch }));

  const save = useMutation({
    mutationFn: () => {
      const payload = { ...form };
      // Never send an empty key: that would clear a stored one.
      if (!keyTouched || !payload.api_key) delete payload.api_key;
      // Base URL only means anything to the local provider.
      if (payload.provider !== 'local' || !payload.base_url?.trim()) {
        delete payload.base_url;
      }
      return llmApi.updateConfig(payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm-config'] });
      setKeyTouched(false);
      toast.success('Settings saved');
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : 'Could not save settings'),
  });

  const test = useMutation({
    mutationFn: () => llmApi.testConnection(),
    onSuccess: (result) => {
      if (result.success === false) {
        toast.error(result.message ?? result.detail ?? 'Connection failed');
      } else {
        toast.success(result.message ?? 'Connection works');
      }
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : 'Connection test failed'),
  });

  const isClaudeCode = form.provider === 'claude_code';
  // Only the local provider needs no credential at all. Claude Code takes an
  // OAuth token, stored in the same encrypted field as the API keys.
  const needsKey = Boolean(form.provider) && form.provider !== 'local';
  const credentialNoun = isClaudeCode ? 'token' : 'key';

  return (
    <div className="flex flex-col gap-5 max-w-2xl">
      <header className="flex flex-col gap-0.5">
        <h1 className="text-xl font-semibold tracking-[-0.01em]">AI assistant</h1>
        <p className="text-ui text-ink-muted">
          Powers grammar checks, job matching and CV tailoring. Nothing is sent anywhere
          until you enable it.
        </p>
      </header>

      {config.isLoading && <p className="text-ui text-ink-muted">Loading settings…</p>}

      {config.data && (
        <>
          <section className="card p-4 flex flex-col gap-3">
            <Field label="Provider">
              {(id) => (
                <select
                  id={id}
                  className="input"
                  value={form.provider ?? 'local'}
                  onChange={(e) => set({ provider: e.target.value })}
                >
                  {PROVIDERS.map((provider) => (
                    <option key={provider.value} value={provider.value}>
                      {provider.label}
                    </option>
                  ))}
                </select>
              )}
            </Field>

            <Field
              label="Model"
              hint={
                form.provider === 'claude_code'
                  ? 'An alias such as opus or sonnet, or a full model id.'
                  : undefined
              }
            >
              {(id) => (
                <TextInput
                  id={id}
                  value={form.model ?? ''}
                  placeholder={
                    form.provider === 'claude_code'
                      ? 'e.g. sonnet'
                      : 'e.g. llama2, gpt-4o, claude-opus-5'
                  }
                  onChange={(e) => set({ model: e.target.value })}
                />
              )}
            </Field>

            {isClaudeCode && <ClaudeCodeTokenHelp hasToken={config.data.has_api_key} />}

            {needsKey && (
              <Field
                label={isClaudeCode ? 'Claude Code token' : 'API key'}
                hint={
                  config.data.has_api_key && !keyTouched
                    ? `A ${credentialNoun} is stored. Leave blank to keep it.`
                    : 'Stored by the backend, never in the browser.'
                }
              >
                {(id) => (
                  <TextInput
                    id={id}
                    type="password"
                    autoComplete="off"
                    value={form.api_key ?? ''}
                    placeholder={config.data.has_api_key ? '••••••••' : ''}
                    onChange={(e) => {
                      setKeyTouched(true);
                      set({ api_key: e.target.value });
                    }}
                  />
                )}
              </Field>
            )}

            {form.provider === 'local' && (
              <Field
                label="Base URL"
                required
                hint="Where Ollama is listening. Required for the local provider."
              >
                {(id) => (
                  <TextInput
                    id={id}
                    value={form.base_url ?? ''}
                    placeholder="http://localhost:11434"
                    onChange={(e) => set({ base_url: e.target.value })}
                  />
                )}
              </Field>
            )}

            <div className="grid grid-cols-2 gap-3">
              <Field label="Temperature">
                {(id) => (
                  <TextInput
                    id={id}
                    type="number"
                    step="0.1"
                    min="0"
                    max="2"
                    value={form.temperature ?? 0.7}
                    onChange={(e) => set({ temperature: Number(e.target.value) })}
                  />
                )}
              </Field>
              <Field label="Max tokens">
                {(id) => (
                  <TextInput
                    id={id}
                    type="number"
                    min="1"
                    value={form.max_tokens ?? 1000}
                    onChange={(e) => set({ max_tokens: Number(e.target.value) })}
                  />
                )}
              </Field>
            </div>
          </section>

          <section className="card p-4 flex flex-col gap-3">
            <span className="rail-label">Consent</span>
            <p className="text-ui text-ink-muted">
              Enabling this sends CV content to the provider above when you use an AI
              feature. With the local provider it stays on your machine.
            </p>
            <Checkbox
              label="I consent to sending CV content to this provider"
              checked={Boolean(form.consent_given)}
              onChange={(e) => set({ consent_given: e.target.checked })}
            />
            <Checkbox
              label="Enable AI features"
              checked={Boolean(form.enabled)}
              onChange={(e) => set({ enabled: e.target.checked })}
            />
            {form.enabled && !form.consent_given && (
              <div className="alert alert-warning mb-0">
                AI features stay off until consent is given.
              </div>
            )}
          </section>

          <div className="flex items-center gap-2">
            <span className="font-mono text-micro text-ink-faint">
              {config.data.enabled ? 'Currently enabled' : 'Currently disabled'}
            </span>
            {form.provider === 'local' && !form.base_url?.trim() && (
              <span className="text-meta text-warning-600">
                Ollama needs a base URL before this will connect.
              </span>
            )}
            <div className="flex-1" />
            <button
              type="button"
              className="btn btn-secondary"
              disabled={test.isPending}
              onClick={() => test.mutate()}
            >
              {test.isPending ? 'Testing…' : 'Test connection'}
            </button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={save.isPending}
              onClick={() => save.mutate()}
            >
              {save.isPending ? 'Saving…' : 'Save settings'}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
