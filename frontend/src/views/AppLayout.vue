<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import ThemeToggle from '@/components/ThemeToggle.vue'
import NotificationBell from '@/components/NotificationBell.vue'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const SIDEBAR_KEY = 'sidebarOpen'

function isMobile() {
  try {
    return window.matchMedia('(max-width: 768px)').matches
  } catch {
    return false
  }
}

function savedOpen() {
  try {
    const v = localStorage.getItem(SIDEBAR_KEY)
    return v === null ? true : v === 'true'
  } catch {
    return true
  }
}

// Desktop: remembered open/collapsed state. Mobile: always start closed (drawer).
const sidebarOpen = ref(isMobile() ? false : savedOpen())

function toggleSidebar() {
  sidebarOpen.value = !sidebarOpen.value
  // Only persist the desktop preference — mobile is a transient drawer.
  if (!isMobile()) {
    try {
      localStorage.setItem(SIDEBAR_KEY, String(sidebarOpen.value))
    } catch {
      /* ignore */
    }
  }
}

function closeSidebar() {
  sidebarOpen.value = false
}

// Close the drawer after navigating on mobile.
watch(
  () => route.fullPath,
  () => {
    if (isMobile()) sidebarOpen.value = false
  }
)

// Reset the sidebar correctly when crossing the mobile breakpoint, so a desktop
// "open" state doesn't render as an open drawer covering the content on resize.
let mql = null
function onBreakpoint(e) {
  sidebarOpen.value = e.matches ? false : savedOpen()
}

onMounted(() => {
  // refresh cached role/profile so admin-side role changes take effect without re-login
  auth.refresh()
  try {
    mql = window.matchMedia('(max-width: 768px)')
    mql.addEventListener('change', onBreakpoint)
  } catch {
    /* matchMedia unavailable — skip the breakpoint listener */
  }
})

onUnmounted(() => {
  try {
    mql?.removeEventListener('change', onBreakpoint)
  } catch {
    /* ignore */
  }
})

function logout() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="app-shell" :class="{ 'sidebar-collapsed': !sidebarOpen }">
    <header class="topbar">
      <button
        class="icon-btn hamburger"
        type="button"
        aria-label="Toggle menu"
        @click="toggleSidebar"
      >
        ☰
      </button>
      <div class="brand">📋 TaskFlow</div>
      <div class="spacer" />
      <NotificationBell />
      <ThemeToggle />
    </header>

    <div class="shell-body">
      <div v-if="sidebarOpen" class="drawer-backdrop" @click="closeSidebar" />

      <aside class="sidebar">
        <nav>
          <router-link class="nav-link" :to="{ name: 'board' }">Board</router-link>
          <router-link class="nav-link" :to="{ name: 'dashboard' }">Dashboard</router-link>
          <router-link v-if="auth.isManager" class="nav-link" :to="{ name: 'admin' }">
            Admin
          </router-link>
        </nav>
        <div class="spacer" />
        <div class="user-box">
          <strong>{{ auth.user?.full_name || auth.user?.username }}</strong><br />
          <span>{{ auth.user?.role }}</span>
        </div>
        <button class="ghost" @click="logout">Logout</button>
      </aside>

      <main class="main">
        <router-view />
      </main>
    </div>
  </div>
</template>
