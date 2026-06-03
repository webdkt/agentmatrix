import { markRaw } from 'vue'
import WhiteboardView from '../WhiteboardView.vue'
import TodoView from '../TodoView.vue'
import TaskFilesPanel from '../TaskFilesPanel.vue'
import SiteKnowledgePanel from './SiteKnowledgePanel.vue'

export const panelRegistry = {
  whiteboard: {
    id: 'whiteboard',
    label: 'Whiteboard',
    icon: 'clipboard',
    component: markRaw(WhiteboardView),
    requires: [],
  },
  todo: {
    id: 'todo',
    label: 'Todo',
    icon: 'list-checks',
    component: markRaw(TodoView),
    requires: [],
  },
  files: {
    id: 'files',
    label: 'Files',
    icon: 'folder',
    component: markRaw(TaskFilesPanel),
    requires: [],
  },
  siteKnowledge: {
    id: 'siteKnowledge',
    label: 'Site Knowledge',
    icon: 'book-open',
    component: markRaw(SiteKnowledgePanel),
    requires: { skills: ['browser_automation'] },
  },
}

export function resolvePanels(skills = []) {
  return Object.values(panelRegistry).filter(panel => {
    if (!panel.requires || panel.requires.length === 0) return true
    if (panel.requires.skills) {
      return panel.requires.skills.some(s => skills.includes(s))
    }
    return false
  })
}