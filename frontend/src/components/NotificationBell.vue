<script setup>
import { ref, onMounted } from 'vue'
import client from '@/api/client'
import { formatDateTime } from '@/utils/datetime'

const open = ref(false)
const items = ref([])
const unread = ref(0)

async function load() {
  try {
    const { data } = await client.get('/api/notifications')
    items.value = data.items
    unread.value = data.unread
  } catch {
    /* ignore — bell just stays empty */
  }
}

async function toggle() {
  open.value = !open.value
  if (open.value) {
    await load()
    if (unread.value > 0) {
      try {
        await client.post('/api/notifications/read-all')
      } catch {
        /* ignore */
      }
      unread.value = 0
      items.value = items.value.map((n) => ({ ...n, read: true }))
    }
  }
}

onMounted(load)
</script>

<template>
  <div class="notif">
    <button class="icon-btn" type="button" :title="unread + ' unread'" @click="toggle">
      🔔<span v-if="unread" class="notif-badge">{{ unread > 99 ? '99+' : unread }}</span>
    </button>

    <div v-if="open" class="notif-backdrop" @click="open = false" />
    <div v-if="open" class="notif-panel">
      <div class="notif-head">Notifications</div>
      <p v-if="!items.length" class="hint">No notifications yet.</p>
      <div
        v-for="n in items"
        :key="n.id"
        class="notif-item"
        :class="{ unread: !n.read }"
      >
        <div class="n-msg">{{ n.message }}</div>
        <div class="n-time">{{ formatDateTime(n.created_at) }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.notif { position: relative; }
.notif-badge {
  position: absolute;
  top: -2px;
  right: -2px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  background: var(--danger);
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  line-height: 16px;
  text-align: center;
}
.notif-backdrop { position: fixed; inset: 0; z-index: 40; }
.notif-panel {
  position: absolute;
  right: 0;
  top: 110%;
  width: 320px;
  max-height: 60vh;
  overflow-y: auto;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 6px 24px var(--shadow);
  z-index: 41;
  padding: 8px;
}
.notif-head { font-weight: 700; font-size: 13px; padding: 4px 8px 8px; }
.notif-item {
  padding: 8px;
  border-radius: 6px;
  border-bottom: 1px solid var(--border);
}
.notif-item:last-child { border-bottom: none; }
.notif-item.unread { background: var(--nav-active-bg); }
.n-msg { font-size: 13px; color: var(--text); }
.n-time { font-size: 11px; color: var(--muted); margin-top: 2px; }
.hint { font-size: 12px; color: var(--muted); padding: 8px; }
</style>
