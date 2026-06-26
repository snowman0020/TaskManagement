<script setup>
import { ref, onMounted, computed } from 'vue'
import draggable from 'vuedraggable'
import client from '@/api/client'
import TaskModal from '@/components/TaskModal.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const canEdit = computed(() => auth.canEdit)

const columns = ref([])
const board = ref({}) // { statusKey: [tasks] }
const users = ref([])
const sprints = ref([])
const selectedSprint = ref('')
const loading = ref(true)
const modalOpen = ref(false)
const editingTask = ref(null)

const userMap = computed(() =>
  Object.fromEntries(users.value.map((u) => [u.id, u]))
)

async function loadBoard() {
  loading.value = true
  const params = selectedSprint.value ? { sprint_id: selectedSprint.value } : {}
  const { data } = await client.get('/api/tasks/board', { params })
  columns.value = data.columns
  // ensure every column has an array (so empty columns are droppable)
  const grouped = {}
  for (const c of data.columns) grouped[c.key] = data.tasks[c.key] || []
  board.value = grouped
  loading.value = false
}

async function loadMeta() {
  const [u, s] = await Promise.all([
    client.get('/api/users'),
    client.get('/api/sprints'),
  ])
  users.value = u.data
  sprints.value = s.data
}

onMounted(async () => {
  await loadMeta()
  await loadBoard()
})

function initials(id) {
  const u = userMap.value[id]
  if (!u) return '?'
  const name = u.full_name || u.username
  return name.slice(0, 2).toUpperCase()
}

// Persist order/status for a column after a drag drop
async function onColumnChange(statusKey) {
  const items = board.value[statusKey].map((t, idx) => ({
    id: t.id,
    status: statusKey,
    order: idx,
  }))
  if (items.length === 0) return
  try {
    await client.patch('/api/tasks/reorder/bulk', { items })
    // refresh status field locally so leadtime badges stay accurate
    for (const t of board.value[statusKey]) t.status = statusKey
  } catch (e) {
    // revert the optimistic local move by re-fetching authoritative state
    await loadBoard()
    alert('Could not save the change. The board has been refreshed.')
  }
}

function openNew() {
  if (!canEdit.value) return
  editingTask.value = null
  modalOpen.value = true
}
function openTask(task) {
  if (!canEdit.value) return // viewers are read-only
  editingTask.value = task
  modalOpen.value = true
}

async function saveTask(payload) {
  if (payload.id) {
    await client.patch(`/api/tasks/${payload.id}`, payload)
  } else {
    if (selectedSprint.value && !payload.sprint_id) payload.sprint_id = selectedSprint.value
    await client.post('/api/tasks', payload)
  }
  modalOpen.value = false
  await loadBoard()
}

async function deleteTask(task) {
  if (!confirm(`Delete ${task.task_number}?`)) return
  await client.delete(`/api/tasks/${task.id}`)
  modalOpen.value = false
  await loadBoard()
}

function wipExceeded(col) {
  return col.wip_limit && (board.value[col.key]?.length || 0) > col.wip_limit
}
</script>

<template>
  <div class="page-head">
    <h1>Board</h1>
    <div style="display:flex;gap:10px;align-items:center">
      <select v-model="selectedSprint" style="width:200px" @change="loadBoard">
        <option value="">All sprints / Backlog</option>
        <option v-for="s in sprints" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
      <button v-if="canEdit" @click="openNew">+ New Task</button>
    </div>
  </div>

  <div v-if="loading">Loading…</div>
  <div v-else class="board">
    <div v-for="col in columns" :key="col.key" class="column">
      <div class="column-head">
        <span>{{ col.name }}</span>
        <span class="count" :class="{ 'wip-warn': wipExceeded(col) }">
          {{ board[col.key]?.length || 0 }}<template v-if="col.wip_limit"> / {{ col.wip_limit }}</template>
        </span>
      </div>
      <draggable
        class="task-list"
        :list="board[col.key]"
        group="tasks"
        item-key="id"
        :animation="150"
        ghost-class="ghost-card"
        :disabled="!canEdit"
        @change="onColumnChange(col.key)"
      >
        <template #item="{ element }">
          <div class="task" @click="openTask(element)">
            <span class="num">{{ element.task_number }}</span>
            <div class="title">{{ element.title }}</div>
            <div class="meta">
              <span class="badge" :class="element.priority">{{ element.priority }}</span>
              <span v-if="element.story_points" class="badge">{{ element.story_points }} pts</span>
              <span style="flex:1"></span>
              <span v-if="element.assignee_id" class="avatar" :title="userMap[element.assignee_id]?.username">
                {{ initials(element.assignee_id) }}
              </span>
            </div>
          </div>
        </template>
      </draggable>
    </div>
  </div>

  <TaskModal
    v-if="modalOpen"
    :task="editingTask"
    :columns="columns"
    :users="users"
    :sprints="sprints"
    @close="modalOpen = false"
    @save="saveTask"
    @delete="deleteTask"
  />
</template>
