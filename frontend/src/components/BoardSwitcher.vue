<script setup>
import { onMounted } from 'vue'
import { useBoardStore } from '@/stores/board'

const board = useBoardStore()

onMounted(() => board.load())

function onChange(e) {
  board.setActive(e.target.value)
}
</script>

<template>
  <select
    v-if="board.boards.length"
    class="board-switcher"
    :value="board.activeId"
    title="Active board"
    @change="onChange"
  >
    <option v-for="b in board.boards" :key="b.id" :value="b.id">{{ b.name }}</option>
  </select>
</template>

<style scoped>
.board-switcher {
  width: auto;
  min-width: 120px;
  max-width: 200px;
  padding: 6px 8px;
  font-size: 13px;
}
</style>
