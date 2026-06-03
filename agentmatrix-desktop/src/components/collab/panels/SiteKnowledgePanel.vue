<script setup>
import { ref } from 'vue'
import { useSiteKnowledge } from '@/composables/useSiteKnowledge'
import { useSessionStore } from '@/stores/session'
import { sessionAPI } from '@/api/session'
import { addPendingEmail, removePendingEmail } from '@/composables/usePendingEmails'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  agentName: { type: String, required: true },
  sessionId: { type: String, required: true },
})

const sessionStore = useSessionStore()
const sk = useSiteKnowledge({ agentName: () => props.agentName })

const expandedSites = ref({})
const expandedProcesses = ref({})
const siteFiles = ref({})
const processFiles = ref({})

const contextMenu = ref({ show: false, x: 0, y: 0, target: null })

function toggleSite(dirname) {
  expandedSites.value[dirname] = !expandedSites.value[dirname]
  if (expandedSites.value[dirname] && !siteFiles.value[dirname]) {
    loadSiteFiles(dirname)
  }
}

function toggleProcess(site, processDir) {
  const key = `${site}/${processDir}`
  expandedProcesses.value[key] = !expandedProcesses.value[key]
  if (expandedProcesses.value[key] && !processFiles.value[key]) {
    loadProcessFiles(site, processDir)
  }
}

async function loadSiteFiles(dirname) {
  const site = sk.sites.value.find(s => s.dirname === dirname)
  if (!site) return
  const result = await sk.loadSiteProcesses(site)
  siteFiles.value[dirname] = result
}

async function loadProcessFiles(siteDirname, processDirName) {
  const site = sk.sites.value.find(s => s.dirname === siteDirname)
  if (!site) return
  const result = await sk.loadProcessSteps(site, processDirName)
  processFiles.value[`${siteDirname}/${processDirName}`] = result
}

function onContextMenu(e, target) {
  e.preventDefault()
  e.stopPropagation()
  contextMenu.value = { show: true, x: e.clientX, y: e.clientY, target }
}

function closeContextMenu() {
  contextMenu.value = { show: false, x: 0, y: 0, target: null }
}

async function openFolder() {
  const target = contextMenu.value.target
  closeContextMenu()
  if (!target) return
  await sk.revealPath(target.path)
}

async function loadKnowledge() {
  const target = contextMenu.value.target
  closeContextMenu()
  if (!target) return

  const siteKey = target.siteKey
  const session = sessionStore.currentSession
  if (!session) return

  const emailData = {
    recipient: props.agentName,
    subject: '',
    body: `Load Site Knowledge: ${siteKey}`,
    task_id: session.task_id || session.session_id,
    in_reply_to: session.last_email_id || undefined,
    recipient_session_id: session.agent_session_id || undefined,
  }

  const placeholderObj = addPendingEmail(session.session_id, emailData)
  try {
    await sessionAPI.sendEmail(session.session_id, emailData)
    removePendingEmail(placeholderObj.id)
  } catch (e) {
    console.error('[SiteKnowledge] Failed to send load knowledge message:', e)
    removePendingEmail(placeholderObj.id)
  }
}
</script>

<template>
  <div class="sk-panel" @click="closeContextMenu">
    <div v-if="sk.isInitialLoad.value" class="sk-panel__empty">Loading...</div>
    <div v-else-if="sk.error.value" class="sk-panel__empty sk-panel__empty--error">
      Failed to load site knowledge
    </div>
    <div v-else-if="sk.sites.value.length === 0" class="sk-panel__empty">
      No site knowledge found
    </div>
    <div v-else class="sk-panel__tree">
      <div v-for="site in sk.sites.value" :key="site.dirname" class="sk-panel__site">
        <div
          class="sk-panel__site-header"
          @click="toggleSite(site.dirname)"
          @contextmenu="onContextMenu($event, { type: 'site', siteKey: site.site_key, path: `${sk.rootDir.value}/${site.dirname}` })"
        >
          <MIcon name="chevron-right" class="sk-panel__chevron" :class="{ 'sk-panel__chevron--open': expandedSites[site.dirname] }" />
          <MIcon name="globe" class="sk-panel__icon" />
          <span class="sk-panel__label" :title="site.url_prefix">{{ site.desc }}</span>
        </div>
        <div v-if="expandedSites[site.dirname]" class="sk-panel__site-children">
          <div
            v-for="file in (siteFiles[site.dirname]?.files || [])"
            :key="file.path"
            class="sk-panel__file-item"
            @contextmenu="onContextMenu($event, { type: 'file', siteKey: site.site_key, path: file.path })"
          >
            <MIcon name="file-text" class="sk-panel__file-icon" />
            <span class="sk-panel__file-name">{{ file.name }}</span>
          </div>
          <div
            v-for="proc in (siteFiles[site.dirname]?.processes || [])"
            :key="proc.name"
            class="sk-panel__process"
          >
            <div
              class="sk-panel__process-header"
              @click="toggleProcess(site.dirname, proc.name)"
              @contextmenu="onContextMenu($event, { type: 'process', siteKey: site.site_key, path: proc.path })"
            >
              <MIcon name="chevron-right" class="sk-panel__chevron" :class="{ 'sk-panel__chevron--open': expandedProcesses[`${site.dirname}/${proc.name}`] }" />
              <MIcon name="folder" class="sk-panel__icon" />
              <span class="sk-panel__label">{{ proc.name }}</span>
            </div>
            <div v-if="expandedProcesses[`${site.dirname}/${proc.name}`]" class="sk-panel__process-children">
              <div
                v-for="step in (processFiles[`${site.dirname}/${proc.name}`]?.steps || [])"
                :key="step.path"
                class="sk-panel__file-item"
                @contextmenu="onContextMenu($event, { type: 'file', siteKey: site.site_key, path: step.path })"
              >
                <MIcon name="file-text" class="sk-panel__file-icon" />
                <span class="sk-panel__file-name">{{ step.name }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Context Menu -->
    <div
      v-if="contextMenu.show"
      class="sk-panel__context-menu"
      :style="{ left: `${contextMenu.x}px`, top: `${contextMenu.y}px` }"
      @click.stop
    >
      <button class="sk-panel__menu-item" @click="openFolder">
        <MIcon name="folder" />
        <span>Open Folder</span>
      </button>
      <button
        v-if="contextMenu.target?.type === 'site' || contextMenu.target?.type === 'process'"
        class="sk-panel__menu-item"
        @click="loadKnowledge"
      >
        <MIcon name="book-open" />
        <span>Load Knowledge</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.sk-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sk-panel__empty {
  padding: 16px;
  color: var(--text-tertiary);
  font-size: 12px;
  text-align: center;
}

.sk-panel__empty--error {
  color: var(--error);
}

.sk-panel__tree {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}

.sk-panel__site-header,
.sk-panel__process-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-secondary);
  transition: background 0.1s;
}

.sk-panel__site-header:hover,
.sk-panel__process-header:hover {
  background: var(--surface-base);
}

.sk-panel__chevron {
  font-size: 10px;
  opacity: 0.4;
  transition: transform 0.15s;
  flex-shrink: 0;
}

.sk-panel__chevron--open {
  transform: rotate(90deg);
}

.sk-panel__icon {
  font-size: 13px;
  opacity: 0.6;
  flex-shrink: 0;
}

.sk-panel__label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}



.sk-panel__site-children,
.sk-panel__process-children {
  padding-left: 16px;
}

.sk-panel__file-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px 3px 22px;
  font-size: 11px;
  color: var(--text-tertiary);
  cursor: default;
}

.sk-panel__file-item:hover {
  color: var(--text-secondary);
}

.sk-panel__file-icon {
  font-size: 12px;
  flex-shrink: 0;
}

.sk-panel__file-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sk-panel__context-menu {
  position: fixed;
  background: white;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-sm);
  min-width: 160px;
  z-index: var(--z-dropdown);
  overflow: hidden;
  animation: skMenuFadeIn 0.15s ease-out;
}

@keyframes skMenuFadeIn {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}

.sk-panel__menu-item {
  width: 100%;
  padding: 7px 12px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  text-align: left;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
}

.sk-panel__menu-item:hover {
  background: var(--surface-hover);
}

.sk-panel__menu-item .m-icon {
  font-size: 13px;
}
</style>