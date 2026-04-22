import { computed, toValue } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { useAgentStore } from '@/stores/agent'

/**
 * Collab file composable — extracted from CollabPanel.vue
 * Reads the current collabring file from the agent store and provides open action.
 * agentName can be a ref, computed, or getter function.
 */
export function useCollabFile({ agentName } = {}) {
  const agentStore = useAgentStore()

  const collabFile = computed(() => {
    const name = toValue(agentName)
    if (!name) return null
    return agentStore.getAgent(name)?.current_collab_file || null
  })

  const collabFileName = computed(() => {
    if (!collabFile.value) return null
    const parts = collabFile.value.split('/')
    return parts[parts.length - 1]
  })

  const openCollabFile = async () => {
    if (!collabFile.value) return
    try {
      await invoke('open_folder', { path: collabFile.value })
    } catch (err) {
      console.error('Failed to open collab file:', err)
    }
  }

  return {
    collabFile,
    collabFileName,
    openCollabFile,
  }
}
