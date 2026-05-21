import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './styles/fonts.css'
import './styles/tokens.css'
import './styles/global.css'
import './styles/animations.css'
import './styles/utilities.css'
import './styles/components.css'

document.documentElement.style.cssText += ';background:transparent!important;background-color:transparent!important'
document.body.style.cssText += ';background:transparent!important;background-color:transparent!important'

import SessionDetailPanel from './components/floating/SessionDetailPanel.vue'

const app = createApp(SessionDetailPanel)
const pinia = createPinia()
app.use(pinia)
app.mount('#detail-app')
