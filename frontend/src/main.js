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

// Default every input/textarea to autocomplete="off" — browser autofill is noise
// in this app (and intrusive on the admin user forms). Fields that opt in with
// their own autocomplete (login, new-password) keep it; this only fills the gaps,
// including for elements Vue mounts later.
function disableAutofill(root) {
  if (root.nodeType !== 1) return
  if (
    (root.tagName === 'INPUT' || root.tagName === 'TEXTAREA') &&
    !root.hasAttribute('autocomplete')
  ) {
    root.setAttribute('autocomplete', 'off')
  }
  root
    .querySelectorAll?.('input:not([autocomplete]),textarea:not([autocomplete])')
    .forEach((el) => el.setAttribute('autocomplete', 'off'))
}
disableAutofill(document.body)
new MutationObserver((mutations) => {
  for (const m of mutations) {
    for (const node of m.addedNodes) disableAutofill(node)
  }
}).observe(document.body, { childList: true, subtree: true })
