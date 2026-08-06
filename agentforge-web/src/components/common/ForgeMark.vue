<script setup lang="ts">
/** 品牌星印：深空方块中亮起的「A」，像夜空中最亮的星 */
withDefaults(defineProps<{ size?: number }>(), { size: 30 })
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 32 32"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    role="img"
    aria-label="AgentForge"
  >
    <rect x="1.5" y="1.5" width="29" height="29" rx="7" fill="#0a0f24" stroke="#ffcf6b" stroke-width="1.6" />
    <path
      d="M9 22 L16 9.5 L23 22 M12 18.2 H20"
      stroke="#ffcf6b"
      stroke-width="2.6"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  </svg>
</template>
