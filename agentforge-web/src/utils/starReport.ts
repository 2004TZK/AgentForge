/**
 * 星盘报告导出（V2）：客户端 Markdown 生成 + 打印/PDF 预览。
 * 与后端 app/services/star_report.py 渲染口径保持一致（本命/行运/推运）。
 */
import type { StarChartData } from '../types/chat'

const PLANET_ZH: Record<string, string> = {
  sun: '太阳', moon: '月亮', mercury: '水星', venus: '金星', mars: '火星',
  jupiter: '木星', saturn: '土星', uranus: '天王星', neptune: '海王星', pluto: '冥王星',
}

const ANGLE_ZH: Record<string, string> = {
  ascendant: '上升点 ASC', midheaven: '天顶 MC', descendant: '下降点 DES', imum_coeli: '天底 IC',
}

const ASPECT_ZH: Record<string, string> = {
  conjunction: '合相', opposition: '对分相', trine: '三分相', square: '四分相', sextile: '六分相',
  semi_sextile: '半六合', semi_square: '半刑', quintile: '五分相',
  sesquiquadrate: '补八分相', biquintile: '倍五分相', quincunx: '梅花相',
}

const POINT_ZH: Record<string, string> = {
  north_node: '北交点', south_node: '南交点', true_node: '真北交点', true_south_node: '真南交点',
  lilith: '莉莉丝', true_lilith: '真莉莉丝', part_of_fortune: '福点', vertex: '宿命点',
  chiron: '凯龙星', ceres: '谷神星', pallas: '智神星', juno: '婚神星', vesta: '灶神星',
}

const HOUSE_SYSTEM_ZH: Record<string, string> = {
  placidus: 'Placidus', whole_sign: '整宫制', equal: '等宫制', koch: 'Koch',
  regiomontanus: 'Regiomontanus', campanus: 'Campanus', porphyry: 'Porphyry',
  topocentric: 'Topocentric', alcabitius: 'Alcabitius', morinus: 'Morinus',
}

const PLANET_ORDER = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune', 'pluto']

function planetName(key: string): string {
  return PLANET_ZH[key] ?? key
}

function aspectName(key: string): string {
  return ASPECT_ZH[key] ?? key
}

function metaLine(chart: StarChartData): string {
  const m = chart.meta
  const zodiac = m.zodiac === 'sidereal'
    ? `恒星黄道${m.ayanamsa ? `（${m.ayanamsa}）` : ''}`
    : '回归黄道'
  const house = HOUSE_SYSTEM_ZH[m.houseSystem] ?? m.houseSystem
  const fallback = m.houseSystemFallback ? '（高纬度自动降级整宫制）' : ''
  const orb = m.orbMode === 'classical' ? ' · 古典容许度' : ''
  return `出生时间 ${m.birthDateTime ?? ''} · 时区 ${m.timezone} · ${zodiac} · ${house}${fallback}${orb}`
}

function degree(v: number): string {
  return `${v.toFixed(1)}°`
}

function tableMarkdown(header: string[], rows: string[][]): string {
  const all = [header, ...rows]
  const sep = header.map(() => '---').join(' | ')
  return all.map((r) => `| ${r.join(' | ')} |`).join('\n') + `\n| ${sep} |`
}

/** 生成 Markdown 报告（本命盘 + 可选行运/推运区块）。 */
export function chartToMarkdown(chart: StarChartData): string {
  const lines: string[] = []
  lines.push('# 星盘分析报告', '')
  lines.push(metaLine(chart), '')

  lines.push('## 四轴', '')
  lines.push(tableMarkdown(
    ['轴点', '星座', '度数'],
    (['ascendant', 'midheaven', 'descendant', 'imum_coeli'] as const).map((k) => [
      ANGLE_ZH[k], chart[k].sign, degree(chart[k].degree),
    ]),
  ), '')

  lines.push('## 行星位置', '')
  lines.push(tableMarkdown(
    ['行星', '星座', '度数', '宫位', '逆行'],
    PLANET_ORDER.map((k) => {
      const p = chart.planets[k]
      return [planetName(k), p.sign, degree(p.degree), String(p.house ?? '—'), p.retrograde ? '℞' : '—']
    }),
  ), '')

  const points = chart.points
  if (points && Object.keys(points).length) {
    lines.push('## 虚点 / 小行星', '')
    lines.push(tableMarkdown(
      ['虚点', '星座', '度数', '宫位'],
      Object.entries(points).map(([k, p]) => [
        POINT_ZH[k] ?? k, p.sign, degree(p.degree), `第${p.house ?? '?'}宫`,
      ]),
    ), '')
  }

  if (chart.aspects.length) {
    lines.push('## 相位', '')
    chart.aspects.forEach((a) => {
      lines.push(`- ${planetName(a.p1)} ${aspectName(a.typeEn)} ${planetName(a.p2)}（${a.orb}°）`)
    })
    lines.push('')
  }

  if (chart.patterns.length) {
    lines.push('## 格局', '')
    chart.patterns.forEach((p) => {
      lines.push(`- ${p.type}：${p.planets.map(planetName).join('、')}`)
    })
    lines.push('')
  }

  lines.push('## 宫位', '')
  lines.push(tableMarkdown(
    ['宫位', '星座', '宫内行星'],
    Array.from({ length: 12 }, (_, i) => {
      const h = chart.houses[String(i + 1)]
      return [String(i + 1), h.sign, (h.planets ?? []).map(planetName).join('、') || '—']
    }),
  ), '')

  const transit = (chart as StarChartData & { transit?: Record<string, unknown> }).transit
  if (transit) {
    lines.push('## 行运', '')
    lines.push(metaLine(chart), '')
    const t = transit as {
      planets?: Record<string, { sign: string; degree: number; natalHouse?: number; retrograde?: boolean }>
      aspects?: Array<{ transit: string; natal: string; type: string; orb: number }>
    }
    if (t.planets) {
      lines.push(tableMarkdown(
        ['行运行星', '星座', '度数', '落本命宫'],
        PLANET_ORDER.map((k) => {
          const p = t.planets?.[k]
          return p
            ? [planetName(k), p.sign, degree(p.degree), `第${p.natalHouse ?? '?'}宫${p.retrograde ? ' ℞' : ''}`]
            : [planetName(k), '—', '—', '—']
        }),
      ), '')
    }
    if (t.aspects?.length) {
      lines.push('### 行运对本命相位', '')
      t.aspects.forEach((a) => {
        lines.push(`- 行运${planetName(a.transit)} ${aspectName(a.type)} 本命${planetName(a.natal)}（${a.orb}°）`)
      })
      lines.push('')
    }
  }

  const progressed = (chart as StarChartData & { progressed?: Record<string, unknown> }).progressed
  if (progressed) {
    const ptype = (progressed as { progressionType?: string }).progressionType
    const typeLabel: Record<string, string> = {
      secondary: '次限（一天=一年）', tertiary: '三限（一天=一月）',
      solar_arc: '太阳弧', solar_return: '日返', lunar_return: '月返',
    }
    lines.push(`## 推运（${typeLabel[ptype ?? 'secondary'] ?? ptype ?? '次限'}）`, '')
    const p = progressed as {
      planets?: Record<string, { sign: string; degree: number; natalHouse?: number; retrograde?: boolean }>
      natalAspects?: Array<{ progressed: string; natal: string; type: string; orb: number }>
    }
    if (p.planets) {
      lines.push(tableMarkdown(
        ['推运行星', '星座', '度数', '落本命宫'],
        PLANET_ORDER.map((k) => {
          const pp = p.planets?.[k]
          return pp
            ? [planetName(k), pp.sign, degree(pp.degree), `第${pp.natalHouse ?? '?'}宫${pp.retrograde ? ' ℞' : ''}`]
            : [planetName(k), '—', '—', '—']
        }),
      ), '')
    }
    if (p.natalAspects?.length) {
      lines.push('### 推运对本命相位', '')
      p.natalAspects.forEach((a) => {
        lines.push(`- 推运${planetName(a.progressed)} ${aspectName(a.type)} 本命${planetName(a.natal)}（${a.orb}°）`)
      })
      lines.push('')
    }
  }

  lines.push('## 免责声明', '')
  lines.push('以上内容仅供娱乐与自我探索参考，不作为任何决策依据。', '')
  lines.push(`报告生成时间：${new Date().toLocaleString('zh-CN')}`, '')
  return lines.join('\n')
}

/** 简单 Markdown → HTML（仅支持本模块生成的格式：标题/表格/列表/段落）。 */
export function markdownToHtml(md: string): string {
  const esc = (s: string) =>
    s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const out: string[] = []
  let table: string[] = []
  const flushTable = () => {
    if (!table.length) return
    const rows = table.map((r) => r.split('|').map((c) => c.trim()))
    const header = rows[0]
    const body = rows.slice(2)
    out.push(
      '<table><thead><tr>' + header.map((c) => `<th>${esc(c)}</th>`).join('') + '</tr></thead>'
      + '<tbody>' + body.map((r) => `<tr>${r.map((c) => `<td>${esc(c)}</td>`).join('')}</tr>`).join('') + '</tbody></table>',
    )
    table = []
  }
  md.split('\n').forEach((raw) => {
    const line = raw.trim()
    if (line.startsWith('|')) {
      table.push(line)
      return
    }
    flushTable()
    if (line.startsWith('### ')) out.push(`<h3>${esc(line.slice(4))}</h3>`)
    else if (line.startsWith('## ')) out.push(`<h2>${esc(line.slice(3))}</h2>`)
    else if (line.startsWith('# ')) out.push(`<h1>${esc(line.slice(2))}</h1>`)
    else if (line.startsWith('- ')) out.push(`<li>${esc(line.slice(2))}</li>`)
    else if (line) out.push(`<p>${esc(line)}</p>`)
  })
  flushTable()
  return out.join('\n')
}
