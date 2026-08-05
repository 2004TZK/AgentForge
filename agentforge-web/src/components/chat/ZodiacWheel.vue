<script setup lang="ts">
/**
 * 黄道圈示意图（M3.3.1）：SVG 绘制本命盘——星座带 / 宫位线 / 四轴 / 行星点位 / 相位连线。
 * 配色按手册约定：合=黄、拱=绿、六合=蓝、刑=红、冲=紫红（锻火橙仅行星点位描边）。
 * 交互（M3.3.2）：行星/相位/宫位 hover 高亮 + 原生 tooltip 说明。
 */
import { computed } from 'vue'
import type { StarChartData } from '../../types/chat'

const props = defineProps<{ chart: StarChartData }>()

const CX = 170
const CY = 170
const R_ZODIAC_OUTER = 158 // 星座带外缘
const R_ZODIAC_INNER = 134 // 星座带内缘 / 宫位线外端
const R_HOUSE_INNER = 84 // 宫位线内端
const R_PLANET = 108 // 行星点位半径
const R_AXIS = 162 // 四轴标记半径

const SIGNS = ['白羊', '金牛', '双子', '巨蟹', '狮子', '处女', '天秤', '天蝎', '射手', '摩羯', '水瓶', '双鱼']

const PLANET_ZH: Record<string, string> = {
  sun: '太阳', moon: '月亮', mercury: '水星', venus: '金星', mars: '火星',
  jupiter: '木星', saturn: '土星', uranus: '天王星', neptune: '海王星', pluto: '冥王星',
}
const PLANET_ORDER = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto']

/** 相位类型 → 连线颜色（手册约定） */
const ASPECT_COLOR: Record<string, string> = {
  conjunction: '#d9b64e', // 合：白/黄
  trine: '#4a7c59', // 拱：绿
  sextile: '#4a6fa5', // 六合：蓝
  square: '#c0392b', // 刑：红
  opposition: '#8e44ad', // 冲：紫红
}
const ASPECT_SHORT: Record<string, string> = {
  conjunction: '合', opposition: '冲', trine: '拱', square: '刑', sextile: '六合',
}

/** 黄道经度 → 屏幕坐标（longitude 0°=白羊头在顶部，逆时针递增） */
function pt(lng: number, r: number) {
  const a = (lng * Math.PI) / 180
  return { x: CX + r * Math.sin(a), y: CY - r * Math.cos(a) }
}

/** 扇形 path（startLng → endLng，环 r2→r1） */
function sectorPath(startLng: number, endLng: number, r2: number, r1: number): string {
  const p1 = pt(startLng, r2)
  const p2 = pt(endLng, r2)
  const p3 = pt(endLng, r1)
  const p4 = pt(startLng, r1)
  return `M ${p1.x} ${p1.y} A ${r2} ${r2} 0 0 1 ${p2.x} ${p2.y} L ${p3.x} ${p3.y} A ${r1} ${r1} 0 0 0 ${p4.x} ${p4.y} Z`
}

/** 星座带 12 段（每段 30°，交替底色） */
const zodiacSegs = computed(() =>
  SIGNS.map((name, i) => {
    const start = i * 30
    return {
      name,
      index: i,
      start,
      path: sectorPath(start, start + 30, R_ZODIAC_OUTER, R_ZODIAC_INNER),
      label: pt(start + 15, (R_ZODIAC_OUTER + R_ZODIAC_INNER) / 2),
    }
  }),
)

/** 宫位扇形（两宫头之间，hover 显示宫号/星座/行星） */
const houseSegs = computed(() => {
  const houses = props.chart.houses
  const cusps = Array.from({ length: 12 }, (_, i) => houses[String(i + 1)]?.cusp ?? 0)
  return cusps.map((cusp, i) => {
    const next = cusps[(i + 1) % 12] + (i === 11 ? 360 : 0)
    const h = houses[String(i + 1)]
    return {
      num: i + 1,
      sign: h?.sign ?? '',
      planets: (h?.planets ?? []).map((k) => PLANET_ZH[k] ?? k),
      path: sectorPath(cusp, next, R_ZODIAC_INNER, R_HOUSE_INNER),
      cusp,
    }
  })
})

/** 行星点位 */
const planetPoints = computed(() =>
  PLANET_ORDER.map((key) => {
    const p = props.chart.planets[key]
    if (!p) return null
    const pos = pt(p.longitude, R_PLANET)
    return { key, zh: PLANET_ZH[key] ?? key, pos, planet: p }
  }).filter(Boolean) as Array<{
    key: string
    zh: string
    pos: { x: number; y: number }
    planet: { sign: string; degree: number; house: number; retrograde: boolean }
  }>,
)

/** 四轴标记（ASC 左、MC 顶按 longitude 定位，标注在圈外） */
const axes = computed(() => {
  const c = props.chart
  return [
    { key: 'ASC', lng: c.ascendant?.longitude ?? 0 },
    { key: 'MC', lng: c.midheaven?.longitude ?? 0 },
    { key: 'DES', lng: c.descendant?.longitude ?? 0 },
    { key: 'IC', lng: c.imum_coeli?.longitude ?? 0 },
  ].map((a) => {
    const inner = pt(a.lng, R_ZODIAC_OUTER + 4)
    const outer = pt(a.lng, R_AXIS)
    const label = pt(a.lng, R_AXIS + 12)
    return { ...a, inner, outer, label }
  })
})

/** 相位连线（行星两两，颜色按类型；同一点对取 orb 更小者） */
const aspectLines = computed(() => {
  const planets = props.chart.planets
  return props.chart.aspects
    .map((a) => {
      const p1 = planets[a.p1]
      const p2 = planets[a.p2]
      if (!p1 || !p2) return null
      return {
        key: `${a.p1}-${a.typeEn}-${a.p2}`,
        p1: pt(p1.longitude, R_PLANET),
        p2: pt(p2.longitude, R_PLANET),
        color: ASPECT_COLOR[a.typeEn] ?? 'var(--steel)',
        title: `${PLANET_ZH[a.p1] ?? a.p1} ${ASPECT_SHORT[a.typeEn] ?? a.type} ${PLANET_ZH[a.p2] ?? a.p2} · ${a.orb}°`,
      }
    })
    .filter(Boolean) as Array<{ key: string; p1: { x: number; y: number }; p2: { x: number; y: number }; color: string; title: string }>
})
</script>

<template>
  <svg class="zodiac-wheel" viewBox="0 0 340 340" role="img" aria-label="黄道圈示意图">
    <!-- 星座带 -->
    <g v-for="(seg, i) in zodiacSegs" :key="`z-${seg.index}`">
      <path :d="seg.path" :class="['zodiac-seg', { alt: i % 2 === 1 }]" />
      <text class="zodiac-sign" :x="seg.label.x" :y="seg.label.y" text-anchor="middle">{{ seg.name }}</text>
    </g>
    <!-- 宫位扇形（hover 高亮 + 说明） -->
    <g v-for="seg in houseSegs" :key="`h-${seg.num}`">
      <path :d="seg.path" class="house-seg">
        <title>{{ `第${seg.num}宫 · ${seg.sign || '—'}` + (seg.planets.length ? ` · ${seg.planets.join(' ')}` : '') }}</title>
      </path>
    </g>
    <!-- 相位连线 -->
    <g v-for="line in aspectLines" :key="`a-${line.key}`">
      <line :x1="line.p1.x" :y1="line.p1.y" :x2="line.p2.x" :y2="line.p2.y" class="aspect-line" :stroke="line.color">
        <title>{{ line.title }}</title>
      </line>
    </g>
    <!-- 宫位号 -->
    <text v-for="seg in houseSegs" :key="`hn-${seg.num}`" class="house-num"
      :x="pt(seg.cusp + 15, (R_ZODIAC_INNER + R_HOUSE_INNER) / 2).x"
      :y="pt(seg.cusp + 15, (R_ZODIAC_INNER + R_HOUSE_INNER) / 2).y" text-anchor="middle">{{ seg.num }}</text>
    <!-- 行星 -->
    <g v-for="p in planetPoints" :key="`p-${p.key}`" class="planet">
      <circle :cx="p.pos.x" :cy="p.pos.y" r="4.5" fill="var(--card, #fffdf7)" stroke="var(--forge, #b54300)" stroke-width="1.6" />
      <text class="planet-label" :x="p.pos.x" :y="p.pos.y - 8" text-anchor="middle">
        {{ p.zh }}<tspan class="planet-retro">{{ p.planet.retrograde ? '℞' : '' }}</tspan>
      </text>
      <title>{{ `${p.zh} ${p.planet.sign} ${p.planet.degree.toFixed(1)}° · 第${p.planet.house}宫${p.planet.retrograde ? ' · 逆行' : ''}` }}</title>
    </g>
    <!-- 四轴 -->
    <g v-for="a in axes" :key="`ax-${a.key}`" class="axis">
      <line :x1="a.inner.x" :y1="a.inner.y" :x2="a.outer.x" :y2="a.outer.y" />
      <text class="axis-label" :x="a.label.x" :y="a.label.y" text-anchor="middle">{{ a.key }}</text>
    </g>
  </svg>
</template>

<style scoped>
/* 锻造工坊：纸墨钢 + 发丝线；黄道圈是示意图不是精密仪器，功能色只给相位连线 */
.zodiac-wheel {
  width: 100%;
  max-width: 300px;
  height: auto;
  display: block;
  margin: 0 auto 6px;
}
.zodiac-seg {
  fill: var(--card, #fffdf7);
  stroke: var(--line, #e1dacb);
  stroke-width: 0.8;
}
.zodiac-seg.alt {
  fill: var(--paper, #f4f0e8);
}
.zodiac-sign {
  font-size: 8.5px;
  fill: var(--steel, #6f6a5b);
  letter-spacing: 1px;
}
.house-seg {
  fill: transparent;
  stroke: var(--line, #e1dacb);
  stroke-width: 0.7;
  cursor: default;
  transition: fill 0.15s;
}
.house-seg:hover {
  fill: var(--forge-glow, #e8590c);
  fill-opacity: 0.08;
  stroke-width: 1.1;
}
.house-num {
  font-family: var(--font-mono, monospace);
  font-size: 8px;
  fill: var(--steel, #6f6a5b);
}
.aspect-line {
  stroke-width: 1.2;
  opacity: 0.75;
  transition: stroke-width 0.15s, opacity 0.15s;
}
.aspect-line:hover {
  stroke-width: 2.2;
  opacity: 1;
}
.planet {
  cursor: default;
}
.planet circle {
  transition: r 0.15s;
}
.planet:hover circle {
  stroke: var(--ink, #221d15);
  stroke-width: 2.2;
}
.planet-label {
  font-size: 8px;
  fill: var(--ink, #221d15);
  font-weight: 500;
  pointer-events: none;
}
.planet-retro {
  fill: var(--forge, #b54300);
  font-size: 7px;
}
.axis line {
  stroke: var(--ink-deep, #17130c);
  stroke-width: 1.3;
}
.axis-label {
  font-family: var(--font-mono, monospace);
  font-size: 8.5px;
  font-weight: 600;
  fill: var(--ink-deep, #17130c);
}
</style>
