import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './assets/main.css'
import { useTheme } from './composables/useTheme'

// Resolve and apply the theme before mount so the correct palette is in place.
useTheme()

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
