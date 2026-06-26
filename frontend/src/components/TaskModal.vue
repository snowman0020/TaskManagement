<script setup>
import { ref, watch, onMounted } from 'vue'
import client from '@/api/client'
import ImageUploader from '@/components/ImageUploader.vue'
import DateField from '@/components/DateField.vue'
import { formatDateTime } from '@/utils/datetime'

const props = defineProps({
  task: { type: Object, default: null },
  columns: { type: Array, default: () => [] },
  users: { type: Array, default: () => [] },
  sprints: { type: Array, default: () => [] },
})
const emit = defineEmits(['close', 'save', 'delete', 'images-changed'])

const form = ref({})
const pendingFiles = ref([])
const history = ref([])

async function loadHistory() {
  if (!props.task?.id) {
    history.value = []
    return
  }
  try {
    const { data } = await client.get(`/api/tasks/${props.task.id}/history`)
    history.value = data
  } catch {
    history.value = []
  }
}

function statusName(key) {
  return props.columns.find((c) => c.key === key)?.name || key
}

function fmtTime(iso) {
  return formatDateTime(iso)
}

onMounted(loadHistory)

watch(
  () => props.task,
  (t) => {
    form.value = {
      title: '',
      description: '',
      status: props.columns[0]?.key || 'TODO',
      priority: 'medium',
      assignee_id: '',
      sprint_id: '',
      story_points: null,
      ...(t || {}),
    }
  },
  { immediate: true }
)

const isNew = () => !props.task?.id

function save() {
  const payload = { ...form.value }
  if (payload.assignee_id === '') payload.assignee_id = null
  if (payload.sprint_id === '') payload.sprint_id = null
  // a cleared number input yields '' — normalize so the int|None backend accepts it
  if (payload.story_points === '') payload.story_points = null
  emit('save', payload, pendingFiles.value)
}
</script>

<template>
  <div class="modal-backdrop" @click.self="emit('close')">
    <div class="modal">
      <h2>
        {{ isNew() ? 'New Task' : task.task_number }}
      </h2>
      <div class="field">
        <label>Title</label>
        <input v-model="form.title" placeholder="Task title" />
      </div>
      <div class="field">
        <label>Description</label>
        <textarea v-model="form.description" rows="4"></textarea>
      </div>
      <div class="row">
        <div class="field">
          <label>Status</label>
          <select v-model="form.status">
            <option v-for="c in columns" :key="c.key" :value="c.key">{{ c.name }}</option>
          </select>
        </div>
        <div class="field">
          <label>Priority</label>
          <select v-model="form.priority">
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
        </div>
      </div>
      <div class="row">
        <div class="field">
          <label>Assignee</label>
          <select v-model="form.assignee_id">
            <option value="">Unassigned</option>
            <option v-for="u in users" :key="u.id" :value="u.id">
              {{ u.full_name || u.username }}
            </option>
          </select>
        </div>
        <div class="field">
          <label>Sprint</label>
          <select v-model="form.sprint_id">
            <option value="">Backlog</option>
            <option v-for="s in sprints" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </div>
        <div class="field">
          <label>Story Points</label>
          <input v-model.number="form.story_points" type="number" min="0" />
        </div>
        <div class="field">
          <label>Expected date</label>
          <DateField v-model="form.due_date" />
        </div>
      </div>
      <ImageUploader
        :task="task"
        @update:pending="pendingFiles = $event"
        @changed="emit('images-changed')"
      />
      <div v-if="!isNew()" class="field">
        <label>Move history</label>
        <div v-if="history.length" class="history">
          <div v-for="(h, i) in history" :key="i" class="history-row">
            <span class="who">{{ h.username }}</span>
            moved
            <span class="badge">{{ statusName(h.from_status) }}</span>
            →
            <span class="badge">{{ statusName(h.to_status) }}</span>
            <span class="when">{{ fmtTime(h.at) }}</span>
          </div>
        </div>
        <p v-else class="hint">No moves yet.</p>
      </div>
      <div class="modal-actions">
        <button v-if="!isNew()" class="danger" @click="emit('delete', task)">Delete</button>
        <button class="ghost" @click="emit('close')">Cancel</button>
        <button @click="save" :disabled="!form.title">Save</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.history {
  max-height: 140px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px;
  background: var(--input-bg);
}
.history-row {
  font-size: 13px;
  color: var(--text);
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  padding: 3px 0;
}
.history-row .who { font-weight: 600; }
.history-row .when { color: var(--muted); margin-left: auto; font-size: 12px; }
.hint { font-size: 12px; color: var(--muted); margin: 4px 0 0; }
</style>
