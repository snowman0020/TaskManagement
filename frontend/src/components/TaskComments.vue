<script setup>
import { ref, onMounted } from 'vue'
import client from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { formatDateTime } from '@/utils/datetime'

const props = defineProps({
  taskId: { type: String, required: true },
})
const auth = useAuthStore()

const comments = ref([])
const newBody = ref('')
const replyFor = ref(null) // id of the comment whose reply box is open
const replyBody = ref('')
const error = ref('')

async function load() {
  try {
    comments.value = (await client.get(`/api/tasks/${props.taskId}/comments`)).data
  } catch {
    comments.value = []
  }
}

async function add(body, parentId = null) {
  const text = (body || '').trim()
  if (!text) return
  error.value = ''
  try {
    await client.post(`/api/tasks/${props.taskId}/comments`, { body: text, parent_id: parentId })
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to post'
  }
}

async function submitNew() {
  await add(newBody.value)
  newBody.value = ''
}
async function submitReply(parentId) {
  await add(replyBody.value, parentId)
  replyBody.value = ''
  replyFor.value = null
}
async function remove(id) {
  if (!confirm('Delete this comment?')) return
  error.value = ''
  try {
    await client.delete(`/api/tasks/${props.taskId}/comments/${id}`)
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to delete'
  }
}
function canDelete(c) {
  return c.user_id === auth.user?.id || auth.isManager
}

onMounted(load)
</script>

<template>
  <div class="field">
    <label>Comments</label>
    <div class="comments">
      <div v-for="c in comments" :key="c.id" class="comment">
        <div class="c-head">
          <span class="who">{{ c.username }}</span>
          <span class="when">{{ formatDateTime(c.created_at) }}</span>
          <button v-if="canDelete(c)" class="c-x" title="Delete" @click="remove(c.id)">×</button>
        </div>
        <div class="c-body">{{ c.body }}</div>
        <button class="c-reply" @click="replyFor = replyFor === c.id ? null : c.id">Reply</button>

        <div v-if="replyFor === c.id" class="reply-box">
          <input v-model="replyBody" placeholder="Write a reply…" @keyup.enter="submitReply(c.id)" />
          <button @click="submitReply(c.id)" :disabled="!replyBody.trim()">Reply</button>
        </div>

        <div v-for="r in c.replies" :key="r.id" class="comment reply">
          <div class="c-head">
            <span class="who">{{ r.username }}</span>
            <span class="when">{{ formatDateTime(r.created_at) }}</span>
            <button v-if="canDelete(r)" class="c-x" title="Delete" @click="remove(r.id)">×</button>
          </div>
          <div class="c-body">{{ r.body }}</div>
        </div>
      </div>
      <p v-if="!comments.length" class="hint">No comments yet.</p>
    </div>

    <div class="add-box">
      <input v-model="newBody" placeholder="Add a comment…" @keyup.enter="submitNew" />
      <button @click="submitNew" :disabled="!newBody.trim()">Comment</button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<style scoped>
.comments {
  max-height: 220px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px;
  background: var(--input-bg);
}
.comment { padding: 6px 0; border-bottom: 1px solid var(--border); }
.comment:last-child { border-bottom: none; }
.comment.reply { margin-left: 18px; border-bottom: none; border-left: 2px solid var(--border); padding-left: 8px; }
.c-head { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.c-head .who { font-weight: 600; color: var(--text); }
.c-head .when { color: var(--muted); }
.c-head .c-x { margin-left: auto; background: transparent; color: var(--muted); padding: 0 6px; font-size: 14px; }
.c-head .c-x:hover { color: var(--danger); }
.c-body { font-size: 13px; color: var(--text); white-space: pre-wrap; margin: 2px 0; }
.c-reply { background: transparent; color: var(--primary); padding: 2px 0; font-size: 12px; }
.reply-box, .add-box { display: flex; gap: 6px; margin-top: 6px; }
.reply-box input, .add-box input { flex: 1; }
.add-box { margin-top: 8px; }
.hint { font-size: 12px; color: var(--muted); margin: 4px 0; }
</style>
