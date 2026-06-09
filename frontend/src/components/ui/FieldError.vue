<script setup lang="ts">
defineProps<{
  message?: string
}>()
</script>

<template>
  <p v-if="message" class="field-error">
    {{ message }}
  </p>
</template>

<style scoped>
.field-error {
  margin: -2px 0 0;
  padding-left: 10px;
  border-left: 3px solid #dc2626;
  color: #b91c1c;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.45;
}
</style>
