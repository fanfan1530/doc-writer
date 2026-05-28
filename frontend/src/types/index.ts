/* ---------- 文书生成 ---------- */

export interface GenerationResult {
  doc_type: string;
  elements: Record<string, string>;
  suggested_laws: string[];
  case_nature: string;
  content: string;
}

export interface CaseFileSummaryResponse {
  success: boolean;
  raw_text: string;
  raw_char_count: number;
  summary: string;
  char_count: number;
  warning?: string;
}

/* ---------- 模型管理 ---------- */

export interface ModelProvider {
  id: string;
  name: string;
  provider: string;
  base_url: string;
  model_name: string;
  model_name_large?: string;
  api_type?: string;
  has_api_key: boolean;
  requires_key: boolean;
  is_active: boolean;
}

export interface ModelTestResult {
  success: boolean;
  message: string;
}

/* ---------- 字段定义 ---------- */

export interface FieldSchema {
  key: string;
  label: string;
  type: 'text' | 'textarea' | 'date' | 'datetime' | 'number' | 'id_card' | 'select' | 'dict' | 'checkbox_group' | 'composite' | 'qa_block' | 'signature_block' | 'document_number' | 'distribution' | 'table';
  required: boolean;
  dict_values?: string[];
  placeholder?: string;
}

/* ---------- 模板管理 ---------- */

export interface TemplateInfo {
  doc_type: string;
  name: string;
  description: string;
  category: string;
  subcategory?: string;
  is_official: boolean;
  version: number;
}

export interface TemplateDetail extends TemplateInfo {
  schema_fields: FieldSchema[];
  template_text: string;
  usage_guide: string;
  is_active: boolean;
}

export interface TemplateCategory {
  name: string;
  count: number;
  children?: TemplateCategory[];
}

/* ---------- 类案检索 ---------- */

export interface CaseItem {
  id: string;
  title: string;
  case_type: '刑事' | '行政' | '民事';
  key_facts: string;
  penalty_outcome: string;
  laws: string[];
  evidence_list: string[];
  procedural_notes: string;
}

export interface CaseSearchResult extends CaseItem {
  similarity_score: number;
}

export interface TimelineEvent {
  timestamp: string;
  event_type: 'arrest' | 'investigation' | 'evidence' | 'court' | 'report' | 'other';
  description: string;
  involved_parties?: string;
  location?: string;
}

/* ---------- 案件管理 (v2.1) ---------- */

export type CaseStatus = 'FILING' | 'INVESTIGATING' | 'REVIEWING' | 'APPROVED' | 'CLOSED' | 'ARCHIVED';

export interface DBCase {
  id: number;
  case_number: string;
  title: string;
  case_type: string;
  status: CaseStatus;
  status_label: string;
  officer_id: number;
  unit: string;
  description: string;
  incident_date: string;
  location: string;
  created_at: string;
  updated_at: string;
}

export interface CaseDocumentItem {
  id: number;
  document_id: number | null;
  doc_type: string;
  title: string;
  status: string;
  submitted_by: number | null;
  submitted_at: string;
  created_at: string;
}

export interface CaseEvidenceItem {
  id: number;
  name: string;
  ev_type: string;
  file_path: string;
  uploaded_by: number | null;
  uploaded_at: string;
}

export interface CaseTimelineItem {
  id: number;
  event: string;
  description: string;
  occurred_at: string;
  recorded_by: number | null;
}

export interface ReviewRecordItem {
  id: number;
  document_id: number;
  reviewer_id: number;
  action: string;
  comment: string;
  created_at: string;
}

export interface CaseDetail extends DBCase {
  documents: CaseDocumentItem[];
  evidences: CaseEvidenceItem[];
  timeline: CaseTimelineItem[];
  reviews: ReviewRecordItem[];
}

/* ---------- 通知 (v2.1) ---------- */

export interface NotificationItem {
  id: number;
  type: string;
  title: string;
  content: string;
  related_case_id: number | null;
  is_read: boolean;
  created_at: string;
}
