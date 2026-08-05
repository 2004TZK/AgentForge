/** 轻量提示：无第三方 UI 库依赖的 Toast。 */

let container: HTMLDivElement | null = null

function getContainer(): HTMLDivElement {
  if (!container) {
    container = document.createElement('div')
    container.style.cssText =
      'position:fixed;top:16px;left:50%;transform:translateX(-50%);z-index:9999;display:flex;flex-direction:column;gap:8px;align-items:center;'
    document.body.appendChild(container)
  }
  return container
}

/** 状态色对齐锻造工坊令牌：成功=铜绿 / 失败=铁锈 / 信息=墨黑 */
const BG: Record<'success' | 'error' | 'info', string> = {
  success: '#2e7d46',
  error: '#b3261e',
  info: '#221d15',
}

export function notify(message: string, type: 'success' | 'error' | 'info' = 'info'): void {
  const el = document.createElement('div')
  const bg = BG[type]
  el.textContent = message
  el.style.cssText =
    `background:${bg};color:#fffdf7;padding:8px 16px;border-radius:6px;font-size:14px;` +
    'box-shadow:0 2px 10px rgba(23,19,12,.28);animation:fadeIn .2s ease;'
  getContainer().appendChild(el)
  setTimeout(() => {
    el.style.transition = 'opacity .3s'
    el.style.opacity = '0'
    setTimeout(() => el.remove(), 300)
  }, 2500)
}

export const notifyError = (message: string): void => notify(message, 'error')
export const notifySuccess = (message: string): void => notify(message, 'success')
