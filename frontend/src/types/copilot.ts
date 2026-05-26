/** AI Copilot 相关类型定义 */

export interface Conversation {
  id: number;
  title: string;
  doc_type: string;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'tool';
  content: string;
  tool_calls?: ToolCallRecord[];
  created_at?: string;
}

export interface ToolCallRecord {
  name: string;
  args: Record<string, unknown>;
  result?: string;
}

export interface SSEChunk {
  text: string;
}

export interface SSEThinking {
  message: string;
}

export interface SSEToolCall {
  tool: string;
  args: Record<string, unknown>;
}

export interface SSEToolResult {
  tool: string;
  result: string;
}

export interface SSEDone {
  elapsed_ms: number;
}

export interface SSEError {
  message: string;
}

/** 工具名称中文映射 */
export const TOOL_LABELS: Record<string, string> = {
  search_laws: '检索法条',
  search_procedures: '检索程序',
  generate_document: '生成文书',
  polish_document: '润色文书',
  check_deadlines: '检查期限',
  analyze_case_nature: '分析案情',
  evidence_checklist: '证据指引',
  penalty_reference: '处罚参考',
};

/** 工具图标 emoji */
export const TOOL_ICONS: Record<string, string> = {
  search_laws: '📚',
  search_procedures: '📋',
  generate_document: '📽',
  polish_document: '✏️',
  check_deadlines: '⏰',
  analyze_case_nature: '⚖️',
  evidence_checklist: '🔍',
  penalty_reference: '💰',
};
