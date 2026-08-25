export function createConfiguredSupabaseClient() {
  const config = globalThis.FISH_SUPABASE_CONFIG;
  const sdk = globalThis.supabase;
  if (!config?.url || !config?.publishableKey || !sdk?.createClient) return null;
  return sdk.createClient(config.url, config.publishableKey);
}

export function isSupabaseConfigured() {
  return Boolean(createConfiguredSupabaseClient());
}
