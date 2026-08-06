<script setup lang="ts">
/**
 * Markdown 渲染：先 HTML 转义再应用语法规则，杜绝 XSS。
 * 支持：标题 / 加粗 / 斜体 / 行内代码 / 代码块 / 无序列表 / 有序列表 /
 *       分隔线（---）/ 引用（>）/ 表格（| ... |）/ 链接。
 * 仅做排版层重排：文本内容原样呈现，不改动智能体回答。
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
  let i = 0
  let inCodeBlock = false
  let codeLines: string[] = []

  const flushCode = (): void => {
    if (codeLines.length) {
      rendered.push(`<pre class="md-code"><code>${codeLines.join('\n')}</code></pre>`)
      codeLines = []
    }
  }

  /** 行内样式：行内代码 / 加粗 / 斜体 / 链接（内容已转义，仅包装标签） */
  const inline = (text: string): string => {
    let c = text
    c = c.replace(/`([^`]+)`/g, '<code>$1</code>')
    c = c.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    c = c.replace(/\*([^*]+)\*/g, '<em>$1</em>')
    c = c.replace(
      /\[([^\]]+)\]\((https?:\/\/[^)\s]+|mailto:[^)\s]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
    )
    return c
  }

  /** 分隔线：--- / *** / ___ */
  const isHr = (t: string): boolean => /^([-*_])\s*\1\s*\1(?:\s*\1)*\s*$/.test(t)

  /** 表格分隔行：| --- | :---: | ---: | 等 */
  const isTableSep = (t: string): boolean =>
    /^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/.test(t)

  const tableCells = (row: string): string[] =>
    row.replace(/^\||\|$/g, '').split('|').map((c) => c.trim())

  while (i < lines.length) {
    const line = lines[i]
    const trimmed = line.trim()

    // 代码块
    if (line.trimStart().startsWith('```')) {
      if (inCodeBlock) {
        flushCode()
        inCodeBlock = false
      } else {
        flushCode()
        inCodeBlock = true
      }
      i++
      continue
    }
    if (inCodeBlock) {
      codeLines.push(line)
      i++
      continue
    }
    if (!trimmed) {
      i++
      continue
    }

    // 分隔线
    if (isHr(trimmed)) {
      rendered.push('<hr class="md-hr" />')
      i++
      continue
    }

    // 标题
    const heading = /^(#{1,6})\s+(.*)$/.exec(trimmed)
    if (heading) {
      const level = heading[1].length
      rendered.push(`<h${level} class="md-h${level}">${inline(heading[2])}</h${level}>`)
      i++
      continue
    }

    // 引用：连续 > 行合并为一个引用块
    if (/^>\s?/.test(trimmed)) {
      const quoteLines: string[] = []
      while (i < lines.length && /^>\s?/.test(lines[i].trim())) {
        quoteLines.push(lines[i].trim().replace(/^>\s?/, ''))
        i++
      }
      rendered.push(
        '<blockquote>' +
          quoteLines.map((q) => `<p>${inline(q) || '&nbsp;'}</p>`).join('') +
          '</blockquote>',
      )
      continue
    }

    // 表格：连续 | 行，且第二行为分隔行
    if (trimmed.startsWith('|')) {
      const rows: string[] = []
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        rows.push(lines[i].trim())
        i++
      }
      if (rows.length >= 2 && isTableSep(rows[1])) {
        const head = tableCells(rows[0]).map((c) => `<th>${inline(c)}</th>`).join('')
        const body = rows
          .slice(2)
          .map(
            (r) =>
              `<tr>${tableCells(r).map((c) => `<td>${inline(c)}</td>`).join('')}</tr>`,
          )
          .join('')
        rendered.push(
          `<div class="md-table-wrap"><table class="md-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`,
        )
        continue
      }
      // 无分隔行的管道文本 → 按普通段落输出
      for (const r of rows) rendered.push(`<p>${inline(r)}</p>`)
      continue
    }

    // 无序列表：连续 - / * 行合并为一个 ul
    const ulMatch = /^[-*]\s+(.*)$/.exec(trimmed)
    if (ulMatch) {
      const items: string[] = []
      while (i < lines.length) {
        const m = /^[-*]\s+(.*)$/.exec(lines[i].trim())
        if (!m) break
        items.push(m[1])
        i++
      }
      rendered.push(`<ul>${items.map((it) => `<li>${inline(it)}</li>`).join('')}</ul>`)
      continue
    }

    // 有序列表：连续数字行合并为一个 ol
    const olMatch = /^\d+\.\s+(.*)$/.exec(trimmed)
    if (olMatch) {
      const items: string[] = []
      while (i < lines.length) {
        const m = /^\d+\.\s+(.*)$/.exec(lines[i].trim())
        if (!m) break
        items.push(m[1])
        i++
      }
      rendered.push(`<ol>${items.map((it) => `<li>${inline(it)}</li>`).join('')}</ol>`)
      continue
    }

    // 普通段落
    rendered.push(`<p>${inline(trimmed)}</p>`)
    i++
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
  line-height: 1.75;
  word-break: break-word;
  /* 覆盖气泡的 pre-wrap：HTML 已带结构，避免标签间换行变成多余空行 */
  white-space: normal;
}

/* ---- 段落与间距 ---- */
.markdown :deep(p) {
  margin: 6px 0;
}

/* ---- 标题：星空层级，星辉金 + 星号点缀 ---- */
.markdown :deep(h1),
.markdown :deep(h2),
.markdown :deep(h3),
.markdown :deep(h4),
.markdown :deep(h5),
.markdown :deep(h6) {
  margin: 18px 0 8px;
  line-height: 1.4;
  font-weight: 700;
  letter-spacing: 0.01em;
}

.markdown :deep(h1) {
  font-size: 20px;
  color: var(--forge-glow);
  padding-bottom: 6px;
  border-bottom: 1px solid var(--line);
}

.markdown :deep(h2) {
  font-size: 17px;
  color: var(--forge-glow);
}

.markdown :deep(h2)::before {
  content: '✦ ';
  color: var(--forge);
}

.markdown :deep(h3) {
  font-size: 15px;
  color: var(--forge);
}

.markdown :deep(h4) {
  font-size: 14px;
  color: var(--ink);
}

/* ---- 列表：正确分组，星辉金标记 ---- */
.markdown :deep(ul) {
  margin: 6px 0;
  padding-left: 22px;
  list-style: disc;
}

.markdown :deep(ol) {
  margin: 6px 0;
  padding-left: 24px;
  list-style: decimal;
}

.markdown :deep(li) {
  margin: 3px 0;
}

.markdown :deep(li::marker) {
  color: var(--forge);
}

/* ---- 强调 ---- */
.markdown :deep(strong) {
  font-weight: 700;
  color: var(--forge-glow);
}

.markdown :deep(em) {
  font-style: italic;
  color: var(--steel);
}

/* ---- 行内代码 / 代码块 ---- */
.markdown :deep(code) {
  background: var(--forge-tint);
  color: var(--forge);
  padding: 1px 5px;
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 12.5px;
}

.markdown :deep(.md-code) {
  background: #0a0f24;
  color: #e8eaf4;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 12.5px;
  font-family: var(--font-mono);
  line-height: 1.6;
  border: 1px solid #2b3765;
}

.markdown :deep(.md-code code) {
  background: transparent;
  color: inherit;
  padding: 0;
}

/* ---- 分隔线：星轨 ---- */
.markdown :deep(.md-hr) {
  border: none;
  height: 1px;
  margin: 16px 0;
  background: linear-gradient(90deg, transparent, var(--forge) 50%, transparent);
  opacity: 0.45;
}

/* ---- 引用：星辉左缘 ---- */
.markdown :deep(blockquote) {
  margin: 10px 0;
  padding: 8px 14px;
  border-left: 3px solid var(--forge);
  background: var(--forge-tint);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.markdown :deep(blockquote p) {
  margin: 4px 0;
}

/* ---- 表格：星图坐标 ---- */
.markdown :deep(.md-table) {
  width: 100%;
  margin: 0;
  border-collapse: collapse;
  font-size: 13px;
}

.markdown :deep(.md-table-wrap) {
  margin: 10px 0;
  overflow-x: auto;
  border-radius: var(--radius-sm);
  border: 1px solid var(--line);
}

.markdown :deep(.md-table th),
.markdown :deep(.md-table td) {
  padding: 8px 10px;
  border: 1px solid var(--line);
  text-align: left;
  vertical-align: top;
}

.markdown :deep(.md-table th) {
  background: var(--forge-tint);
  color: var(--forge-glow);
  font-weight: 700;
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.04em;
}

.markdown :deep(.md-table tbody tr:nth-child(even)) {
  background: rgba(20, 28, 63, 0.45);
}

/* ---- 链接 ---- */
.markdown :deep(a) {
  color: var(--forge);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.markdown :deep(a:hover) {
  color: var(--forge-glow);
}
</style>
