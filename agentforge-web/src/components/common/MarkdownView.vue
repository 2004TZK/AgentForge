<script setup lang="ts">
/**
 * 轻量 Markdown 渲染：先 HTML 转义再应用语法规则，杜绝 XSS。
 * 支持：标题/加粗/斜体/行内代码/代码块/列表/链接/换行。
 */
import { computed } from 'vue'

const props = defineProps<{ content: string }>()

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

const html = computed(() => {
  const escaped = escapeHtml(props.content)
  const lines = escaped.split('\n')
  const rendered: string[] = []
  let inCodeBlock = false
  let codeLines: string[] = []

  const flushCode = () => {
    if (codeLines.length) {
      rendered.push(`<pre class="md-code"><code>${codeLines.join('\n')}</code></pre>`)
      codeLines = []
    }
  }

  for (const line of lines) {
    if (line.trimStart().startsWith('```')) {
      if (inCodeBlock) {
        flushCode()
        inCodeBlock = false
      } else {
        flushCode()
        inCodeBlock = true
      }
      continue
    }
    if (inCodeBlock) {
      codeLines.push(line)
      continue
    }
    const trimmed = line.trim()
    if (!trimmed) {
      rendered.push('')
      continue
    }
    // 标题
    const heading = /^(#{1,6})\s+(.*)$/.exec(trimmed)
    if (heading) {
      const level = heading[1].length
      rendered.push(`<h${level} class="md-h${level}">${heading[2]}</h${level}>`)
      continue
    }
    // 无序列表
    if (/^[-*]\s+/.test(trimmed)) {
      rendered.push(`<li>${trimmed.replace(/^[-*]\s+/, '')}</li>`)
      continue
    }
    // 有序列表
    if (/^\d+\.\s+/.test(trimmed)) {
      rendered.push(`<li>${trimmed.replace(/^\d+\.\s+/, '')}</li>`)
      continue
    }
    let content = trimmed
    // 行内代码
    content = content.replace(/`([^`]+)`/g, '<code>$1</code>')
    // 加粗/斜体
    content = content.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    content = content.replace(/\*([^*]+)\*/g, '<em>$1</em>')
    // 链接（href 限制为 http/https/mailto，防伪协议）
    content = content.replace(
      /\[([^\]]+)\]\((https?:\/\/[^)\s]+|mailto:[^)\s]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
    )
    rendered.push(`<p>${content}</p>`)
  }
  flushCode()
  return rendered.join('\n')
})
</script>

<template>
  <div class="markdown" v-html="html" />
</template>

<style scoped>
.markdown {
  line-height: 1.7;
  word-break: break-word;
}

.markdown :deep(p) {
  margin: 4px 0;
}

.markdown :deep(li) {
  margin: 2px 0 2px 18px;
  list-style: disc;
}

.markdown :deep(code) {
  background: rgba(0, 0, 0, 0.06);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 13px;
}

.markdown :deep(.md-code) {
  background: #0f172a;
  color: #e2e8f0;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 13px;
}

.markdown :deep(.md-code code) {
  background: transparent;
  color: inherit;
  padding: 0;
}

.markdown :deep(h1),
.markdown :deep(h2),
.markdown :deep(h3) {
  margin: 12px 0 6px;
}
</style>
