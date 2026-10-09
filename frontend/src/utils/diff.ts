/**
 * 轻量文本 diff 工具：用于回填视图的左右对比高亮。
 *
 * - 词级 LCS 差异（中文按字、英文按词）；
 * - 文本过长时退化为整体标注，避免 DP 表过大卡顿；
 * - 输出已做 HTML 转义，可直接 v-html 渲染。
 */

export interface DiffToken {
  text: string
  changed: boolean
}

interface DiffResult {
  left: DiffToken[]
  right: DiffToken[]
}

const TOKEN_PATTERN = /[\u4e00-\u9fff\u3040-\u30ff]|[A-Za-z0-9_'’.-]+|\s+|[\s\S]/g
const MAX_CELLS = 400000

export function tokenize(text: string): string[] {
  return text.match(TOKEN_PATTERN) || []
}

function pushToken(list: DiffToken[], text: string, changed: boolean): void {
  if (!text) return
  const last = list[list.length - 1]
  if (last && last.changed === changed) {
    last.text += text
  } else {
    list.push({ text, changed })
  }
}

export function diffTokens(a: string, b: string): DiffResult {
  if (a === b) {
    return { left: [{ text: a, changed: false }], right: [{ text: b, changed: false }] }
  }

  const A = tokenize(a)
  const B = tokenize(b)
  if (A.length === 0 || B.length === 0 || A.length * B.length > MAX_CELLS) {
    return { left: [{ text: a, changed: true }], right: [{ text: b, changed: true }] }
  }

  const cols = B.length + 1
  const dp = new Uint32Array((A.length + 1) * cols)
  for (let i = A.length - 1; i >= 0; i -= 1) {
    for (let j = B.length - 1; j >= 0; j -= 1) {
      dp[i * cols + j] =
        A[i] === B[j]
          ? dp[(i + 1) * cols + (j + 1)] + 1
          : Math.max(dp[(i + 1) * cols + j], dp[i * cols + (j + 1)])
    }
  }

  const left: DiffToken[] = []
  const right: DiffToken[] = []
  let i = 0
  let j = 0
  while (i < A.length && j < B.length) {
    if (A[i] === B[j]) {
      pushToken(left, A[i], false)
      pushToken(right, B[j], false)
      i += 1
      j += 1
    } else if (dp[(i + 1) * cols + j] >= dp[i * cols + (j + 1)]) {
      pushToken(left, A[i], true)
      i += 1
    } else {
      pushToken(right, B[j], true)
      j += 1
    }
  }
  while (i < A.length) {
    pushToken(left, A[i], true)
    i += 1
  }
  while (j < B.length) {
    pushToken(right, B[j], true)
    j += 1
  }

  return { left, right }
}

export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function render(tokens: DiffToken[], className: string): string {
  return tokens
    .map((token) =>
      token.changed
        ? `<span class="${className}">${escapeHtml(token.text)}</span>`
        : escapeHtml(token.text)
    )
    .join('')
}

/** 把任意字段值（字符串 / 字符串数组）标准化为可对比的文本。 */
export function fieldToText(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map((item) => String(item)).join('\n')
  }
  if (value === null || value === undefined) return ''
  return String(value)
}

/** 文本 → 字段值（bullets 还原为数组）。 */
export function textToFieldValue(field: string, text: string): string | string[] {
  if (field === 'bullets') {
    return text
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
  }
  return text.trim()
}

/**
 * 生成左右两侧的高亮 HTML。
 * left 高亮"将被替换/删除"的内容，right 高亮"新增/变更"的内容。
 */
export function diffHtml(
  current: unknown,
  proposed: unknown
): { left: string; right: string; changed: boolean } {
  const a = fieldToText(current)
  const b = fieldToText(proposed)
  const { left, right } = diffTokens(a, b)
  return {
    left: render(left, 'diff-del'),
    right: render(right, 'diff-ins'),
    changed: a !== b
  }
}
