<script setup>
import { ref, onMounted, watch } from 'vue'
import draggable from 'vuedraggable'
import client from '@/api/client'
import DateField from '@/components/DateField.vue'
import { useAuthStore } from '@/stores/auth'
import { useBoardStore } from '@/stores/board'

const auth = useAuthStore()
const board = useBoardStore()
const tab = ref('users')

/* ---------- Users ---------- */
const users = ref([])
const newUser = ref({ username: '', email: '', password: '', full_name: '', role: 'member' })
const userError = ref('')
const editingId = ref(null) // id of the user being edited inline, or null
const editForm = ref({ full_name: '', email: '', role: 'member', is_active: true, password: '' })

async function loadUsers() {
  users.value = (await client.get('/api/users')).data
}
async function createUser() {
  userError.value = ''
  try {
    await client.post('/api/users', newUser.value)
    newUser.value = { username: '', email: '', password: '', full_name: '', role: 'member' }
    await loadUsers()
  } catch (e) {
    userError.value = e.response?.data?.detail || 'Failed'
  }
}
async function updateRole(u, role) {
  userError.value = ''
  try {
    await client.patch(`/api/users/${u.id}`, { role })
  } catch (e) {
    userError.value = e.response?.data?.detail || 'Failed'
  } finally {
    await loadUsers() // re-sync :value-bound dropdown to server truth
  }
}
async function toggleActive(u) {
  userError.value = ''
  try {
    await client.patch(`/api/users/${u.id}`, { is_active: !u.is_active })
  } catch (e) {
    userError.value = e.response?.data?.detail || 'Failed'
  } finally {
    await loadUsers()
  }
}
async function deleteUser(u) {
  if (!confirm(`Delete ${u.username}?`)) return
  userError.value = ''
  try {
    await client.delete(`/api/users/${u.id}`)
  } catch (e) {
    userError.value = e.response?.data?.detail || 'Failed'
  } finally {
    await loadUsers()
  }
}
function startEdit(u) {
  userError.value = ''
  editingId.value = u.id
  editForm.value = {
    full_name: u.full_name || '',
    email: u.email,
    role: u.role,
    is_active: u.is_active,
    password: '', // blank = keep current password
  }
}
function cancelEdit() {
  editingId.value = null
}
async function saveEdit(u) {
  userError.value = ''
  const f = editForm.value
  const payload = {
    full_name: f.full_name,
    email: f.email,
    role: f.role,
    is_active: f.is_active,
  }
  if (f.password) payload.password = f.password // only change password when provided
  try {
    await client.patch(`/api/users/${u.id}`, payload)
    editingId.value = null
  } catch (e) {
    userError.value = e.response?.data?.detail || 'Failed'
  } finally {
    await loadUsers()
  }
}

/* ---------- Status Columns ---------- */
const columns = ref([])
const newCol = ref({ key: '', name: '', order: 0, wip_limit: null, is_done: false })
const colError = ref('')

async function loadColumns() {
  columns.value = (await client.get('/api/status-columns', { params: { board_id: board.activeId } })).data
}
async function createColumn() {
  colError.value = ''
  try {
    await client.post('/api/status-columns', { ...newCol.value, board_id: board.activeId })
    newCol.value = { key: '', name: '', order: columns.value.length, wip_limit: null, is_done: false }
    await loadColumns()
  } catch (e) {
    colError.value = e.response?.data?.detail || 'Failed'
  }
}
async function saveColumn(c) {
  colError.value = ''
  try {
    await client.patch(`/api/status-columns/${c.id}`, {
      key: c.key, name: c.name, order: c.order, wip_limit: c.wip_limit, is_done: c.is_done,
    })
  } catch (e) {
    colError.value = e.response?.data?.detail || 'Failed'
  } finally {
    await loadColumns()
  }
}
async function persistColumnOrder() {
  colError.value = ''
  const items = columns.value.map((c, i) => ({ id: c.id, order: i }))
  try {
    await client.patch('/api/status-columns/reorder', { items })
    columns.value.forEach((c, i) => (c.order = i))
  } catch (e) {
    colError.value = e.response?.data?.detail || 'Failed'
    await loadColumns()
  }
}
async function deleteColumn(c) {
  colError.value = ''
  try {
    await client.delete(`/api/status-columns/${c.id}`)
    await loadColumns()
  } catch (e) {
    colError.value = e.response?.data?.detail || 'Failed'
  }
}

/* ---------- Sprints ---------- */
const sprints = ref([])
const gen = ref({ start_date: '', count: 6, weeks: 2, name_prefix: 'Sprint', manday: null })
const sprintError = ref('')

// '' (cleared number input) -> null so "not set" stays distinct from 0 capacity
function normManday(v) {
  return v === '' || v == null ? null : v
}

async function loadSprints() {
  sprints.value = (await client.get('/api/sprints', { params: { board_id: board.activeId } })).data
}
async function generateSprints() {
  sprintError.value = ''
  try {
    const payload = { ...gen.value, manday: normManday(gen.value.manday), board_id: board.activeId }
    const { data } = await client.post('/api/sprints/generate', payload)
    if (data.created === 0) sprintError.value = 'No new sprints created (names already exist).'
  } catch (e) {
    sprintError.value = e.response?.data?.detail || 'Failed'
  } finally {
    await loadSprints()
  }
}
async function saveManday(s) {
  sprintError.value = ''
  try {
    await client.patch(`/api/sprints/${s.id}`, { manday: normManday(s.manday) })
  } catch (e) {
    sprintError.value = e.response?.data?.detail || 'Failed'
  } finally {
    await loadSprints()
  }
}
async function completeSprint(s) {
  if (
    !confirm(
      `Complete "${s.name}"? This permanently deletes its done tasks and cannot be undone.`
    )
  )
    return
  sprintError.value = ''
  try {
    const { data } = await client.post(`/api/sprints/${s.id}/complete`)
    alert(`Completed "${s.name}". Deleted ${data.deleted} done task(s).`)
  } catch (e) {
    sprintError.value = e.response?.data?.detail || 'Failed'
  } finally {
    await loadSprints()
  }
}
async function setSprintStatus(s, status) {
  sprintError.value = ''
  try {
    await client.patch(`/api/sprints/${s.id}`, { status })
  } catch (e) {
    sprintError.value = e.response?.data?.detail || 'Failed'
  } finally {
    await loadSprints()
  }
}
async function deleteSprint(s) {
  if (!confirm(`Delete ${s.name}?`)) return
  sprintError.value = ''
  try {
    await client.delete(`/api/sprints/${s.id}`)
  } catch (e) {
    sprintError.value = e.response?.data?.detail || 'Failed'
  } finally {
    await loadSprints()
  }
}
function fmt(d) {
  return d ? new Date(d).toISOString().slice(0, 10) : ''
}

/* ---------- Boards ---------- */
const boards = ref([])
const newBoard = ref({ name: '', prefix: 'TASK', start_number: 1, member_ids: [] })
const boardError = ref('')

async function loadBoards() {
  boards.value = (await client.get('/api/boards')).data
}
async function createBoard() {
  boardError.value = ''
  try {
    await client.post('/api/boards', newBoard.value)
    newBoard.value = { name: '', prefix: 'TASK', start_number: 1, member_ids: [] }
    await loadBoards()
    await board.reload() // refresh the top-bar switcher
  } catch (e) {
    boardError.value = e.response?.data?.detail || 'Failed'
  }
}
async function saveBoardMembers(b) {
  boardError.value = ''
  try {
    await client.patch(`/api/boards/${b.id}`, { member_ids: b.member_ids })
  } catch (e) {
    boardError.value = e.response?.data?.detail || 'Failed'
  } finally {
    await loadBoards()
  }
}
async function deleteBoard(b) {
  if (!confirm(`Delete board "${b.name}" and all its tasks/sprints/columns? Cannot be undone.`)) return
  boardError.value = ''
  try {
    await client.delete(`/api/boards/${b.id}`)
    await loadBoards()
    await board.reload()
  } catch (e) {
    boardError.value = e.response?.data?.detail || 'Failed'
  }
}
function toggleMember(list, userId) {
  const i = list.indexOf(userId)
  if (i >= 0) list.splice(i, 1)
  else list.push(userId)
}

onMounted(async () => {
  await board.load()
  loadUsers(); loadColumns(); loadSprints(); loadBoards()
})

// columns and sprints are per board — reload them when the active board changes
watch(() => board.activeId, () => {
  loadColumns(); loadSprints()
})
</script>

<template>
  <div class="page-head"><h1>Admin</h1></div>

  <div class="tabs">
    <div class="tab" :class="{ active: tab === 'users' }" @click="tab = 'users'">Users &amp; Roles</div>
    <div class="tab" :class="{ active: tab === 'columns' }" @click="tab = 'columns'">Status Columns</div>
    <div class="tab" :class="{ active: tab === 'sprints' }" @click="tab = 'sprints'">Sprints</div>
    <div v-if="auth.isAdmin" class="tab" :class="{ active: tab === 'boards' }" @click="tab = 'boards'">Boards</div>
  </div>

  <!-- USERS -->
  <div v-if="tab === 'users'">
    <div class="card" v-if="auth.isAdmin" style="margin-bottom:16px">
      <h3 style="margin-top:0">Add User</h3>
      <div class="row">
        <input v-model="newUser.username" placeholder="username" autocomplete="off" />
        <input v-model="newUser.email" placeholder="email" autocomplete="off" />
        <input v-model="newUser.full_name" placeholder="full name" autocomplete="off" />
      </div>
      <div class="row" style="margin-top:10px">
        <input v-model="newUser.password" type="password" placeholder="password (min 6)" autocomplete="new-password" />
        <select v-model="newUser.role">
          <option value="admin">admin</option>
          <option value="manager">manager</option>
          <option value="member">member</option>
          <option value="viewer">viewer</option>
        </select>
        <button @click="createUser">Create</button>
      </div>
      <p v-if="userError" class="error">{{ userError }}</p>
    </div>

    <div class="card">
      <table>
        <thead><tr><th>Username</th><th>Email</th><th>Role</th><th>Active</th><th></th></tr></thead>
        <tbody>
          <template v-for="u in users" :key="u.id">
            <tr>
              <td>{{ u.full_name || u.username }}<br /><small style="color:var(--muted)">{{ u.username }}</small></td>
              <td>{{ u.email }}</td>
              <td>
                <select :value="u.role" :disabled="!auth.isAdmin" @change="updateRole(u, $event.target.value)">
                  <option value="admin">admin</option>
                  <option value="manager">manager</option>
                  <option value="member">member</option>
                  <option value="viewer">viewer</option>
                </select>
              </td>
              <td><button class="ghost" :disabled="!auth.isAdmin" @click="toggleActive(u)">{{ u.is_active ? 'Yes' : 'No' }}</button></td>
              <td style="white-space:nowrap">
                <button v-if="auth.isAdmin" class="ghost" @click="editingId === u.id ? cancelEdit() : startEdit(u)">
                  {{ editingId === u.id ? 'Close' : 'Edit' }}
                </button>
                <button v-if="auth.isAdmin" class="danger" @click="deleteUser(u)">Delete</button>
              </td>
            </tr>
            <tr v-if="editingId === u.id">
              <td colspan="5">
                <div class="card" style="background:var(--col-bg)">
                  <div class="row">
                    <label style="flex:1">Full name
                      <input v-model="editForm.full_name" autocomplete="off" />
                    </label>
                    <label style="flex:1">Email
                      <input v-model="editForm.email" type="email" autocomplete="off" />
                    </label>
                  </div>
                  <div class="row" style="margin-top:10px">
                    <label style="flex:1">Role
                      <select v-model="editForm.role">
                        <option value="admin">admin</option>
                        <option value="manager">manager</option>
                        <option value="member">member</option>
                        <option value="viewer">viewer</option>
                      </select>
                    </label>
                    <label style="flex:1">Active
                      <select v-model="editForm.is_active">
                        <option :value="true">Yes</option>
                        <option :value="false">No</option>
                      </select>
                    </label>
                  </div>
                  <div class="row" style="margin-top:10px">
                    <label style="flex:1">New password <small style="color:var(--muted)">(leave blank to keep current)</small>
                      <input v-model="editForm.password" type="password" placeholder="new password (min 6)" autocomplete="new-password" />
                    </label>
                  </div>
                  <div class="row" style="margin-top:10px;align-items:center">
                    <button @click="saveEdit(u)">Save changes</button>
                    <button class="ghost" @click="cancelEdit">Cancel</button>
                    <small style="color:var(--muted)">Username <code>{{ u.username }}</code> can't be changed</small>
                  </div>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </div>

  <!-- COLUMNS -->
  <div v-if="tab === 'columns'">
    <div class="card" style="margin-bottom:16px">
      <h3 style="margin-top:0">Add Status Column</h3>
      <div class="row">
        <input v-model="newCol.key" placeholder="key (e.g. Review)" />
        <input v-model="newCol.name" placeholder="display name" />
        <input v-model.number="newCol.order" type="number" placeholder="order" />
        <input v-model.number="newCol.wip_limit" type="number" placeholder="WIP limit" />
        <label style="display:flex;align-items:center;gap:6px;margin:0">
          <input type="checkbox" v-model="newCol.is_done" style="width:auto" /> Done
        </label>
        <button @click="createColumn">Add</button>
      </div>
      <p v-if="colError" class="error">{{ colError }}</p>
    </div>

    <div class="card">
      <table>
        <thead><tr><th></th><th>Key</th><th>Name</th><th>WIP Limit</th><th>Is Done</th><th></th></tr></thead>
        <draggable
          tag="tbody"
          :list="columns"
          item-key="id"
          handle=".drag-handle"
          :animation="150"
          @end="persistColumnOrder"
        >
          <template #item="{ element: c }">
            <tr>
              <td class="drag-handle" style="cursor:grab;width:28px;text-align:center" title="Drag to reorder">⠿</td>
              <td><input v-model="c.key" style="width:130px" /></td>
              <td><input v-model="c.name" /></td>
              <td><input v-model.number="c.wip_limit" type="number" style="width:80px" /></td>
              <td><input type="checkbox" v-model="c.is_done" style="width:auto" /></td>
              <td style="display:flex;gap:6px">
                <button @click="saveColumn(c)">Save</button>
                <button class="danger" @click="deleteColumn(c)">Del</button>
              </td>
            </tr>
          </template>
        </draggable>
      </table>
    </div>
  </div>

  <!-- SPRINTS -->
  <div v-if="tab === 'sprints'">
    <div class="card" style="margin-bottom:16px">
      <h3 style="margin-top:0">Generate Sprints (2-week, Mon–Fri workdays)</h3>
      <div class="row">
        <div>
          <label>Start date (snaps to Monday)</label>
          <DateField v-model="gen.start_date" />
        </div>
        <div>
          <label>Sprint count</label>
          <input v-model.number="gen.count" type="number" min="1" max="52" />
        </div>
        <div>
          <label>Weeks per sprint</label>
          <input v-model.number="gen.weeks" type="number" min="1" max="4" />
        </div>
        <div>
          <label>Name prefix</label>
          <input v-model="gen.name_prefix" />
        </div>
        <div>
          <label>Manday (default)</label>
          <input v-model.number="gen.manday" type="number" min="0" step="0.5" placeholder="optional" />
        </div>
        <div style="display:flex;align-items:flex-end">
          <button @click="generateSprints" :disabled="!gen.start_date">Generate</button>
        </div>
      </div>
      <p v-if="sprintError" class="error">{{ sprintError }}</p>
    </div>

    <div class="card">
      <table>
        <thead><tr><th>Name</th><th>Start</th><th>End</th><th>Working Days</th><th>Manday</th><th>Status</th><th></th></tr></thead>
        <tbody>
          <tr v-for="s in sprints" :key="s.id">
            <td>{{ s.name }}<br /><small style="color:var(--muted)">{{ s.goal }}</small></td>
            <td>{{ fmt(s.start_date) }}</td>
            <td>{{ fmt(s.end_date) }}</td>
            <td>{{ s.working_days }}</td>
            <td style="display:flex;gap:6px;align-items:center">
              <input v-model.number="s.manday" type="number" min="0" step="0.5" style="width:80px" />
              <button class="ghost" @click="saveManday(s)">Save</button>
            </td>
            <td>
              <select :value="s.status" @change="setSprintStatus(s, $event.target.value)">
                <option value="planned">planned</option>
                <option value="active">active</option>
                <option value="completed">completed</option>
              </select>
            </td>
            <td style="display:flex;gap:6px">
              <button class="ghost" @click="completeSprint(s)">Complete</button>
              <button class="danger" @click="deleteSprint(s)">Delete</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- BOARDS -->
  <div v-if="tab === 'boards' && auth.isAdmin">
    <div class="card" style="margin-bottom:16px">
      <h3 style="margin-top:0">Create Board</h3>
      <div class="row">
        <div>
          <label>Name</label>
          <input v-model="newBoard.name" placeholder="e.g. Mobile App" />
        </div>
        <div>
          <label>Task prefix</label>
          <input v-model="newBoard.prefix" placeholder="TASK" />
        </div>
        <div>
          <label>Start number</label>
          <input v-model.number="newBoard.start_number" type="number" min="1" />
        </div>
        <div style="display:flex;align-items:flex-end">
          <button @click="createBoard" :disabled="!newBoard.name || !newBoard.prefix">Create</button>
        </div>
      </div>
      <div style="margin-top:10px">
        <label>Members</label>
        <div style="display:flex;flex-wrap:wrap;gap:10px">
          <label
            v-for="u in users"
            :key="u.id"
            style="display:flex;align-items:center;gap:4px;margin:0;font-size:13px"
          >
            <input
              type="checkbox"
              style="width:auto"
              :checked="newBoard.member_ids.includes(u.id)"
              @change="toggleMember(newBoard.member_ids, u.id)"
            />
            {{ u.full_name || u.username }}
          </label>
        </div>
      </div>
      <p v-if="boardError" class="error">{{ boardError }}</p>
    </div>

    <div class="card">
      <table>
        <thead><tr><th>Name</th><th>Prefix</th><th>Members</th><th></th></tr></thead>
        <tbody>
          <tr v-for="b in boards" :key="b.id">
            <td>
              {{ b.name }}
              <span v-if="b.is_default" class="badge" style="margin-left:6px">default</span>
            </td>
            <td><code>{{ b.prefix }}</code></td>
            <td>
              <div style="display:flex;flex-wrap:wrap;gap:8px">
                <label
                  v-for="u in users"
                  :key="u.id"
                  style="display:flex;align-items:center;gap:4px;margin:0;font-size:12px"
                >
                  <input
                    type="checkbox"
                    style="width:auto"
                    :checked="b.member_ids.includes(u.id)"
                    @change="toggleMember(b.member_ids, u.id)"
                  />
                  {{ u.username }}
                </label>
              </div>
            </td>
            <td style="display:flex;gap:6px">
              <button class="ghost" @click="saveBoardMembers(b)">Save</button>
              <button v-if="!b.is_default" class="danger" @click="deleteBoard(b)">Delete</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
