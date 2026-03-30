<template>
  <div class="resources-tab">
    <div class="resources-grid">
      <!-- Open Browser -->
      <button class="resource-card" @click="openBrowser">
        <div class="resource-card__icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="12" cy="12" r="10"/>
            <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
          </svg>
        </div>
        <div class="resource-card__label">{{ $t('matrix.resources.browser') }}</div>
        <div class="resource-card__desc">{{ $t('matrix.resources.browserDesc') }}</div>
      </button>

      <!-- Open Computer -->
      <button class="resource-card resource-card--disabled" disabled>
        <div class="resource-card__icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <rect x="2" y="3" width="20" height="14" rx="2"/>
            <path d="M8 21h8M12 17v4"/>
          </svg>
        </div>
        <div class="resource-card__label">{{ $t('matrix.resources.computer') }}</div>
        <div class="resource-card__desc">Coming soon</div>
      </button>

      <!-- Open Home Folder -->
      <button class="resource-card" @click="openHomeFolder">
        <div class="resource-card__icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
        </div>
        <div class="resource-card__label">{{ $t('matrix.resources.homeFolder') }}</div>
        <div class="resource-card__desc">{{ $t('matrix.resources.homeFolderDesc') }}</div>
      </button>

      <!-- Open Work Files -->
      <button class="resource-card" @click="openWorkFiles">
        <div class="resource-card__icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            <path d="M12 11v6M9 14h6"/>
          </svg>
        </div>
        <div class="resource-card__label">{{ $t('matrix.resources.sessionFolder') }}</div>
        <div class="resource-card__desc">{{ $t('matrix.resources.sessionFolderDesc') }}</div>
      </button>

      <!-- Open Skills Folder -->
      <button class="resource-card" @click="openSkillsFolder">
        <div class="resource-card__icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M12 2L2 7l10 5 10-5-10-5z"/>
            <path d="M2 17l10 5 10-5"/>
            <path d="M2 12l10 5 10-5"/>
          </svg>
        </div>
        <div class="resource-card__label">{{ $t('matrix.resources.skillsFolder') }}</div>
        <div class="resource-card__desc">{{ $t('matrix.resources.skillsFolderDesc') }}</div>
      </button>
    </div>
  </div>
</template>

<script setup>
import { invoke } from '@tauri-apps/api/core'

const props = defineProps({
  agentName: {
    type: String,
    required: true
  }
})

async function getWorldPath() {
  const config = await invoke('get_config')
  return config.matrix_world_path
}

async function openBrowser() {
  try {
    const worldPath = await getWorldPath()
    const profilePath = `${worldPath}/.matrix/browser_profile/${props.agentName}`
    await invoke('open_browser_with_profile', { profilePath })
  } catch (error) {
    console.error('Failed to open browser:', error)
  }
}

async function openHomeFolder() {
  try {
    const worldPath = await getWorldPath()
    const path = `${worldPath}/workspace/agent_files/${props.agentName}/home`
    await invoke('open_folder', { path })
  } catch (error) {
    console.error('Failed to open home folder:', error)
  }
}

async function openWorkFiles() {
  try {
    const worldPath = await getWorldPath()
    const path = `${worldPath}/workspace/agent_files/${props.agentName}/work_files`
    await invoke('open_folder', { path })
  } catch (error) {
    console.error('Failed to open work files:', error)
  }
}

async function openSkillsFolder() {
  try {
    const worldPath = await getWorldPath()
    const path = `${worldPath}/workspace/agent_files/${props.agentName}/home/SKILLS`
    await invoke('open_folder', { path })
  } catch (error) {
    console.error('Failed to open skills folder:', error)
  }
}
</script>

<style scoped>
.resources-tab {
  padding: var(--spacing-lg);
  height: 100%;
  overflow-y: auto;
}

.resources-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-md);
}

.resources-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-md);
}

.resource-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: var(--spacing-lg);
  background: var(--parchment-50);
  border: 1px solid var(--parchment-300);
  border-radius: 2px;
  cursor: pointer;
  transition: background-color 0.15s, border-color 0.15s;
  text-align: left;
}

.resource-card:hover {
  background: var(--parchment-200);
  border-color: var(--ink-300);
}

.resource-card--disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.resource-card--disabled:hover {
  background: var(--parchment-50);
  border-color: var(--parchment-300);
}

.resource-card__icon {
  width: 32px;
  height: 32px;
  color: var(--ink-500);
  margin-bottom: var(--spacing-md);
  transition: color 0.15s;
}

.resource-card:hover .resource-card__icon {
  color: var(--accent);
}

.resource-card__label {
  font-family: var(--font-sans);
  font-size: 14px;
  font-weight: 600;
  color: var(--ink-900);
  margin-bottom: 4px;
}

.resource-card__desc {
  font-family: var(--font-sans);
  font-size: 12px;
  color: var(--ink-500);
}
</style>
