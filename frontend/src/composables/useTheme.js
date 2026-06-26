import { ref } from 'vue'

const STORAGE_KEY = 'theme'
const theme = ref('light')
let initialized = false

function safeGet(key) {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function safeSet(key, value) {
  try {
    localStorage.setItem(key, value)
  } catch {
    /* storage blocked — keep in-memory only */
  }
}

function systemPrefersDark() {
  try {
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  } catch {
    return false
  }
}

function apply(value) {
  document.documentElement.dataset.theme = value
}

function setTheme(value) {
  theme.value = value
  apply(value)
  safeSet(STORAGE_KEY, value)
}

function toggle() {
  setTheme(theme.value === 'dark' ? 'light' : 'dark')
}

// Initialize once: saved choice wins; otherwise follow the OS preference and
// keep following it only until the user makes an explicit choice.
function init() {
  if (initialized) return
  initialized = true

  const saved = safeGet(STORAGE_KEY)
  theme.value = saved || (systemPrefersDark() ? 'dark' : 'light')
  apply(theme.value)

  try {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    mq.addEventListener('change', (e) => {
      if (!safeGet(STORAGE_KEY)) {
        theme.value = e.matches ? 'dark' : 'light'
        apply(theme.value)
      }
    })
  } catch {
    /* matchMedia unavailable — stay on the resolved theme */
  }
}

export function useTheme() {
  init()
  return { theme, setTheme, toggle }
}
