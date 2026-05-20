import { invoke } from '@tauri-apps/api/core'

const SYSTEM_CONFIGS = ['default_llm', 'default_slm', 'default_vision']
const REQUIRED_CONFIGS = ['default_llm', 'default_slm']
const SYSTEM_DISPLAY_NAMES = {
  default_llm: '默认大模型',
  default_slm: '默认小脑模型',
  default_vision: '默认视觉模型',
}

export async function readLLMConfigs() {
  const config = await invoke('read_llm_config', { matrixWorldPath: (await invoke('get_config')).matrix_world_path })
  return config
}

export async function writeLLMConfigs(configs) {
  await invoke('save_llm_config', {
    matrixWorldPath: (await invoke('get_config')).matrix_world_path,
    llmConfig: configs,
  })
}

export function isSystemConfig(name) { return SYSTEM_CONFIGS.includes(name) }
export function isRequiredConfig(name) { return REQUIRED_CONFIGS.includes(name) }
export function getSystemDisplayName(name) { return SYSTEM_DISPLAY_NAMES[name] || name }
export function getSystemConfigs() { return [...SYSTEM_CONFIGS] }
export function getRequiredConfigs() { return [...REQUIRED_CONFIGS] }

export function buildConfigEntry(data) {
  return {
    url: (data.url || '').trim(),
    API_KEY: (data.api_key || '').trim(),
    model_name: (data.model_name || '').trim(),
  }
}

export function isConfigEmpty(entry) {
  if (!entry) return true
  return !entry.url && !entry.API_KEY && !entry.model_name
}

export function normalizeEntry(entry) {
  if (!entry) return { model_name: '', api_key: '', url: '' }
  return {
    model_name: entry.model_name || '',
    api_key: entry.API_KEY || entry.api_key || '',
    url: entry.url || '',
  }
}