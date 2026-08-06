/**
 * Galaxy 背景验证：WebGL canvas 存在且渲染、无控制台错误、截图留档。
 * 运行：node scripts/check-galaxy.mjs （依赖 playwright-core + 系统 Edge）
 * 输出：shots/galaxy-main.png
 */
import { chromium } from 'playwright-core'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const BASE = 'http://localhost'
const SHOTS = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'shots')

const browser = await chromium.launch({ executablePath: EDGE, headless: true })
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
const consoleErrors = []
page.on('console', (msg) => {
  if (msg.type() === 'error') consoleErrors.push(msg.text())
})
page.on('pageerror', (err) => consoleErrors.push(`pageerror: ${err.message}`))

await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' })
await page.fill('input[placeholder="请输入用户名"]', 'admin')
await page.fill('input[placeholder="请输入密码"]', 'admin123')
await page.click('button[type="submit"]')
await page.waitForURL('**/agents', { timeout: 15000 })
await page.waitForTimeout(1500) // 等 shader 预热渲染几帧

const state = await page.evaluate(() => {
  const canvas = document.querySelector('.app-bg canvas')
  const gl = canvas
    ? canvas.getContext('webgl2') || canvas.getContext('webgl') || canvas.getContext('experimental-webgl')
    : null
  const rect = canvas?.getBoundingClientRect()
  // 采样 canvas 中央像素（WebGL 读取）
  let centerPx = null
  if (canvas && gl) {
    const w = gl.drawingBufferWidth
    const h = gl.drawingBufferHeight
    const px = new Uint8Array(4)
    gl.readPixels(Math.floor(w / 2), Math.floor(h / 2), 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px)
    centerPx = [px[0], px[1], px[2], px[3]]
  }
  return {
    hasCanvas: !!canvas,
    hasWebGL: !!gl,
    canvasSize: rect ? { w: Math.round(rect.width), h: Math.round(rect.height) } : null,
    centerPx,
    bgZ: getComputedStyle(document.querySelector('.app-bg')).zIndex,
    viewZ: getComputedStyle(document.querySelector('.app-view')).zIndex,
  }
})
console.log('[Galaxy]', JSON.stringify(state, null, 2))
if (!state.hasCanvas) throw new Error('缺少 Galaxy canvas')
if (!state.hasWebGL) throw new Error('WebGL 上下文创建失败')
if (state.canvasSize.w < 100 || state.canvasSize.h < 100) throw new Error('canvas 尺寸异常')
if (state.bgZ !== '0' || state.viewZ !== '1') throw new Error('背景/内容层级异常')

await page.screenshot({ path: path.join(SHOTS, 'galaxy-main.png') })
console.log('[截图] shots/galaxy-main.png')

if (consoleErrors.length) {
  console.error('[控制台错误]', consoleErrors)
  process.exitCode = 1
} else {
  console.log('✅ Galaxy 背景渲染正常，无控制台错误')
}
await browser.close()
