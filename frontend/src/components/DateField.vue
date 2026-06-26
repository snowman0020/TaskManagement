<script setup>
import { computed } from 'vue'

// A native date picker that normalizes its value: accepts an ISO datetime or a
// YYYY-MM-DD string, and emits YYYY-MM-DD (or null when cleared).
const props = defineProps({
  modelValue: { type: [String, null], default: '' },
})
const emit = defineEmits(['update:modelValue'])

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
</script>

<template>
  <input type="date" v-model="dateStr" />
</template>
