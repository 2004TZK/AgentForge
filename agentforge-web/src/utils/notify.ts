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

export function notify(message: string, type: 'success' | 'error' | 'info' = 'info'): void {
  const el = document.createElement('div')
  const bg = type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'
  el.textContent = message
  el.style.cssText =
    `background:${bg};color:#fff;padding:8px 16px;border-radius:8px;font-size:14px;` +
    'box-shadow:0 2px 8px rgba(0,0,0,.2);animation:fadeIn .2s ease;'
  getContainer().appendChild(el)
  setTimeout(() => {
    el.style.transition = 'opacity .3s'
    el.style.opacity = '0'
    setTimeout(() => el.remove(), 300)
  }, 2500)
}

export const notifyError = (message: string): void => notify(message, 'error')
export const notifySuccess = (message: string): void => notify(message, 'success')
