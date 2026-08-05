<script setup lang="ts">
/**
 * 排盘卡片（M2.5）：渲染 star_chart 工具返回的结构化星盘数据。
 * 四轴 / 行星落座落宫 / 相位 / 格局 / 宫位，锻造工坊风格表格。
 * 数据由 chat store 在 onTool 事件中解析 JSON 填充（msg.chart）。
 */
import type { StarChartData } from '../../types/chat'

defineProps<{ chart: StarChartData }>()

/** 行星英文键 → 中文名 */
const PLANET_ZH: Record<string, string> = {
  sun: '太阳',
  moon: '月亮',
  mercury: '水星',
  venus: '金星',
  mars: '火星',
  jupiter: '木星',
  saturn: '土星',
  uranus: '天王星',
  neptune: '海王星',
  pluto: '冥王星',
}

/** 相位类型 → 短标签 */
const ASPECT_SHORT: Record<string, string> = {
  conjunction: '合',
  opposition: '冲',
  trine: '拱',
  square: '刑',
  sextile: '六合',
}

const PLANET_ORDER = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto']

function planetName(key: string): string {
  return PLANET_ZH[key] ?? key
}

function formatDegree(degree: number): string {
  return degree.toFixed(1).replace(/\.0$/, '')
}
</script>

<template>
  <div class="chart-card">
    <div class="chart-head">
      <span class="chart-title">本命盘排盘</span>
      <span class="chart-meta mono">
        回归黄道{{ chart.meta.houseSystem === 'whole_sign' ? ' · 整宫制' : ' · Placidus' }}
        · {{ chart.meta.timezone }}
        <span v-if="chart.meta.houseSystemFallback" class="chart-fallback" title="高纬度 Placidus 计算失败，已自动降级整宫制">降级</span>
      </span>
    </div>

    <!-- 四轴 -->
    <div class="chart-angles">
      <span v-for="(p, label) in { ASC: chart.ascendant, MC: chart.midheaven, DES: chart.descendant, IC: chart.imum_coeli }" :key="label" class="angle-chip">
        <span class="angle-label mono">{{ label }}</span>
        <span>{{ p.sign }} {{ formatDegree(p.degree) }}°</span>
      </span>
    </div>

    <!-- 行星表 -->
    <table class="chart-table">
      <thead>
        <tr><th>行星</th><th>星座</th><th>度数</th><th>宫位</th><th class="col-retro">逆行</th></tr>
      </thead>
      <tbody>
        <tr v-for="key in PLANET_ORDER" :key="key">
          <td class="cell-name">{{ planetName(key) }}</td>
          <td>{{ chart.planets[key]?.sign }}</td>
          <td class="mono">{{ formatDegree(chart.planets[key]?.degree ?? 0) }}°</td>
          <td class="mono">{{ chart.planets[key]?.house }}</td>
          <td class="cell-retro mono">{{ chart.planets[key]?.retrograde ? '℞' : '—' }}</td>
        </tr>
      </tbody>
    </table>

    <!-- 相位 -->
    <div v-if="chart.aspects.length" class="chart-section">
      <div class="chart-section-title">相位（{{ chart.aspects.length }}）</div>
      <div class="aspect-list">
        <span v-for="(a, i) in chart.aspects" :key="i" class="aspect-chip">
          <span class="mono">{{ planetName(a.p1) }}</span>
          <span class="aspect-mark mono">{{ ASPECT_SHORT[a.typeEn] ?? a.type }}</span>
          <span class="mono">{{ planetName(a.p2) }}</span>
          <span class="aspect-orb mono">{{ a.orb }}°</span>
        </span>
      </div>
    </div>

    <!-- 格局 -->
    <div v-if="chart.patterns.length" class="chart-section">
      <div class="chart-section-title">格局</div>
      <div class="pattern-list">
        <span v-for="(p, i) in chart.patterns" :key="i" class="pattern-chip">
          {{ p.type }}
          <template v-if="p.type === '星群' && p.scope === 'house'">· {{ p.house }}宫</template>
          <template v-else-if="p.type === '星群' && p.scope === 'sign'">· {{ p.sign }}</template>
          <span class="pattern-planets mono">{{ p.planets.map(planetName).join(' / ') }}</span>
        </span>
      </div>
    </div>

    <!-- 宫位 -->
    <div class="chart-section">
      <div class="chart-section-title">宫位</div>
      <div class="house-grid mono">
        <span v-for="i in 12" :key="i" class="house-cell">
          <span class="house-num">{{ i }}</span>
          <span class="house-sign">{{ chart.houses[String(i)]?.sign }}</span>
          <span class="house-planets">{{ (chart.houses[String(i)]?.planets ?? []).map(planetName).join(' ') || '—' }}</span>
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 锻造工坊：纸墨钢 + 发丝线；等宽字体是零件钢印 */
.chart-card {
  margin: 8px 0;
  padding: 12px 14px;
  border: 1px solid var(--line, #e1dacb);
  border-radius: var(--radius, 8px);
  background: var(--card, #fffdf7);
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--ink, #221d15);
}
.chart-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.chart-title {
  font-weight: 600;
  color: var(--ink-deep, #17130c);
}
.chart-meta {
  font-size: 11px;
  color: var(--steel, #6f6a5b);
}
.chart-fallback {
  color: var(--warn, #92600a);
  border: 1px solid currentColor;
  border-radius: 3px;
  padding: 0 3px;
  margin-left: 4px;
}
.mono {
  font-family: var(--font-mono, monospace);
}
.chart-angles {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.angle-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 8px;
  border: 1px solid var(--line, #e1dacb);
  border-radius: var(--radius-sm, 6px);
  background: var(--paper, #f4f0e8);
}
.angle-label {
  color: var(--steel, #6f6a5b);
  font-size: 11px;
}
.chart-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 4px;
}
.chart-table th,
.chart-table td {
  padding: 3px 6px;
  border-bottom: 1px solid var(--line, #e1dacb);
  text-align: left;
  white-space: nowrap;
}
.chart-table th {
  font-size: 11px;
  font-weight: 500;
  color: var(--steel, #6f6a5b);
}
.cell-name {
  font-weight: 500;
}
.chart-section {
  margin-top: 10px;
}
.chart-section-title {
  font-size: 11px;
  color: var(--steel, #6f6a5b);
  margin-bottom: 5px;
}
.aspect-list,
.pattern-list {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.aspect-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 7px;
  border: 1px solid var(--line, #e1dacb);
  border-radius: var(--radius-sm, 6px);
}
.aspect-mark {
  color: var(--forge, #b54300);
  font-weight: 600;
}
.aspect-orb {
  color: var(--steel, #6f6a5b);
  font-size: 11px;
}
.pattern-chip {
  padding: 2px 7px;
  border: 1px dashed var(--forge, #b54300);
  border-radius: var(--radius-sm, 6px);
  color: var(--ink-deep, #17130c);
}
.pattern-planets {
  color: var(--steel, #6f6a5b);
  font-size: 11px;
  margin-left: 2px;
}
.house-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
  gap: 4px;
}
.house-cell {
  display: flex;
  gap: 5px;
  align-items: baseline;
  padding: 2px 6px;
  border: 1px solid var(--line, #e1dacb);
  border-radius: var(--radius-sm, 6px);
  font-size: 11px;
}
.house-num {
  color: var(--steel, #6f6a5b);
}
.house-planets {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
