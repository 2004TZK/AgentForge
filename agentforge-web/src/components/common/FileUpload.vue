<script setup lang="ts">
/**
 * 文件上传组件：选择文件 → 自动/手动切片 → 上传入库。
 * - 自动切片（默认）：选文件立即上传，系统默认策略切片
 * - 手动切片：选文件先快速解析预览（不入库）→ 自定义参数 → 预览切片 → 确认入库
 */
import { computed, ref } from 'vue'
import { apiPreviewFile, apiUploadFile } from '../../api/file'
import { notifyError } from '../../utils/notify'
import type { DocumentItem, SlicePreview } from '../../types/chat'

const ACCEPT = '.pdf,.docx,.txt,.md,.db,.sqlite,.sqlite3,.csv'

const props = defineProps<{ agentId: number }>()
const emit = defineEmits<{ uploaded: [doc: DocumentItem] }>()

const fileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const progress = ref(0)
const slicingMode = ref<'auto' | 'manual'>('auto')
const selectedFile = ref<File | null>(null)
const previewing = ref(false)
const preview = ref<SlicePreview | null>(null)
const previewError = ref('')

// ---- 手动切片参数（设计 v0.2 §5.4） ----
const chunkRows = ref(50)
const byTable = ref(true)
const keepHeader = ref(true)
const excludeTables = ref('')
const excludeColumns = ref('')

const manualConfig = computed(() =>
  JSON.stringify({
    chunkRows: Math.max(1, Number(chunkRows.value) || 50),
    byTable: byTable.value,
    keepHeader: keepHeader.value,
    excludeTables: excludeTables.value.split(',').map((s) => s.trim()).filter(Boolean),
    excludeColumns: excludeColumns.value.split(',').map((s) => s.trim()).filter(Boolean),
  }),
)

const isDatabaseFile = computed(() => {
  const ext = selectedFile.value?.name.toLowerCase().split('.').pop()
  return ext === 'db' || ext === 'sqlite' || ext === 'sqlite3' || ext === 'csv'
})

/** CSV 无表名概念，排除表参数不适用 */
const isCsvFile = computed(() => selectedFile.value?.name.toLowerCase().endsWith('.csv'))

/** 手动模式：快速解析结构（读取表名/列/行数，不入库） */
async function doPreview(): Promise<void> {
  const file = selectedFile.value
  if (!file || !isDatabaseFile.value) {
    notifyError('手动切片仅支持数据库/表格类文件（db/sqlite/sqlite3/csv）')
    return
  }
  previewing.value = true
  previewError.value = ''
  try {
    preview.value = await apiPreviewFile(file, {
      slicingMode: 'manual',
      slicingConfig: manualConfig.value,
    })
  } catch (e) {
    previewError.value = (e as Error).message
    preview.value = null
  } finally {
    previewing.value = false
  }
}

/** 手动模式：确认入库（携带切片参数） */
async function uploadManual(): Promise<void> {
  const file = selectedFile.value
  if (!file) return
  uploading.value = true
  progress.value = 0
  try {
    const doc = await apiUploadFile(props.agentId, file,
      { slicingMode: 'manual', slicingConfig: manualConfig.value },
      (percent) => { progress.value = percent })
    emit('uploaded', doc)
    reset()
  } catch {
    // 错误提示已由拦截器处理
  } finally {
    uploading.value = false
  }
}

/** 自动模式：选择文件立即上传 */
async function uploadAuto(): Promise<void> {
  const file = selectedFile.value
  if (!file || !props.agentId) {
    notifyError('请先选择智能体')
    return
  }
  uploading.value = true
  progress.value = 0
  try {
    const doc = await apiUploadFile(props.agentId, file, { slicingMode: 'auto' },
      (percent) => { progress.value = percent })
    emit('uploaded', doc)
    reset()
  } catch {
    // 错误提示已由拦截器处理
  } finally {
    uploading.value = false
  }
}

function onFileChange(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  selectedFile.value = file
  preview.value = null
  previewError.value = ''
  if (!props.agentId) {
    notifyError('请先选择智能体')
    return
  }
  if (slicingMode.value === 'auto') {
    void uploadAuto()
  } else {
    // 手动模式：先做快速结构预览（不入库），等待用户确认参数后入库
    void doPreview()
  }
}

function onModeChange(mode: 'auto' | 'manual'): void {
  slicingMode.value = mode
  if (mode === 'manual' && selectedFile.value && !preview.value) {
    void doPreview()
  }
}

function trigger(): void {
  fileInput.value?.click()
}

function reset(): void {
  selectedFile.value = null
  preview.value = null
  previewError.value = ''
  if (fileInput.value) fileInput.value.value = ''
}
</script>

<template>
  <div class="upload">
    <input ref="fileInput" type="file" :accept="ACCEPT" hidden @change="onFileChange" />
    <button class="btn" :disabled="uploading || !agentId" @click="trigger">
      {{ uploading ? `上传中 ${progress}%…` : (selectedFile ? '重新选择文件' : '选择文件') }}
    </button>
    <span v-if="selectedFile" class="file-name mono">{{ selectedFile.name }}</span>
    <span v-else class="muted upload-tip">支持 pdf / docx / txt / md / db / sqlite / sqlite3 / csv，≤ 50MB</span>

    <!-- 切片方式选择（设计 v0.2 §5.4） -->
    <div class="mode-row">
      <label class="mode-option">
        <input type="radio" :checked="slicingMode === 'auto'" @change="onModeChange('auto')" />
        自动切片
      </label>
      <label class="mode-option">
        <input type="radio" :checked="slicingMode === 'manual'" @change="onModeChange('manual')" />
        手动切片
      </label>
    </div>

    <!-- 手动切片参数区 + 预览 -->
    <div v-if="slicingMode === 'manual' && selectedFile" class="manual-panel">
      <div class="params">
        <label class="param">
          每 chunk 行数
          <input v-model.number="chunkRows" type="number" min="1" max="500" class="input input-sm" />
        </label>
        <label class="param">
          按表切分
          <input v-model="byTable" type="checkbox" />
        </label>
        <label class="param">
          保留表头
          <input v-model="keepHeader" type="checkbox" />
        </label>
        <label v-if="!isCsvFile" class="param">
          排除表（逗号分隔）
          <input v-model="excludeTables" type="text" class="input input-sm" placeholder="users,logs" />
        </label>
        <label class="param">
          排除列（逗号分隔）
          <input v-model="excludeColumns" type="text" class="input input-sm" placeholder="password,secret" />
        </label>
      </div>

      <div class="preview-actions">
        <button class="btn btn-secondary btn-sm" :disabled="previewing" @click="doPreview">
          {{ previewing ? '预览中…' : '预览切片' }}
        </button>
        <button class="btn btn-primary btn-sm" :disabled="uploading" @click="uploadManual">
          {{ uploading ? `入库中 ${progress}%…` : '确认入库' }}
        </button>
      </div>

      <div v-if="previewError" class="preview-error">{{ previewError }}</div>

      <div v-if="preview" class="preview-result">
        <div class="muted preview-summary">
          {{ preview.sourceType.toUpperCase() }} · {{ preview.tableCount }} 张表 ·
          共 {{ preview.totalRows }} 行
        </div>
        <table v-if="preview.tables.length" class="table preview-table">
          <thead>
            <tr>
              <th>表名</th>
              <th>列</th>
              <th>行数</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in preview.tables" :key="t.name">
              <td class="mono">{{ t.name }}</td>
              <td class="muted">{{ t.columns.join(', ') }}</td>
              <td>{{ t.rowCount }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="preview.sampleChunks.length" class="sample-chunks">
          <div class="muted label">切片样例（前 {{ preview.sampleChunks.length }} 个）：</div>
          <div v-for="(c, i) in preview.sampleChunks" :key="i" class="sample-chunk">
            <div class="muted mono chunk-meta">
              {{ c.table || '(csv)' }} · 第 {{ c.rowStart }}–{{ c.rowEnd }} 行
            </div>
            <pre class="chunk-content">{{ c.content }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.upload {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.upload-tip {
  font-size: 12px;
}

.file-name {
  font-size: 13px;
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mode-row {
  display: flex;
  gap: 14px;
  align-items: center;
  font-size: 13px;
}

.mode-option {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}

.manual-panel {
  width: 100%;
  border: 1px solid var(--border, #ddd);
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.params {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: flex-end;
}

.param {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
}

.input-sm {
  width: 120px;
}

.preview-actions {
  display: flex;
  gap: 8px;
}

.preview-error {
  color: #e5484d;
  font-size: 12px;
}

.preview-result {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.preview-summary {
  font-size: 12px;
}

.preview-table {
  max-width: 100%;
}

.sample-chunks {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.label {
  font-size: 12px;
}

.sample-chunk {
  border-left: 3px solid var(--accent, #ff6a3d);
  padding: 4px 8px;
  background: var(--surface-2, rgba(0, 0, 0, 0.04));
  border-radius: 4px;
}

.chunk-meta {
  font-size: 11px;
}

.chunk-content {
  margin: 4px 0 0;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 160px;
  overflow-y: auto;
}
</style>
