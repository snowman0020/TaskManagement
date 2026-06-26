<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import draggable from 'vuedraggable'
import client from '@/api/client'
import TaskModal from '@/components/TaskModal.vue'
import { useAuthStore } from '@/stores/auth'
import { useBoardStore } from '@/stores/board'

const auth = useAuthStore()
const boardStore = useBoardStore()
const canEdit = computed(() => auth.canEdit)

const columns = ref([])
const board = ref({}) // { statusKey: [tasks] }
const users = ref([])
const sprints = ref([])
// view: 'active' (active sprint) | 'backlog' | 'all' | a specific sprint id
const view = ref('all')
const selectedAssignee = ref('') // '' = all, 'none' = unassigned, otherwise a user id
const loading = ref(true)
const modalOpen = ref(false)
const editingTask = ref(null)

const userMap = computed(() =>
  Object.fromEntries(users.value.map((u) => [u.id, u]))
)

const activeSprint = computed(() => sprints.value.find((s) => s.status === 'active'))
const noActiveSprint = computed(() => view.value === 'active' && !activeSprint.value)

// the "jump to a specific sprint" dropdown: blank while in a toggle mode
const sprintSelect = computed({
  get: () => (['active', 'backlog', 'all'].includes(view.value) ? '' : view.value),
  set: (v) => {
    if (v) setView(v)
  },
})

// the sprint a new task should default into, given the current view
function currentSprintId() {
  if (view.value === 'active') return activeSprint.value?.id || null
  if (view.value === 'backlog' || view.value === 'all') return null
  return view.value
}

// other users for the filter row (the current user gets a dedicated "Me" chip)
const otherUsers = computed(() =>
  users.value.filter((u) => u.id !== auth.user?.id)
)

async function loadBoard() {
  // "Active Sprint" view with no active sprint: show empty columns + a hint,
  // reusing the already-loaded columns rather than fetching every task.
  if (noActiveSprint.value) {
    const grouped = {}
    for (const c of columns.value) grouped[c.key] = []
    board.value = grouped
    loading.value = false
    return
  }
  loading.value = true
  const params = { board_id: boardStore.activeId }
  if (view.value === 'backlog') params.sprint_id = 'none'
  else if (view.value === 'active') params.sprint_id = activeSprint.value.id
  else if (view.value !== 'all') params.sprint_id = view.value
  if (selectedAssignee.value) params.assignee_id = selectedAssignee.value
  const { data } = await client.get('/api/tasks/board', { params })
  columns.value = data.columns
  // ensure every column has an array (so empty columns are droppable)
  const grouped = {}
  for (const c of data.columns) grouped[c.key] = data.tasks[c.key] || []
  board.value = grouped
  loading.value = false
}

function setView(v) {
  view.value = v
  loadBoard()
}

async function loadMeta() {
  const [u, s] = await Promise.all([
    client.get('/api/users'),
    client.get('/api/sprints', { params: { board_id: boardStore.activeId } }),
  ])
  users.value = u.data
  sprints.value = s.data
}

async function reloadForBoard() {
  await loadMeta()
  // default to the active sprint when there is one, otherwise show everything
  view.value = activeSprint.value ? 'active' : 'all'
  selectedAssignee.value = ''
  await loadBoard()
}

onMounted(async () => {
  await boardStore.load()
  await reloadForBoard()
})

// reload everything when the active board changes
watch(() => boardStore.activeId, reloadForBoard)

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

async function uploadImages(taskId, files) {
  if (!files?.length) return
  const fd = new FormData()
  for (const f of files) fd.append('files', f)
  await client.post(`/api/tasks/${taskId}/images`, fd)
}

async function saveTask(payload, pendingFiles = []) {
  let taskId = payload.id
  if (payload.id) {
    await client.patch(`/api/tasks/${payload.id}`, payload)
  } else {
    const sid = currentSprintId()
    if (sid && !payload.sprint_id) payload.sprint_id = sid
    payload.board_id = boardStore.activeId
    const { data } = await client.post('/api/tasks', payload)
    taskId = data.id
  }
  await uploadImages(taskId, pendingFiles)
  modalOpen.value = false
  await loadBoard()
}

// An image was added/removed inside the modal without saving the task — keep
// the board's attachment badges in sync.
async function onImagesChanged() {
  await loadBoard()
}

function closeModal() {
  modalOpen.value = false
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

function setAssignee(val) {
  selectedAssignee.value = val
  loadBoard()
}
</script>

<template>
  <div class="page-head">
    <h1>Board</h1>
    <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
      <div class="segmented">
        <button class="seg-btn" :class="{ active: view === 'active' }" @click="setView('active')">
          Active Sprint
        </button>
        <button class="seg-btn" :class="{ active: view === 'backlog' }" @click="setView('backlog')">
          Backlog
        </button>
        <button class="seg-btn" :class="{ active: view === 'all' }" @click="setView('all')">All</button>
      </div>
      <select v-model="sprintSelect" style="width:170px">
        <option value="">Jump to sprint…</option>
        <option v-for="s in sprints" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
      <button v-if="canEdit" @click="openNew">+ New Task</button>
    </div>
  </div>

  <div class="filter-row">
    <span class="chip" :class="{ active: selectedAssignee === '' }" @click="setAssignee('')">All</span>
    <span
      v-if="auth.user"
      class="chip"
      :class="{ active: selectedAssignee === auth.user.id }"
      @click="setAssignee(auth.user.id)"
    >
      <span class="avatar">{{ initials(auth.user.id) }}</span> Me
    </span>
    <span
      v-for="u in otherUsers"
      :key="u.id"
      class="chip"
      :class="{ active: selectedAssignee === u.id }"
      :title="u.username"
      @click="setAssignee(u.id)"
    >
      <span class="avatar">{{ initials(u.id) }}</span> {{ u.full_name || u.username }}
    </span>
    <span class="chip" :class="{ active: selectedAssignee === 'none' }" @click="setAssignee('none')">
      Unassigned
    </span>
  </div>

  <div v-if="loading">Loading…</div>
  <div v-else-if="noActiveSprint" class="empty-hint">
    No active sprint. Set a sprint’s status to “active” in Admin, or choose Backlog / All.
  </div>
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
              <span v-if="element.images?.length" class="badge">📎 {{ element.images.length }}</span>
              <span v-if="element.due_date" class="badge">📅 {{ String(element.due_date).slice(0, 10) }}</span>
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
    @close="closeModal"
    @save="saveTask"
    @delete="deleteTask"
    @images-changed="onImagesChanged"
  />
</template>
