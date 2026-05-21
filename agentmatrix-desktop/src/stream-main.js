import { createApp } from 'vue'
import { createPinia } from 'pinia'
import i18n from './i18n'
import './styles/fonts.css'
import './styles/tokens.css'
import './styles/global.css'
import './styles/animations.css'
import './styles/utilities.css'
import './styles/components.css'

document.documentElement.style.cssText += ';background:transparent!important;background-color:transparent!important'
document.body.style.cssText += ';background:transparent!important;background-color:transparent!important'

import FloatingStream from './components/floating/FloatingStream.vue'

const app = createApp(FloatingStream)
const pinia = createPinia()
app.use(pinia)
app.use(i18n)
app.mount('#stream-app')
