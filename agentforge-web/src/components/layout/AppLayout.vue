<script lang="ts">
// 模块级共享状态：布局组件在路由切换时会整体重挂载，
// 用普通 <script> 块声明，跨实例传递"待播放粒子迸发"标志。
let pendingBurst = false
let pendingBurstTimer: number | undefined
</script>

<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, useTemplateRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ForgeMark from '../common/ForgeMark.vue'
import { useAuthStore } from '../../stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

function logout(): void {
  authStore.logout()
  router.push('/login')
}

/* ── Gooey 导航（左侧主导航）：激活药丸 + 粒子迸发 + 文字反色 ── */
interface NavItem {
  label: string
  to: string
}

const NAV_ITEMS: NavItem[] = [
  { label: '智能体', to: '/agents' },
  { label: '对话', to: '/chat' },
  { label: '文件', to: '/files' },
  { label: '工具', to: '/tools' },
  { label: '工作流', to: '/workflows' },
  { label: '模型', to: '/models' },
]

const ANIMATION_TIME = 600
const PARTICLE_COUNT = 15
const PARTICLE_DISTANCES: [number, number] = [90, 10]
const PARTICLE_R = 100
const TIME_VARIANCE = 300
const COLORS = [1, 2, 3, 1, 2, 3, 1, 4]

const containerRef = useTemplateRef<HTMLDivElement>('containerRef')
const navRef = useTemplateRef<HTMLUListElement>('navRef')
const filterRef = useTemplateRef<HTMLSpanElement>('filterRef')
const textRef = useTemplateRef<HTMLSpanElement>('textRef')
const starsRef = useTemplateRef<HTMLSpanElement>('starsRef')
const activeIndex = ref(-1)

let resizeObserver: ResizeObserver | null = null

const noise = (n = 1): number => n / 2 - Math.random() * n

const getXY = (distance: number, pointIndex: number, totalPoints: number): [number, number] => {
  const angle = ((360 + noise(8)) / totalPoints) * pointIndex * (Math.PI / 180)
  return [distance * Math.cos(angle), distance * Math.sin(angle)]
}

const createParticle = (i: number, t: number, d: [number, number], r: number) => {
  const rotate = noise(r / 10)
  return {
    start: getXY(d[0], PARTICLE_COUNT - i, PARTICLE_COUNT),
    end: getXY(d[1] + noise(7), PARTICLE_COUNT - i, PARTICLE_COUNT),
    time: t,
    scale: 1 + noise(0.2),
    color: COLORS[Math.floor(Math.random() * COLORS.length)],
    rotate: rotate > 0 ? (rotate + r / 20) * 10 : (rotate - r / 20) * 10,
  }
}

const makeParticles = (element: HTMLElement): void => {
  const d: [number, number] = PARTICLE_DISTANCES
  const r = PARTICLE_R
  const bubbleTime = ANIMATION_TIME * 2 + TIME_VARIANCE
  element.style.setProperty('--time', `${bubbleTime}ms`)
  for (let i = 0; i < PARTICLE_COUNT; i++) {
    const t = ANIMATION_TIME * 2 + noise(TIME_VARIANCE * 2)
    const p = createParticle(i, t, d, r)
    setTimeout(() => {
      const particle = document.createElement('span')
      const point = document.createElement('span')
      particle.classList.add('particle')
      particle.style.setProperty('--start-x', `${p.start[0]}px`)
      particle.style.setProperty('--start-y', `${p.start[1]}px`)
      particle.style.setProperty('--end-x', `${p.end[0]}px`)
      particle.style.setProperty('--end-y', `${p.end[1]}px`)
      particle.style.setProperty('--time', `${p.time}ms`)
      particle.style.setProperty('--scale', `${p.scale}`)
      particle.style.setProperty('--color', `var(--color-${p.color}, white)`)
      particle.style.setProperty('--rotate', `${p.rotate}deg`)
      point.classList.add('point')
      particle.appendChild(point)
      element.appendChild(particle)
      setTimeout(() => {
        try {
          element.removeChild(particle)
        } catch {
          /* 粒子已移除则忽略 */
        }
      }, t)
    }, 30)
  }
}

const updateEffectPosition = (element: HTMLElement): void => {
  if (!containerRef.value || !filterRef.value || !textRef.value || !starsRef.value) return
  const containerRect = containerRef.value.getBoundingClientRect()
  const pos = element.getBoundingClientRect()
  const styles = {
    left: `${pos.x - containerRect.x}px`,
    top: `${pos.y - containerRect.y}px`,
    width: `${pos.width}px`,
    height: `${pos.height}px`,
  }
  Object.assign(filterRef.value.style, styles)
  Object.assign(textRef.value.style, styles)
  Object.assign(starsRef.value.style, styles)
  textRef.value.innerText = element.innerText
}

const positionActive = (): void => {
  if (!navRef.value || activeIndex.value < 0) return
  const activeLi = navRef.value.querySelectorAll('li')[activeIndex.value] as HTMLElement | undefined
  if (activeLi) {
    updateEffectPosition(activeLi)
    textRef.value?.classList.add('active')
  }
}

const burst = (): void => {
  if (!starsRef.value || !textRef.value || !filterRef.value) return
  starsRef.value.querySelectorAll('.particle').forEach((p) => {
    starsRef.value?.removeChild(p)
  })
  textRef.value.classList.remove('active')
  void textRef.value.offsetWidth
  textRef.value.classList.add('active')
  // 药丸生长动画（gooey 滤镜层）+ 星星粒子（独立层，保留颜色与辉光）
  filterRef.value.classList.remove('active')
  void filterRef.value.offsetWidth
  filterRef.value.classList.add('active')
  makeParticles(starsRef.value)
}

const handleClick = (index: number): void => {
  if (indexForPath(route.path) === index) return
  // 立即反馈：先把药丸移到目标项；新页面挂载后再触发粒子迸发
  activeIndex.value = index
  positionActive()
  pendingBurst = true
  if (pendingBurstTimer) window.clearTimeout(pendingBurstTimer)
  pendingBurstTimer = window.setTimeout(() => {
    pendingBurst = false
  }, 1200)
}

const indexForPath = (path: string): number => {
  const index = NAV_ITEMS.findIndex((item) => path.startsWith(item.to))
  return index >= 0 ? index : 0
}

watch(
  () => route.path,
  (path) => {
    const index = indexForPath(path)
    if (index !== activeIndex.value) {
      activeIndex.value = index
    } else {
      requestAnimationFrame(positionActive)
    }
  },
)

watch(activeIndex, () => {
  requestAnimationFrame(positionActive)
})

onMounted(async () => {
  activeIndex.value = indexForPath(route.path)
  await nextTick()
  positionActive()
  // 若刚点击导航跳转而来，在新实例上播放药丸生长 + 粒子迸发
  if (pendingBurst) {
    pendingBurst = false
    if (pendingBurstTimer) window.clearTimeout(pendingBurstTimer)
    requestAnimationFrame(() => burst())
  }
  if (containerRef.value) {
    resizeObserver = new ResizeObserver(() => positionActive())
    resizeObserver.observe(containerRef.value)
  }
  // 窄屏横向滚动时跟随激活项
  navRef.value?.addEventListener('scroll', positionActive)
})

onUnmounted(() => {
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  navRef.value?.removeEventListener('scroll', positionActive)
})
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <router-link to="/agents" class="wordmark">
        <ForgeMark :size="26" />
        <span class="wordmark-text">AGENTFORGE</span>
      </router-link>

      <!-- Gooey 导航：激活药丸 + 粒子迸发（效果层在文字层之下） -->
      <div class="nav" ref="containerRef">
        <nav class="nav-list" aria-label="主导航">
          <ul ref="navRef">
            <li
              v-for="(item, index) in NAV_ITEMS"
              :key="item.to"
              :class="{ active: activeIndex === index }"
            >
              <router-link :to="item.to" @click="handleClick(index)">{{ item.label }}</router-link>
            </li>
          </ul>
        </nav>
        <span class="effect filter" ref="filterRef" />
        <span class="effect text" ref="textRef" />
        <span class="effect stars" ref="starsRef" />
      </div>

      <div class="sidebar-foot">
        <span class="mono-mini">v1.0.0 · MIT</span>
        <span class="mono-mini">FORGE YOUR AGENTS</span>
      </div>
    </aside>

    <div class="main">
      <header class="topbar">
        <span class="crumb mono-mini">
          <span class="crumb-root">WORKSHOP</span>
          <span class="crumb-sep">/</span>
          <span class="crumb-page">{{ route.meta.title ?? '' }}</span>
        </span>
        <div class="user-area">
          <span class="username mono-mini">{{ authStore.user?.username ?? 'ANON' }}</span>
          <button class="btn btn-secondary btn-sm" @click="logout">退出</button>
        </div>
      </header>
      <main class="content">
        <slot />
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  height: 100%;
}

/* ---- 深空侧栏：夜蓝 + 星云微光 ---- */
.sidebar {
  width: 216px;
  background-color: rgba(10, 15, 36, 0.72); /* 半透明深空：星海透出，文字仍可读 */
  color: var(--card);
  background-image:
    radial-gradient(ellipse 90% 45% at 15% 0%, rgba(88, 101, 242, 0.2), transparent 60%),
    radial-gradient(ellipse 70% 40% at 100% 100%, rgba(168, 85, 247, 0.16), transparent 60%);
  padding: 18px 14px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 26px;
}

.wordmark {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 2px 6px;
  text-decoration: none;
}

.wordmark-text {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.24em;
  color: var(--card);
}

/* ── Gooey 导航 ── */
.nav {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  /* 星星粒子配色（深空星云：暖白星光 / 星辉金 / 冷白星光 / 星云紫） */
  --color-1: #fff7e6;
  --color-2: #ffd873;
  --color-3: #c7d7ff;
  --color-4: #b794f6;
}

.nav-list ul {
  position: relative;
  z-index: 3;
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
  color: rgba(255, 253, 247, 0.62);
  text-shadow: 0 1px 1px hsl(205deg 30% 10% / 0.2);
}

.nav-list li {
  position: relative;
  border-radius: 9999px;
  cursor: pointer;
  transition:
    background-color 0.3s,
    color 0.3s,
    box-shadow 0.3s;
  box-shadow: 0 0 0.5px 1.5px transparent;
}

.nav-list li a {
  display: inline-block;
  padding: 10px 12px;
  color: inherit;
  font-size: 14px;
  text-decoration: none;
  outline: none;
  white-space: nowrap;
}

/* 悬停：亮星金，激活项保持深色反字 */
.nav-list li:not(.active) a:hover {
  color: var(--forge-glow);
}

/* 激活项：文字反色（白色药丸上深色字） */
.nav-list li.active {
  color: var(--ink-deep);
  text-shadow: none;
  font-weight: 600;
}

.nav-list li.active::after {
  opacity: 1;
  transform: scale(1);
}

.nav-list li::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 8px;
  background: var(--forge);
  opacity: 0;
  transform: scale(0);
  transition: all 0.3s ease;
  z-index: -1;
}

.nav-list li.active::after {
  box-shadow: 0 0 16px -2px rgba(255, 207, 107, 0.55);
}

/* ── 效果层：药丸（gooey 滤镜）+ 文字副本 + 粒子 ── */
.effect {
  position: absolute;
  opacity: 1;
  pointer-events: none;
  display: grid;
  place-items: center;
  z-index: 1;
}

.effect.text {
  color: rgba(255, 253, 247, 0.62);
  transition: color 0.3s ease;
}

.effect.text.active {
  color: var(--ink-deep);
}

.effect.filter {
  filter: blur(7px) contrast(100) blur(0);
  mix-blend-mode: lighten;
}

/* 星星粒子独立层：不经过 gooey 对比度滤镜，保留星辉色与光晕 */
.effect.stars {
  z-index: 2;
}

.effect.filter::before {
  content: '';
  position: absolute;
  inset: -75px;
  z-index: -2;
  background: black;
}

.effect.filter::after {
  content: '';
  position: absolute;
  inset: 0;
  background: var(--forge);
  transform: scale(0);
  opacity: 0;
  z-index: -1;
  border-radius: 9999px;
}

.effect.active::after {
  animation: pill 0.3s ease both;
}

@keyframes pill {
  to {
    transform: scale(1);
    opacity: 1;
  }
}

.sidebar-foot {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 0 6px;
  color: rgba(255, 253, 247, 0.35);
}

.mono-mini {
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

/* ---- 主区 ---- */
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.topbar {
  height: 52px;
  background: var(--card);
  border-bottom: 1px solid var(--line);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}

.crumb {
  color: var(--steel);
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
}

.crumb-page {
  overflow: hidden;
  text-overflow: ellipsis;
}

.crumb-root {
  color: var(--forge);
}

.crumb-sep {
  opacity: 0.6;
}

.user-area {
  display: flex;
  align-items: center;
  gap: 12px;
}

.username {
  color: var(--steel);
}

.content {
  flex: 1;
  overflow-y: auto;
}

/* ---- 响应式：窄屏收成顶栏 ---- */
@media (max-width: 860px) {
  .layout {
    flex-direction: column;
  }

  .sidebar {
    width: 100%;
    flex-direction: row;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
  }

  .wordmark-text {
    display: none;
  }

  .nav {
    flex: 1;
    min-width: 0;
  }

  .nav-list ul {
    flex-direction: row;
    overflow-x: auto;
    scrollbar-width: none;
  }

  .nav-list ul::-webkit-scrollbar {
    display: none;
  }

  .nav-list li a {
    padding: 7px 12px;
  }

  .sidebar-foot {
    display: none;
  }

  .crumb-root,
  .crumb-sep {
    display: none;
  }
}
</style>

<style>
/* 粒子由 JS 动态创建（无 scoped 属性），样式必须放在非 scoped 块 */
.particle,
.point {
  display: block;
  opacity: 0;
  width: 20px;
  height: 20px;
  border-radius: 9999px;
  transform-origin: center;
}

.particle {
  --time: 5s;
  position: absolute;
  top: calc(50% - 8px);
  left: calc(50% - 8px);
  animation: particle calc(var(--time)) ease 1 -350ms;
}

.point {
  /* 星星粒子：5 角星剪影 + 亮核渐变（白色核心 → 星云色边缘） */
  background: radial-gradient(circle at 35% 35%, #fffdf7 0%, var(--color) 72%);
  clip-path: polygon(
    50% 0%,
    61% 35%,
    98% 35%,
    68% 57%,
    79% 91%,
    50% 70%,
    21% 91%,
    32% 57%,
    2% 35%,
    39% 35%
  );
  opacity: 1;
  filter: drop-shadow(0 0 5px var(--color));
  animation: point calc(var(--time)) ease 1 -350ms;
}

@keyframes particle {
  0% {
    transform: rotate(0deg) translate(calc(var(--start-x)), calc(var(--start-y)));
    opacity: 1;
    animation-timing-function: cubic-bezier(0.55, 0, 1, 0.45);
  }
  70% {
    transform: rotate(calc(var(--rotate) * 0.5)) translate(calc(var(--end-x) * 1.2), calc(var(--end-y) * 1.2));
    opacity: 1;
    animation-timing-function: ease;
  }
  85% {
    transform: rotate(calc(var(--rotate) * 0.66)) translate(calc(var(--end-x)), calc(var(--end-y)));
    opacity: 1;
  }
  100% {
    transform: rotate(calc(var(--rotate) * 1.2)) translate(calc(var(--end-x) * 0.5), calc(var(--end-y) * 0.5));
    opacity: 1;
  }
}

@keyframes point {
  0% {
    transform: scale(0);
    opacity: 0;
    animation-timing-function: cubic-bezier(0.55, 0, 1, 0.45);
  }
  25% {
    transform: scale(calc(var(--scale) * 0.25));
  }
  38% {
    opacity: 1;
  }
  65% {
    transform: scale(var(--scale));
    opacity: 1;
    animation-timing-function: ease;
  }
  85% {
    transform: scale(var(--scale));
    opacity: 1;
  }
  100% {
    transform: scale(0);
    opacity: 0;
  }
}
</style>
