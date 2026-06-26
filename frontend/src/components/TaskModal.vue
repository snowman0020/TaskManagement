<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  task: { type: Object, default: null },
  columns: { type: Array, default: () => [] },
  users: { type: Array, default: () => [] },
  sprints: { type: Array, default: () => [] },
})
const emit = defineEmits(['close', 'save', 'delete'])

const form = ref({})

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
  emit('save', payload)
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
      </div>
      <div class="modal-actions">
        <button v-if="!isNew()" class="danger" @click="emit('delete', task)">Delete</button>
        <button class="ghost" @click="emit('close')">Cancel</button>
        <button @click="save" :disabled="!form.title">Save</button>
      </div>
    </div>
  </div>
</template>
