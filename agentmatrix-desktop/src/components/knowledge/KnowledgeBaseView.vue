<script setup>
import { ref, onMounted } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import KBList from './KBList.vue'
import CreateKBWizard from './CreateKBWizard.vue'
import WikiView from './WikiView.vue'

const knowledgeStore = useKnowledgeStore()

// State: 'list', 'wizard', 'wiki'
const viewState = ref('list')

onMounted(async () => {
  await knowledgeStore.fetchKBs()
})

function onCreateNew() {
  viewState.value = 'wizard'
}

async function onSelectKB(kb) {
  await knowledgeStore.selectKB(kb.name)
  viewState.value = 'wiki'
}

function onWizardComplete() {
  viewState.value = 'wiki'
}

function onWizardCancel() {
  viewState.value = 'list'
}

function onBackToList() {
  knowledgeStore.clearCurrent()
  viewState.value = 'list'
  knowledgeStore.fetchKBs()
}
</script>

<template>
  <div class="kb-view">
    <KBList
      v-if="viewState === 'list'"
      @create="onCreateNew"
      @select="onSelectKB"
    />
    <CreateKBWizard
      v-else-if="viewState === 'wizard'"
      @complete="onWizardComplete"
      @cancel="onWizardCancel"
    />
    <WikiView
      v-else-if="viewState === 'wiki'"
      @back="onBackToList"
    />
  </div>
</template>

<style scoped>
.kb-view {
  width: 100%;
  height: 100%;
  display: flex;
  overflow: hidden;
}
</style>