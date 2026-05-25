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
  type: string;
  required: boolean;
  dict_values?: string[];
}
