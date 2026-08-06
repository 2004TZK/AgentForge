<script setup lang="ts">
// 根组件：全局星海背景（WebGL Galaxy）+ 路由出口（布局由各页面按需包裹）
import Galaxy from './components/common/Galaxy.vue'
</script>

<template>
  <div class="app-bg" aria-hidden="true">
    <Galaxy
      :hue-shift="42"
      :saturation="0.75"
      :glow-intensity="0.5"
      :density="1.2"
      :star-speed="0.4"
      :twinkle-intensity="0.5"
      :rotation-speed="0.03"
      :speed="0.8"
    />
  </div>
  <div class="app-view">
    <router-view />
  </div>
</template>

<style>
/* 星海背景：固定铺满视口、置于内容之下、不拦截鼠标 */
.app-bg {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
}

/* 内容层：保持 #app → 页面 height:100% 链路，并盖在星海之上 */
.app-view {
  position: relative;
  z-index: 1;
  height: 100%;
}
</style>
