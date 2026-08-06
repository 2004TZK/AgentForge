import { describe, expect, it } from 'vitest'
import { chartToMarkdown, markdownToHtml } from '../starReport'
import type { StarChartData } from '../../types/chat'

function makeChart(): StarChartData {
  const point = (sign: string, degree: number) => ({ sign, signIndex: 0, degree, longitude: degree })
  const planet = (sign: string, degree: number, house: number) => ({
    sign, signIndex: 0, degree, longitude: degree, house, retrograde: false,
  })
  const houses: StarChartData['houses'] = {}
  for (let i = 1; i <= 12; i += 1) houses[String(i)] = { cusp: i * 30, sign: '白羊座', planets: [] }
  houses['1'].planets = ['sun']
  return {
    meta: {
      zodiac: 'tropical', houseSystem: 'placidus', houseSystemFallback: false,
      timezone: 'Asia/Shanghai', ephemeris: 'pyswisseph', ayanamsa: null,
      birthDateTime: '1994-05-20T14:30:00+08:00', utDateTime: '1994-05-20T06:30:00Z',
    },
    ascendant: point('天秤座', 12.5),
    midheaven: point('巨蟹座', 23.4),
    descendant: point('白羊座', 12.5),
    imum_coeli: point('摩羯座', 23.4),
    planets: {
      sun: planet('金牛座', 29.4, 9),
      moon: planet('双子座', 3.8, 10),
      mercury: planet('双子座', 15.2, 10),
      venus: planet('白羊座', 5.1, 8),
      mars: planet('白羊座', 28.3, 7),
      jupiter: planet('天蝎座', 10.5, 2),
      saturn: planet('双鱼座', 18.7, 5),
      uranus: planet('摩羯座', 22.1, 3),
      neptune: planet('摩羯座', 22.4, 3),
      pluto: planet('射手座', 27.5, 2),
    },
    houses,
    aspects: [
      { p1: 'sun', p2: 'moon', type: '三分相', typeEn: 'trine', orb: 4.4 },
      { p1: 'sun', p2: 'saturn', type: '四分相', typeEn: 'square', orb: 1.9 },
    ],
    patterns: [{ type: '星群', scope: 'house', house: 10, planets: ['moon', 'mercury'] }],
    birthText: null,
  }
}

describe('starReport', () => {
  it('生成包含核心章节的 Markdown', () => {
    const md = chartToMarkdown(makeChart())
    expect(md.startsWith('# 星盘分析报告')).toBe(true)
    for (const kw of ['四轴', '行星位置', '相位', '格局', '宫位', '免责声明']) {
      expect(md).toContain(kw)
    }
    expect(md).toContain('太阳 三分相 月亮')
  })

  it('行运区块渲染', () => {
    const chart = makeChart() as StarChartData & { transit?: unknown }
    chart.transit = {
      planets: { sun: { sign: '狮子座', degree: 13.2, natalHouse: 5, retrograde: false } },
      aspects: [{ transit: 'saturn', natal: 'sun', type: 'square', orb: 1.2 }],
    }
    const md = chartToMarkdown(chart)
    expect(md).toContain('## 行运')
    expect(md).toContain('行运土星 四分相 本命太阳')
  })

  it('markdownToHtml 转出表格与标题', () => {
    const md = chartToMarkdown(makeChart())
    const html = markdownToHtml(md)
    expect(html).toContain('<h1>')
    expect(html).toContain('<table>')
    expect(html).toContain('<th>')
  })
})
