<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

// refresh cached role/profile so admin-side role changes take effect without re-login
onMounted(() => auth.refresh())

function logout() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">📋 TaskFlow</div>
      <router-link class="nav-link" :to="{ name: 'board' }">Board</router-link>
      <router-link class="nav-link" :to="{ name: 'dashboard' }">Dashboard</router-link>
      <router-link v-if="auth.isManager" class="nav-link" :to="{ name: 'admin' }">
        Admin
      </router-link>
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
</template>
