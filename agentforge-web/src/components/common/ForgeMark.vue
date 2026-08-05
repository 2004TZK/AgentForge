<script setup lang="ts">
/** 品牌钢印：锻黑方块中烧出的「A」，像热烙在零件上的标记 */
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
    <rect x="1.5" y="1.5" width="29" height="29" rx="7" fill="#17130c" stroke="#e8590c" stroke-width="1.6" />
    <path
      d="M9 22 L16 9.5 L23 22 M12 18.2 H20"
      stroke="#e8590c"
      stroke-width="2.6"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  </svg>
</template>
