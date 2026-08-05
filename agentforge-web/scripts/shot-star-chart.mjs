/**
 * 星盘排盘卡片截图（M3.3 验证）：登录 → /chat/4 星盘分析师 → 发送基准输入
 * → 等待黄道圈 svg 出现 → 截图（全卡片 + 整页）。
 * 运行：node scripts/shot-star-chart.mjs （依赖 playwright-core + 系统 Edge）
 * 输出：shots/star-chart-wheel.png（卡片）、shots/star-chart-chat-wheel.png（聊天页）
 */
import { chromium } from 'playwright-core'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const BASE = 'http://localhost'
const SHOTS = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'shots')
const MAIN_INPUT = '1994-05-20 14:30 北京'

const browser = await chromium.launch({ executablePath: EDGE, headless: true })
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })

// 1) 登录 admin
await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' })
await page.fill('input[placeholder="请输入用户名"]', 'admin')
await page.fill('input[placeholder="请输入密码"]', 'admin123')
await page.click('button[type="submit"]')
await page.waitForURL('**/agents', { timeout: 15000 })
console.log('[登录] ok')

// 2) 进入星盘分析师聊天，新建会话（避免历史记忆导致不再排盘）
await page.goto(`${BASE}/chat/4`, { waitUntil: 'domcontentloaded' })
await page.waitForSelector('textarea.input-box', { timeout: 15000 })
await page.click('text=＋新建')
await page.waitForTimeout(800)
console.log('[聊天页] ok（已新建会话）')

// 3) 发送基准输入，等待黄道圈卡片
await page.fill('textarea.input-box', MAIN_INPUT)
await page.keyboard.press('Enter')
console.log('[发送]', MAIN_INPUT, '等待排盘…')
await page.waitForSelector('svg.zodiac-wheel', { timeout: 240000 })
await page.waitForTimeout(1200) // 等卡片渲染稳定
console.log('[排盘] 黄道圈已出现')

// 4) 截图
await page.locator('.chart-card').screenshot({ path: path.join(SHOTS, 'star-chart-wheel.png') })
await page.screenshot({ path: path.join(SHOTS, 'star-chart-chat-wheel.png') })
console.log('[截图] shots/star-chart-wheel.png + star-chart-chat-wheel.png')

await browser.close()
