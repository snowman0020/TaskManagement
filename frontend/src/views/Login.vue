<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    router.push({ name: 'board' })
  } catch (e) {
    error.value = e.response?.data?.detail || 'Login failed'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;">
    <form class="card" style="width:360px" @submit.prevent="submit">
      <h1 style="margin-top:0;text-align:center">Task Management</h1>
      <div class="field">
        <label>Username or Email</label>
        <input v-model="username" autocomplete="username" required />
      </div>
      <div class="field">
        <label>Password</label>
        <input v-model="password" type="password" autocomplete="current-password" required />
      </div>
      <button type="submit" style="width:100%" :disabled="loading">
        {{ loading ? 'Signing in…' : 'Sign in' }}
      </button>
      <p v-if="error" class="error">{{ error }}</p>
    </form>
  </div>
</template>
