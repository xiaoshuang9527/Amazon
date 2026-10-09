/** 与后端 schema 对齐的前端类型定义。 */

export interface UserRead {
  id: number
  email: string
  is_active: boolean
  is_admin: boolean
  created_at?: string
}

export interface AdminUserRow {
  id: number
  email: string
  is_active: boolean
  is_admin: boolean
  created_at?: string
}

export interface AdminUserPage {
  total: number
  limit: number
  offset: number
  items: AdminUserRow[]
}

export interface AdminStats {
  users: number
  admins: number
  listings: number
  generations: number
}

export interface TokenRead {
  access_token: string
  token_type: string
}

export interface UsageRead {
  plan: string
  status: string
  quota_total: number
  quota_used: number
  quota_remaining: number
  current_period_start?: string | null
  current_period_end?: string | null
}

export interface ShopRead {
  id: number
  seller_id: string
  marketplace_ids: string[]
  status: string
  created_at?: string
}

export interface AuthUser extends UserRead {
  nickname: string
  plan: string
  quotaRemaining: number
  quotaTotal: number
}

export interface Violation {
  type: string
  word?: string
  field?: string
  position?: number
  message?: string
  suggestion?: string
}

export interface ComplianceReport {
  passed: boolean
  violations: Violation[]
}

export interface GeneratedListing {
  target_marketplace: string
  target_language: string
  title: string
  bullets: string[]
  description: string
  search_terms: string
  suggested_keywords: string[]
  compliance_report: ComplianceReport
  model_used?: string
}

/** 结果视图：在生成结果上补一个 marketplace 别名，便于前端表格/标签使用。 */
export interface GeneratedResultView extends GeneratedListing {
  marketplace: string
}

export interface TaskStatus {
  task_id: string
  status: string
  listing_id: number | null
  results: GeneratedListing[]
  created_at?: string | null
  errors: string[]
}

export interface GenerationRow {
  id: number
  task_id: string
  listing_id: number | null
  target_marketplace: string
  target_language: string
  model_used: string
  result: Record<string, any>
  status: string
  created_at: string
}

export interface SourceContentPayload {
  title: string
  bullets: string[]
  description: string
  keywords: string[]
  attributes?: Record<string, any>
}

export interface ListingRow {
  id: number
  shop_id: number | null
  asin: string | null
  sku: string | null
  marketplace_id: string | null
  source_language: string
  source_content: Record<string, any>
  created_at: string
  updated_at: string
}

export type BackfillField = 'title' | 'bullets' | 'description' | 'search_terms'

export interface DiffField {
  field: BackfillField
  label: string
  current: any
  proposed: any
  changed: boolean
  editable: boolean
}

export interface ListingDiff {
  listing_id: number
  marketplace_id: string
  task_id: string
  current_source: 'listing_copy' | 'source_content' | string
  current_updated_at: string | null
  model_used: string
  target_language: string
  generated_compliance_report: ComplianceReport
  fields: DiffField[]
}

export interface FieldSelection {
  field: BackfillField
  selected: boolean
  value?: any
}

export interface ApplyRequest {
  task_id: string
  marketplace_id: string
  selections: FieldSelection[]
  force?: boolean
}

export interface ApplyResponse {
  listing_id: number
  marketplace_id: string
  task_id: string
  applied_fields: string[]
  skipped_fields: string[]
  compliance_report: ComplianceReport
  forced: boolean
  spapi_synced: boolean
  message: string
  applied_at: string | null
  content: Record<string, any>
}

export type ExportFormat = 'xlsx' | 'json' | 'csv'
