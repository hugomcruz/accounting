<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { RouterView } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

onMounted(() => {
  if (auth.isAuthenticated) {
    auth.setupSession()
  }
})

onUnmounted(() => {
  auth.teardownSession()
})
</script>

<template>
  <RouterView />
</template>
