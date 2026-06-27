<script setup>
import { computed, ref } from 'vue'

// A native date picker that normalizes its value: accepts an ISO datetime or a
// YYYY-MM-DD string, and emits YYYY-MM-DD (or null when cleared).
const props = defineProps({
  modelValue: { type: [String, null], default: '' },
})
const emit = defineEmits(['update:modelValue'])

const el = ref(null)

const dateStr = computed({
  get() {
    if (!props.modelValue) return ''
    const s = String(props.modelValue)
    return s.length >= 10 ? s.slice(0, 10) : s
  },
  set(v) {
    emit('update:modelValue', v || null)
  },
})

// Open the native calendar on click anywhere in the field (where supported),
// so users don't have to hit the tiny indicator icon.
function openPicker() {
  try {
    el.value?.showPicker?.()
  } catch {
    /* showPicker throws if not user-activated or unsupported; ignore */
  }
}
</script>

<template>
  <input ref="el" type="date" v-model="dateStr" @click="openPicker" />
</template>

<style scoped>
input[type='date']::-webkit-calendar-picker-indicator {
  cursor: pointer;
}
</style>
