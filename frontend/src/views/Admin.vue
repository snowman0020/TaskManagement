<script setup>
import { ref, onMounted } from 'vue'
import client from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const tab = ref('users')

/* ---------- Users ---------- */
const users = ref([])
const newUser = ref({ username: '', email: '', password: '', full_name: '', role: 'member' })
const userError = ref('')

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
  await client.patch(`/api/users/${u.id}`, { role })
  await loadUsers()
}
async function toggleActive(u) {
  await client.patch(`/api/users/${u.id}`, { is_active: !u.is_active })
  await loadUsers()
}
async function deleteUser(u) {
  if (!confirm(`Delete ${u.username}?`)) return
  await client.delete(`/api/users/${u.id}`)
  await loadUsers()
}

/* ---------- Status Columns ---------- */
const columns = ref([])
const newCol = ref({ key: '', name: '', order: 0, wip_limit: null, is_done: false })
const colError = ref('')

async function loadColumns() {
  columns.value = (await client.get('/api/status-columns')).data
}
async function createColumn() {
  colError.value = ''
  try {
    await client.post('/api/status-columns', newCol.value)
    newCol.value = { key: '', name: '', order: columns.value.length, wip_limit: null, is_done: false }
    await loadColumns()
  } catch (e) {
    colError.value = e.response?.data?.detail || 'Failed'
  }
}
async function saveColumn(c) {
  await client.patch(`/api/status-columns/${c.id}`, {
    name: c.name, order: c.order, wip_limit: c.wip_limit, is_done: c.is_done,
  })
  await loadColumns()
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
const gen = ref({ start_date: '', count: 6, weeks: 2, name_prefix: 'Sprint' })

async function loadSprints() {
  sprints.value = (await client.get('/api/sprints')).data
}
async function generateSprints() {
  await client.post('/api/sprints/generate', gen.value)
  await loadSprints()
}
async function setSprintStatus(s, status) {
  await client.patch(`/api/sprints/${s.id}`, { status })
  await loadSprints()
}
async function deleteSprint(s) {
  if (!confirm(`Delete ${s.name}?`)) return
  await client.delete(`/api/sprints/${s.id}`)
  await loadSprints()
}
function fmt(d) {
  return d ? new Date(d).toISOString().slice(0, 10) : ''
}

onMounted(() => {
  loadUsers(); loadColumns(); loadSprints()
})
</script>

<template>
  <div class="page-head"><h1>Admin</h1></div>

  <div class="tabs">
    <div class="tab" :class="{ active: tab === 'users' }" @click="tab = 'users'">Users &amp; Roles</div>
    <div class="tab" :class="{ active: tab === 'columns' }" @click="tab = 'columns'">Status Columns</div>
    <div class="tab" :class="{ active: tab === 'sprints' }" @click="tab = 'sprints'">Sprints</div>
  </div>

  <!-- USERS -->
  <div v-if="tab === 'users'">
    <div class="card" v-if="auth.isAdmin" style="margin-bottom:16px">
      <h3 style="margin-top:0">Add User</h3>
      <div class="row">
        <input v-model="newUser.username" placeholder="username" />
        <input v-model="newUser.email" placeholder="email" />
        <input v-model="newUser.full_name" placeholder="full name" />
      </div>
      <div class="row" style="margin-top:10px">
        <input v-model="newUser.password" type="password" placeholder="password (min 6)" />
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
          <tr v-for="u in users" :key="u.id">
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
            <td><button class="ghost" @click="toggleActive(u)">{{ u.is_active ? 'Yes' : 'No' }}</button></td>
            <td><button v-if="auth.isAdmin" class="danger" @click="deleteUser(u)">Delete</button></td>
          </tr>
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
        <thead><tr><th>Key</th><th>Name</th><th>Order</th><th>WIP Limit</th><th>Is Done</th><th></th></tr></thead>
        <tbody>
          <tr v-for="c in columns" :key="c.id">
            <td><code>{{ c.key }}</code></td>
            <td><input v-model="c.name" /></td>
            <td><input v-model.number="c.order" type="number" style="width:70px" /></td>
            <td><input v-model.number="c.wip_limit" type="number" style="width:80px" /></td>
            <td><input type="checkbox" v-model="c.is_done" style="width:auto" /></td>
            <td style="display:flex;gap:6px">
              <button @click="saveColumn(c)">Save</button>
              <button class="danger" @click="deleteColumn(c)">Del</button>
            </td>
          </tr>
        </tbody>
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
          <input v-model="gen.start_date" type="date" />
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
        <div style="display:flex;align-items:flex-end">
          <button @click="generateSprints" :disabled="!gen.start_date">Generate</button>
        </div>
      </div>
    </div>

    <div class="card">
      <table>
        <thead><tr><th>Name</th><th>Start</th><th>End</th><th>Working Days</th><th>Status</th><th></th></tr></thead>
        <tbody>
          <tr v-for="s in sprints" :key="s.id">
            <td>{{ s.name }}<br /><small style="color:var(--muted)">{{ s.goal }}</small></td>
            <td>{{ fmt(s.start_date) }}</td>
            <td>{{ fmt(s.end_date) }}</td>
            <td>{{ s.working_days }}</td>
            <td>
              <select :value="s.status" @change="setSprintStatus(s, $event.target.value)">
                <option value="planned">planned</option>
                <option value="active">active</option>
                <option value="completed">completed</option>
              </select>
            </td>
            <td><button class="danger" @click="deleteSprint(s)">Delete</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
