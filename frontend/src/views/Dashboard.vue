<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import client from '@/api/client'
import { useBoardStore } from '@/stores/board'

const board = useBoardStore()
const stats = ref(null)
const sprints = ref([])
const users = ref([])
const selectedSprint = ref('')
const loading = ref(true)

const userMap = computed(() => Object.fromEntries(users.value.map((u) => [u.id, u])))

async function load() {
  loading.value = true
  const params = { board_id: board.activeId }
  if (selectedSprint.value) params.sprint_id = selectedSprint.value
  const { data } = await client.get('/api/dashboard/overview', { params })
  stats.value = data
  loading.value = false
}

async function loadAll() {
  const [s, u] = await Promise.all([
    client.get('/api/sprints', { params: { board_id: board.activeId } }),
    client.get('/api/users'),
  ])
  sprints.value = s.data
  users.value = u.data
  selectedSprint.value = ''
  await load()
}

onMounted(async () => {
  await board.load()
  await loadAll()
})

watch(() => board.activeId, loadAll)

function maxVal(obj) {
  const vals = Object.values(obj || {})
  return vals.length ? Math.max(...vals, 1) : 1
}
function assigneeName(id) {
  if (id === 'unassigned') return 'Unassigned'
  return userMap.value[id]?.full_name || userMap.value[id]?.username || id
}
function fmtHours(h) {
  if (h == null) return '—'
  if (h < 24) return `${h} h`
  return `${(h / 24).toFixed(1)} d`
}
</script>

<template>
  <div class="page-head">
    <h1>Dashboard</h1>
    <select v-model="selectedSprint" style="width:200px" @change="load">
      <option value="">All sprints</option>
      <option v-for="s in sprints" :key="s.id" :value="s.id">{{ s.name }}</option>
    </select>
  </div>

  <div v-if="loading">Loading…</div>
  <div v-else-if="stats">
    <div class="stat-grid">
      <div class="stat">
        <div class="label">Total Tasks</div>
        <div class="value">{{ stats.total_tasks }}</div>
      </div>
      <div class="stat">
        <div class="label">Completed</div>
        <div class="value">{{ stats.done_tasks }}</div>
      </div>
      <div class="stat">
        <div class="label">Completion Rate</div>
        <div class="value">{{ stats.completion_rate }}%</div>
      </div>
      <div class="stat">
        <div class="label">Avg Lead Time</div>
        <div class="value">{{ fmtHours(stats.leadtime_hours.avg) }}</div>
      </div>
      <div class="stat">
        <div class="label">Avg Cycle Time</div>
        <div class="value">{{ fmtHours(stats.cycletime_hours.avg) }}</div>
      </div>
      <div class="stat">
        <div class="label">Story Points (done / total)</div>
        <div class="value">{{ stats.story_points.done }} / {{ stats.story_points.total }}</div>
      </div>
    </div>

    <div class="row" style="align-items:flex-start">
      <div class="card">
        <h3 style="margin-top:0">Tasks by Status</h3>
        <div v-for="(count, key) in stats.by_status" :key="key" class="bar-row">
          <span class="name">{{ key }}</span>
          <div class="bar" :style="{ width: (count / maxVal(stats.by_status)) * 200 + 'px' }"></div>
          <span>{{ count }}</span>
        </div>
      </div>

      <div class="card">
        <h3 style="margin-top:0">Tasks by Assignee</h3>
        <div v-for="(count, id) in stats.by_assignee" :key="id" class="bar-row">
          <span class="name">{{ assigneeName(id) }}</span>
          <div class="bar" :style="{ width: (count / maxVal(stats.by_assignee)) * 200 + 'px', background: 'var(--qa)' }"></div>
          <span>{{ count }}</span>
        </div>
      </div>
    </div>

    <div class="card" style="margin-top:16px">
      <h3 style="margin-top:0">Lead Time Detail (created → done)</h3>
      <div class="row">
        <div><div class="label">Average</div><strong>{{ fmtHours(stats.leadtime_hours.avg) }}</strong></div>
        <div><div class="label">Fastest</div><strong>{{ fmtHours(stats.leadtime_hours.min) }}</strong></div>
        <div><div class="label">Slowest</div><strong>{{ fmtHours(stats.leadtime_hours.max) }}</strong></div>
        <div><div class="label">Samples</div><strong>{{ stats.leadtime_hours.samples }}</strong></div>
      </div>
    </div>
  </div>
</template>
