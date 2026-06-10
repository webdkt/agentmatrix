<script setup>
import { ref, computed, watch } from 'vue'
import { useMatrixStore } from '@/stores/matrix'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  sections: { type: Object, required: true },  // {section: {key: {content, last_modified}}}
  isLoaded: { type: Boolean, default: false },
  agentName: { type: String, default: '' },
})

const emit = defineEmits(['save'])

const matrixStore = useMatrixStore()

// ---- 编辑弹窗状态 ----
const isEditing = ref(false)
const editSections = ref({})  // 深拷贝编辑副本
const agentWasPausedByUs = ref(false)

const sectionNames = computed(() => Object.keys(props.sections))

// ---- 打开编辑 ----
function openEditor() {
  if (!props.agentName) return
  // 深拷贝
  editSections.value = JSON.parse(JSON.stringify(props.sections))
  isEditing.value = true
  try {
    matrixStore.pauseAgent(props.agentName)
    agentWasPausedByUs.value = true
  } catch (e) {
    console.error('Failed to pause agent:', e)
  }
}

// ---- 关闭：resume agent ----
async function closeEditor() {
  isEditing.value = false
  if (agentWasPausedByUs.value && props.agentName) {
    try { await matrixStore.resumeAgent(props.agentName) } catch (e) { console.error(e) }
    agentWasPausedByUs.value = false
  }
}

// ---- 保存（不关闭）----
function handleSave() {
  emit('save', JSON.parse(JSON.stringify(editSections.value)))
}

// ---- 保存并关闭 ----
function handleSaveAndClose() {
  emit('save', JSON.parse(JSON.stringify(editSections.value)))
  closeEditor()
}

// ---- 取消 ----
function handleCancel() {
  closeEditor()
}

// ---- 编辑操作 ----
function addSection() {
  const name = `section_${Object.keys(editSections.value).length + 1}`
  editSections.value[name] = {}
}

function deleteSection(sec) {
  delete editSections.value[sec]
}

function renameSection(oldName) {
  // 简单实现：直接改 key（Vue 响应式需要重新赋值）
  // 这里用一个 hack：先删除再添加
}

function addEntry(sec) {
  const key = `item_${Object.keys(editSections.value[sec] || {}).length + 1}`
  if (!editSections.value[sec]) editSections.value[sec] = {}
  editSections.value[sec][key] = { content: '', last_modified: new Date().toISOString() }
}

function deleteEntry(sec, key) {
  if (editSections.value[sec]) {
    delete editSections.value[sec][key]
    if (!Object.keys(editSections.value[sec]).length) delete editSections.value[sec]
  }
}

// 编辑中的 sections 列表（用于 v-for）
const editSectionList = computed(() => Object.keys(editSections.value))
</script>

<template>
  <div class="whiteboard-view" @dblclick="openEditor">
    <!-- 加载中 -->
    <div v-if="!isLoaded" class="whiteboard-view__loading">
      <span class="animate-spin"><MIcon name="loader" /></span>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!sectionNames.length" class="whiteboard-view__empty">
      无内容
    </div>

    <!-- 只读展示 -->
    <div v-else class="whiteboard-view__content">
      <div v-for="sec in sectionNames" :key="sec" class="wb-section">
        <div class="wb-section__header">
          <span class="wb-section__dot"></span>
          <span class="wb-section__name">{{ sec }}</span>
        </div>
        <div class="wb-section__entries">
          <div v-for="(entry, key) in sections[sec]" :key="key" class="wb-entry">
            <span class="wb-entry__key">{{ key }}</span>
            <span class="wb-entry__val">{{ entry.content }}</span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="isLoaded && sectionNames.length" class="whiteboard-view__hint">双击编辑</div>

    <!-- ========== 编辑弹窗 ========== -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="isEditing" class="wb-editor-overlay" @click.self="handleCancel">
          <div class="wb-editor">
            <!-- Banner -->
            <div class="wb-editor__banner">
              <MIcon name="player-pause" />
              <span>Agent Paused — 关闭此窗口可恢复</span>
            </div>

            <!-- Header -->
            <div class="wb-editor__header">
              <span class="wb-editor__title">Whiteboard</span>
              <div class="wb-editor__header-actions">
                <button class="wb-editor__btn wb-editor__btn--save" @click="handleSave">
                  <MIcon name="save" /> 保存
                </button>
                <button class="wb-editor__btn wb-editor__btn--primary" @click="handleSaveAndClose">
                  <MIcon name="check" /> 保存并关闭
                </button>
                <button class="wb-editor__btn wb-editor__btn--ghost" @click="handleCancel">
                  取消
                </button>
              </div>
            </div>

            <!-- Body -->
            <div class="wb-editor__body">
              <div v-for="sec in editSectionList" :key="sec" class="wb-edit-section">
                <div class="wb-edit-section__header">
                  <input
                    class="wb-edit-section__name"
                    :value="sec"
                    @change="(e) => {
                      const newName = e.target.value.trim()
                      if (newName && newName !== sec) {
                        editSections[newName] = editSections[sec]
                        delete editSections[sec]
                      }
                    }"
                  />
                  <button class="wb-edit-section__del" @click="deleteSection(sec)" title="删除分组">
                    <MIcon name="trash-2" />
                  </button>
                </div>
                <div class="wb-edit-section__entries">
                  <div v-for="(entry, ekey) in editSections[sec]" :key="ekey" class="wb-edit-entry">
                    <input
                      class="wb-edit-entry__key"
                      :value="ekey"
                      @change="(e) => {
                        const newName = e.target.value.trim()
                        if (newName && newName !== ekey) {
                          const secData = editSections[sec]
                          secData[newName] = entry
                          delete secData[ekey]
                        }
                      }"
                      placeholder="key"
                    />
                    <textarea class="wb-edit-entry__content" v-model="entry.content" placeholder="内容" rows="2" />
                    <button class="wb-edit-entry__del" @click="deleteEntry(sec, ekey)">
                      <MIcon name="x" />
                    </button>
                  </div>
                  <button class="wb-edit-add-btn" @click="addEntry(sec)">
                    <MIcon name="plus" /> 添加条目
                  </button>
                </div>
              </div>

              <button class="wb-edit-add-section" @click="addSection">
                <MIcon name="plus" /> 添加分组
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.whiteboard-view {
  padding: 10px 14px;
  min-height: 40px;
  user-select: none;
}
.whiteboard-view__loading {
  display: flex; align-items: center; justify-content: center;
  padding: 20px; color: var(--text-tertiary); font-size: 13px;
}
.whiteboard-view__empty {
  color: var(--text-tertiary); font-size: 13px;
  text-align: center; padding: 24px 0; font-style: italic;
}
.whiteboard-view__hint {
  margin-top: 10px; font-size: 11px;
  color: var(--text-quaternary); text-align: center; opacity: 0.5;
}

/* ---- 只读展示：紧凑列表 ---- */
.whiteboard-view__content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.wb-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.wb-section__header {
  display: flex;
  align-items: center;
  gap: 7px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--border-light);
}

.wb-section__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  flex-shrink: 0;
}

.wb-section__name {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-secondary);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.wb-section__entries {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding-left: 13px;  /* align with dot center */
}

.wb-entry {
  display: flex;
  align-items: baseline;
  gap: 6px;
  line-height: 1.5;
  font-size: 13px;
}

.wb-entry__key {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-tertiary);
  white-space: nowrap;
  flex-shrink: 0;
  min-width: 0;
}
.wb-entry__key::after {
  content: '';
  display: inline-block;
  width: 2px;
}

.wb-entry__val {
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
}

/* ========== 编辑弹窗 ========== */
.wb-editor-overlay {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0, 0, 0, 0.45);
  display: flex; align-items: center; justify-content: center;
}
.wb-editor {
  width: 680px; max-height: 85vh;
  background: var(--surface-base);
  border-radius: 12px;
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.25);
  display: flex; flex-direction: column;
  overflow: hidden;
}
.wb-editor__banner {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 16px;
  background: #fef3c7;
  color: #92400e;
  font-size: 12px; font-weight: 500;
}
.wb-editor__header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-light);
}
.wb-editor__title {
  font-size: 15px; font-weight: 700; color: var(--text-primary);
}
.wb-editor__header-actions {
  display: flex; gap: 6px;
}

/* ---- 按钮 ---- */
.wb-editor__btn {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 5px 12px; border-radius: 6px;
  font-size: 12px; font-weight: 600;
  cursor: pointer; border: 1px solid transparent;
  transition: all 0.12s;
}
.wb-editor__btn--ghost {
  background: transparent; color: var(--text-secondary);
  border-color: var(--border);
}
.wb-editor__btn--ghost:hover { background: var(--surface-hover); }
.wb-editor__btn--save {
  background: var(--surface-secondary); color: var(--text-primary);
  border-color: var(--border);
}
.wb-editor__btn--save:hover { background: var(--surface-hover); }
.wb-editor__btn--primary {
  background: var(--accent); color: white; border-color: var(--accent);
}
.wb-editor__btn--primary:hover { filter: brightness(1.1); }

/* ---- 编辑主体 ---- */
.wb-editor__body {
  flex: 1; overflow-y: auto;
  padding: 16px;
  display: flex; flex-direction: column; gap: 14px;
}

.wb-edit-section {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  overflow: hidden;
}
.wb-edit-section__header {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 10px;
  background: color-mix(in srgb, var(--accent) 8%, transparent);
}
.wb-edit-section__name {
  flex: 1; border: none; background: transparent;
  font-size: 13px; font-weight: 700; color: var(--accent);
  outline: none; padding: 2px 4px; border-radius: 4px;
}
.wb-edit-section__name:focus { background: var(--surface-base); }
.wb-edit-section__del {
  width: 26px; height: 26px;
  border: none; background: transparent; border-radius: 4px;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  color: var(--text-quaternary); font-size: 13px;
}
.wb-edit-section__del:hover { background: #fee2e2; color: #dc2626; }

.wb-edit-section__entries {
  padding: 8px 10px;
  display: flex; flex-direction: column; gap: 8px;
}

.wb-edit-entry {
  display: flex; gap: 6px; align-items: flex-start;
  padding: 6px; border-radius: 6px;
  background: var(--surface-secondary);
}
.wb-edit-entry__key {
  width: 120px; flex-shrink: 0;
  border: 1px solid var(--border-light); border-radius: 4px;
  padding: 4px 6px; font-size: 12px; font-weight: 600;
  background: var(--surface-base); outline: none;
}
.wb-edit-entry__key:focus { border-color: var(--accent); }
.wb-edit-entry__content {
  flex: 1;
  border: 1px solid var(--border-light); border-radius: 4px;
  padding: 4px 6px; font-size: 12px;
  background: var(--surface-base); outline: none;
  resize: vertical; min-height: 32px;
}
.wb-edit-entry__content:focus { border-color: var(--accent); }
.wb-edit-entry__del {
  width: 24px; height: 24px; flex-shrink: 0;
  border: none; background: transparent; border-radius: 4px;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  color: var(--text-quaternary); font-size: 12px; margin-top: 2px;
}
.wb-edit-entry__del:hover { background: #fee2e2; color: #dc2626; }

.wb-edit-add-btn {
  display: flex; align-items: center; justify-content: center; gap: 4px;
  padding: 4px; border: 1px dashed var(--border); border-radius: 4px;
  background: transparent; color: var(--text-tertiary); font-size: 11px;
  cursor: pointer; transition: all 0.12s;
}
.wb-edit-add-btn:hover { color: var(--accent); border-color: var(--accent); background: color-mix(in srgb, var(--accent) 5%, transparent); }

.wb-edit-add-section {
  display: flex; align-items: center; justify-content: center; gap: 4px;
  padding: 8px; border: 1px dashed var(--border); border-radius: 6px;
  background: transparent; color: var(--text-tertiary); font-size: 12px;
  cursor: pointer; transition: all 0.12s;
}
.wb-edit-add-section:hover { color: var(--accent); border-color: var(--accent); background: color-mix(in srgb, var(--accent) 5%, transparent); }

/* ---- Animations ---- */
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
