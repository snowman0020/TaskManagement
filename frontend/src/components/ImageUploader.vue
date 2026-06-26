<script setup>
import { ref, watch, onUnmounted } from 'vue'
import client from '@/api/client'

const props = defineProps({
  task: { type: Object, default: null },
})
const emit = defineEmits(['update:pending', 'changed'])

const ALLOWED = ['image/png', 'image/jpeg', 'image/webp', 'image/gif']
const MAX_BYTES = 5 * 1024 * 1024
const MAX_IMAGES = 10

const existing = ref([]) // { id, url, filename } — object URLs from authed blob fetch
const pending = ref([]) // { file, url, name }
const error = ref('')
const dragOver = ref(false)

function total() {
  return existing.value.length + pending.value.length
}

function emitPending() {
  emit('update:pending', pending.value.map((p) => p.file))
}

function revokeAll() {
  existing.value.forEach((p) => URL.revokeObjectURL(p.url))
  pending.value.forEach((p) => URL.revokeObjectURL(p.url))
}

// Existing images require the Authorization header, so a plain <img src> won't
// work — fetch each as a blob and render via an object URL.
async function loadExisting() {
  existing.value.forEach((p) => URL.revokeObjectURL(p.url))
  existing.value = []
  const t = props.task
  if (!t?.id || !t.images?.length) return
  for (const im of t.images) {
    try {
      const { data } = await client.get(`/api/tasks/${t.id}/images/${im.id}`, {
        responseType: 'blob',
      })
      existing.value.push({ id: im.id, url: URL.createObjectURL(data), filename: im.filename })
    } catch {
      /* skip an image that failed to load */
    }
  }
}

function addFiles(fileList) {
  error.value = ''
  for (const f of Array.from(fileList)) {
    if (total() >= MAX_IMAGES) {
      error.value = `You can attach at most ${MAX_IMAGES} images`
      break
    }
    if (!ALLOWED.includes(f.type)) {
      error.value = `"${f.name}" is not a supported image (PNG, JPEG, WebP, GIF)`
      continue
    }
    if (f.size > MAX_BYTES) {
      error.value = `"${f.name}" is larger than 5 MB`
      continue
    }
    pending.value.push({ file: f, url: URL.createObjectURL(f), name: f.name })
  }
  emitPending()
}

function onPick(e) {
  addFiles(e.target.files)
  e.target.value = '' // allow re-picking the same file
}

function onDrop(e) {
  dragOver.value = false
  if (e.dataTransfer?.files) addFiles(e.dataTransfer.files)
}

function removePending(idx) {
  URL.revokeObjectURL(pending.value[idx].url)
  pending.value.splice(idx, 1)
  emitPending()
}

async function removeExisting(idx) {
  const img = existing.value[idx]
  try {
    await client.delete(`/api/tasks/${props.task.id}/images/${img.id}`)
    URL.revokeObjectURL(img.url)
    existing.value.splice(idx, 1)
    emit('changed')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to delete image'
  }
}

watch(() => props.task, loadExisting, { immediate: true })
onUnmounted(revokeAll)
</script>

<template>
  <div class="field">
    <label>Attachments ({{ total() }}/{{ MAX_IMAGES }})</label>

    <div
      class="dropzone"
      :class="{ over: dragOver }"
      @dragover.prevent="dragOver = true"
      @dragleave.prevent="dragOver = false"
      @drop.prevent="onDrop"
    >
      <input
        type="file"
        multiple
        accept="image/png,image/jpeg,image/webp,image/gif"
        @change="onPick"
      />
      <span class="hint">Drop images here or choose files — PNG, JPEG, WebP, GIF · max 5 MB each</span>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="total()" class="thumbs">
      <div v-for="(p, i) in existing" :key="'e-' + p.id" class="thumb" :title="p.filename">
        <img :src="p.url" :alt="p.filename" />
        <button type="button" class="thumb-x" title="Remove" @click="removeExisting(i)">×</button>
      </div>
      <div v-for="(p, i) in pending" :key="'p-' + i" class="thumb pending" :title="p.name">
        <img :src="p.url" :alt="p.name" />
        <button type="button" class="thumb-x" title="Remove" @click="removePending(i)">×</button>
        <span class="badge new-badge">new</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dropzone {
  border: 1px dashed var(--border);
  border-radius: 6px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--input-bg);
}
.dropzone.over {
  border-color: var(--primary);
  background: var(--nav-active-bg);
}
.dropzone input[type='file'] {
  width: 100%;
}
.hint {
  font-size: 12px;
  color: var(--muted);
}
.thumbs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}
.thumb {
  position: relative;
  width: 72px;
  height: 72px;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid var(--border);
  background: var(--col-bg);
}
.thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.thumb-x {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 20px;
  height: 20px;
  padding: 0;
  border-radius: 50%;
  background: var(--backdrop);
  color: #fff;
  font-size: 14px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
.thumb .new-badge {
  position: absolute;
  bottom: 2px;
  left: 2px;
  background: var(--primary);
  color: var(--on-primary);
}
</style>
