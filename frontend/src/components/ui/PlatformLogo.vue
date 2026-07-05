<script setup lang="ts">
import AppIcon from './AppIcon.vue'

withDefaults(defineProps<{ platform: string; size?: number }>(), { size: 18 })

// Official app icons provided by the user (frontend/public/platform-logos/).
// Falls back to a neutral generic icon for any platform not in this set.
const LOGO_FILES: Record<string, string> = {
  xhs: 'xhs.jpg',
  dy: 'dy.jpg',
  ks: 'ks.png',
  bili: 'bili.png',
  wb: 'wb.jpg',
  tieba: 'tieba.png',
  zhihu: 'zhihu.webp',
  xianyu: 'xianyu.png',
}
</script>

<template>
  <img
    v-if="LOGO_FILES[platform]"
    :src="`/platform-logos/${LOGO_FILES[platform]}`"
    :width="size"
    :height="size"
    class="platform-logo"
    alt=""
  />
  <AppIcon v-else name="layers" :size="size" />
</template>

<style scoped>
.platform-logo {
  flex-shrink: 0;
  border-radius: 22%;
  object-fit: cover;
}
</style>
