/**
 * Gooey 导航截图（验证左侧导航激活药丸 + 粒子迸发）：
 * 运行：node scripts/shot-nav-gooey.mjs （依赖 playwright-core + 系统 Edge）
 * 输出：shots/nav-gooey-active.png / nav-gooey-burst.png / nav-gooey-chat.png
 */
import { chromium } from 'playwright-core'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const BASE = 'http://localhost'
const SHOTS = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'shots')

const browser = await chromium.launch({ executablePath: EDGE, headless: true })
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })

await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' })
await page.fill('input[placeholder="请输入用户名"]', 'admin')
await page.fill('input[placeholder="请输入密码"]', 'admin123')
await page.click('button[type="submit"]')
await page.waitForURL('**/agents', { timeout: 15000 })
await page.waitForTimeout(1200)
console.log('[登录] ok')

// 1) 静态：智能体激活（白色药丸 + 反色文字）
await page.locator('.sidebar').screenshot({ path: path.join(SHOTS, 'nav-gooey-active.png') })
console.log('[截图] 激活态 nav-gooey-active.png')

// 2) 点击「对话」：等待新布局挂载且粒子出现后，捕获迸发瞬间
await page.locator('.nav-list li a').nth(1).click()
await page.waitForURL('**/chat', { timeout: 10000 })
await page.waitForFunction(() => document.querySelectorAll('.effect.stars .particle').length > 0, null, { timeout: 10000 })
// 粒子点有 opacity 延迟动画，等待至少一个点可见后立即截图
await page.waitForFunction(() => {
  const pts = document.querySelectorAll('.effect.stars .point')
  for (const pt of pts) {
    if (parseFloat(getComputedStyle(pt).opacity) > 0.5) return true
  }
  return false
}, null, { timeout: 10000 })
await page.waitForTimeout(500) // 飞行中段：点已放大、opacity=1
await page.locator('.sidebar').screenshot({ path: path.join(SHOTS, 'nav-gooey-burst.png') })
await page.screenshot({ path: path.join(SHOTS, 'nav-gooey-burst-full.png') })
console.log('[截图] 粒子迸发 nav-gooey-burst.png')

// 3) 粒子消散后：对话激活态（稳定）
await page.waitForFunction(() => document.querySelectorAll('.effect.stars .particle').length === 0, null, { timeout: 10000 })
await page.waitForTimeout(150)
await page.locator('.sidebar').screenshot({ path: path.join(SHOTS, 'nav-gooey-chat.png') })
console.log('[截图] 切换后 nav-gooey-chat.png')

await browser.close()
