import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './styles/global.css'
import i18n from './i18n'
import App from './App.vue'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(i18n)
app.mount('#app')
