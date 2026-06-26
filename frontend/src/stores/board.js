import { defineStore } from 'pinia'
import client from '@/api/client'

// Active board selection, shared across views and persisted across reloads.
export const useBoardStore = defineStore('board', {
  state: () => ({
    boards: [],
    activeId: localStorage.getItem('activeBoard') || '',
    loaded: false,
  }),
  getters: {
    active: (s) => s.boards.find((b) => b.id === s.activeId) || null,
  },
  actions: {
    async load() {
      if (this.loaded) return
      const { data } = await client.get('/api/boards')
      this.boards = data
      if (!this.activeId || !data.find((b) => b.id === this.activeId)) {
        this.activeId = data[0]?.id || ''
        this._persist()
      }
      this.loaded = true
    },
    async reload() {
      this.loaded = false
      await this.load()
    },
    setActive(id) {
      this.activeId = id
      this._persist()
    },
    _persist() {
      try {
        localStorage.setItem('activeBoard', this.activeId)
      } catch {
        /* ignore */
      }
    },
  },
})
