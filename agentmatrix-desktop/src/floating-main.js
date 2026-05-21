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

import FloatingAgentPanel from './components/floating/FloatingAgentPanel.vue'

const app = createApp(FloatingAgentPanel)
const pinia = createPinia()
app.use(pinia)
app.mount('#floating-app')
