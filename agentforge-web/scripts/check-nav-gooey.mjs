/**
 * Gooey 导航 DOM/样式断言：验证激活药丸、反色文字、粒子迸发均生效。
 * 运行：node scripts/check-nav-gooey.mjs
 */
import { chromium } from 'playwright-core'

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const BASE = 'http://localhost'

const browser = await chromium.launch({ executablePath: EDGE, headless: true })
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
page.on('console', (msg) => {
  if (msg.type() === 'error') console.log('[console.error]', msg.text())
})
page.on('pageerror', (err) => console.log('[pageerror]', err.message))
const fail = (msg) => { console.error('[FAIL]', msg); process.exitCode = 1 }

await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' })
await page.fill('input[placeholder="请输入用户名"]', 'admin')
await page.fill('input[placeholder="请输入密码"]', 'admin123')
await page.click('button[type="submit"]')
await page.waitForURL('**/agents', { timeout: 15000 })
await page.waitForTimeout(1000)

const state = await page.evaluate(() => {
  const li = document.querySelectorAll('.nav-list li')
  const active = document.querySelector('.nav-list li.active')
  const filter = document.querySelector('.effect.filter')
  const text = document.querySelector('.effect.text')
  const activeRect = active?.getBoundingClientRect()
  const filterRect = filter?.getBoundingClientRect()
  const after = filter ? getComputedStyle(filter, '::after') : null
  return {
    liCount: li.length,
    activeLabel: active?.innerText ?? null,
    activeColor: active ? getComputedStyle(active).color : null,
    activeBg: active ? getComputedStyle(active, '::after').backgroundColor : null,
    filterPosition: filterRect ? { x: Math.round(filterRect.x), y: Math.round(filterRect.y), w: Math.round(filterRect.width), h: Math.round(filterRect.height) } : null,
    activePosition: activeRect ? { x: Math.round(activeRect.x), y: Math.round(activeRect.y), w: Math.round(activeRect.width), h: Math.round(activeRect.height) } : null,
    pillOpacity: after ? after.opacity : null,
    pillScale: after ? after.transform : null,
    textMatches: text?.innerText === active?.innerText,
  }
})
console.log('[状态]', JSON.stringify(state, null, 2))
if (state.liCount !== 5) fail('应渲染 5 个导航项')
if (!state.activeLabel) fail('缺少激活项')
if (state.activeColor !== 'rgb(10, 15, 36)') fail(`激活文字应为深色反色，实际 ${state.activeColor}`)
if (state.activeBg !== 'rgb(255, 207, 107)') fail(`激活药丸应为星辉金，实际 ${state.activeBg}`)
if (!state.filterPosition || state.activePosition && Math.abs(state.filterPosition.x - state.activePosition.x) > 2) {
  fail('效果层应贴合激活项位置')
}
if (!state.textMatches) fail('文字副本应与激活项一致')

// 点击「对话」→ 断言粒子出现
await page.locator('.nav-list li a').nth(1).click()
await page.waitForTimeout(120)
console.log('[URL]', page.url())
console.log('[导航类型]', await page.evaluate(() => performance.getEntriesByType('navigation')[0]?.type))
await page.waitForTimeout(250)
const burst = await page.evaluate(() => ({
  particles: document.querySelectorAll('.effect.stars .particle').length,
  activeLabel: document.querySelector('.nav-list li.active')?.innerText ?? null,
  filterActive: document.querySelector('.effect.filter')?.classList.contains('active') ?? false,
  filterPillBg: getComputedStyle(document.querySelector('.effect.filter'), '::after').backgroundColor,
  starClip: getComputedStyle(document.querySelector('.effect.stars .point')).clipPath,
  starGlow: getComputedStyle(document.querySelector('.effect.stars .point')).filter,
}))
console.log('[迸发]', JSON.stringify(burst))
if (burst.activeLabel !== '对话') fail('点击后激活项应为「对话」')
if (burst.particles < 3) fail(`粒子应生成，实际 ${burst.particles}`)
if (!burst.filterActive) fail('效果层应处于 active 状态')
if (burst.filterPillBg !== 'rgb(255, 207, 107)') fail(`药丸应为主题星辉金，实际 ${burst.filterPillBg}`)
if (!burst.starClip.includes('polygon')) fail(`粒子应为星形，实际 clip-path ${burst.starClip}`)
if (!burst.starGlow.includes('drop-shadow')) fail(`星星应有辉光，实际 filter ${burst.starGlow}`)

// 切换延迟：点击「文件」→ 新页面内容挂载耗时（路由 chunk 已由空闲预取缓存）
const t0 = Date.now()
await page.locator('.nav-list li a').nth(2).click()
await page.waitForSelector('.page-container', { timeout: 10000 })
const latency = Date.now() - t0
console.log('[切换延迟]', `${latency}ms`)
if (latency > 800) fail(`切换延迟偏高：${latency}ms（期望 < 800ms）`)

await browser.close()
console.log(process.exitCode ? '❌ 存在失败项' : '✅ Gooey 导航全部断言通过')

// ── 窄屏响应式：顶栏横排 + 药丸跟随 ──
const mobile = await chromium.launch({ executablePath: EDGE, headless: true })
const mp = await mobile.newPage({ viewport: { width: 700, height: 900 } })
await mp.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' })
await mp.fill('input[placeholder="请输入用户名"]', 'admin')
await mp.fill('input[placeholder="请输入密码"]', 'admin123')
await mp.click('button[type="submit"]')
await mp.waitForURL('**/agents', { timeout: 15000 })
await mp.waitForTimeout(800)
const mobileState = await mp.evaluate(() => {
  const ul = document.querySelector('.nav-list ul')
  const active = document.querySelector('.nav-list li.active')
  const filter = document.querySelector('.effect.filter')
  const a = active?.getBoundingClientRect()
  const f = filter?.getBoundingClientRect()
  return {
    direction: ul ? getComputedStyle(ul).flexDirection : null,
    activeLabel: active?.innerText ?? null,
    aligned: a && f ? Math.abs(a.x - f.x) < 3 && Math.abs(a.y - f.y) < 3 : false,
  }
})
console.log('[窄屏]', JSON.stringify(mobileState))
if (mobileState.direction !== 'row') { console.error('[FAIL] 窄屏导航应为横排'); process.exitCode = 1 }
if (!mobileState.aligned) { console.error('[FAIL] 窄屏药丸应贴合激活项'); process.exitCode = 1 }
await mobile.close()
console.log(process.exitCode ? '❌ 窄屏验证失败' : '✅ 窄屏验证通过')
