/** AI Copilot 对话面板 —— SSE 流式对话 + 工具调用可视化 + 会话管理。 */

import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Button, Input, Select, Typography, Tag, App, Popconfirm, Empty, Spin,
} from 'antd';
import {
  SendOutlined, PlusOutlined, DeleteOutlined,
  RobotOutlined, UserOutlined, ToolOutlined,
  ThunderboltOutlined, LoadingOutlined, CheckCircleOutlined,
  BulbOutlined, SearchOutlined, FormOutlined, ClockCircleOutlined,
  SafetyOutlined, FundOutlined,
} from '@ant-design/icons';
import { getAccessToken } from '../api/client';
import type { Conversation } from '../types/copilot';
import { TOOL_LABELS, TOOL_ICONS } from '../types/copilot';

const { Text } = Typography;

// ── 工具图标映射 ──
const TOOL_ANT_ICONS: Record<string, React.ReactNode> = {
  search_laws: <SearchOutlined />,
  search_procedures: <SearchOutlined />,
  generate_document: <FormOutlined />,
  polish_document: <FormOutlined />,
  check_deadlines: <ClockCircleOutlined />,
  analyze_case_nature: <SafetyOutlined />,
  evidence_checklist: <BulbOutlined />,
  penalty_reference: <FundOutlined />,
};

// ── 消息类型 ──
interface UIMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: ToolCallState[];
}

interface ToolCallState {
  name: string;
  args: Record<string, unknown>;
  result?: string;
  status: 'pending' | 'running' | 'done';
}

// ── Props ──
interface ChatPanelProps {
  docContext?: string;
  docType?: string;
  onDocumentModified?: (content: string) => void;
}

export default function ChatPanel({ docContext = '', docType = '', onDocumentModified }: ChatPanelProps) {
  const { message: antMsg } = App.useApp();

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [convId, setConvId] = useState<number | null>(null);
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [thinkingText, setThinkingText] = useState('');
  const [activeToolCalls, setActiveToolCalls] = useState<ToolCallState[]>([]);
  const [loadingConvs, setLoadingConvs] = useState(false);

  const msgListRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // ── 加载会话列表 ──
  const loadConversations = useCallback(async () => {
    setLoadingConvs(true);
    try {
      const token = getAccessToken();
      const resp = await fetch('/api/copilot/conversations?limit=50', {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (resp.ok) {
        const data = await resp.json();
        setConversations(data.conversations || []);
      }
    } catch { /* ignore */ } finally {
      setLoadingConvs(false);
    }
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  // ── 加载会话消息 ──
  const loadMessages = useCallback(async (id: number) => {
    try {
      const token = getAccessToken();
      const resp = await fetch(`/api/copilot/conversations/${id}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (resp.ok) {
        const data = await resp.json();
        const msgs: UIMessage[] = (data.messages || []).map((m: {
          id: number; role: string; content: string; tool_calls?: Array<{
            name: string; args: Record<string, unknown>; result?: string;
          }>;
        }) => ({
          id: String(m.id),
          role: m.role === 'assistant' ? 'assistant' : 'user',
          content: m.content || '',
          toolCalls: (m.tool_calls || []).map((tc) => ({
            name: tc.name,
            args: tc.args || {},
            result: tc.result,
            status: 'done' as const,
          })),
        }));
        setMessages(msgs);
      }
    } catch { /* ignore */ }
  }, []);

  // ── 切换会话 ──
  const handleSwitchConv = useCallback((id: number) => {
    setConvId(id);
    setMessages([]);
    setActiveToolCalls([]);
    setThinkingText('');
    if (id) loadMessages(id);
  }, [loadMessages]);

  // ── 新建会话 ──
  const handleNewChat = useCallback(() => {
    setConvId(null);
    setMessages([]);
    setActiveToolCalls([]);
    setThinkingText('');
    setInputValue('');
  }, []);

  // ── 删除会话 ──
  const handleDeleteConv = useCallback(async (id: number) => {
    try {
      const token = getAccessToken();
      await fetch(`/api/copilot/conversations/${id}`, {
        method: 'DELETE',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (convId === id) handleNewChat();
      loadConversations();
    } catch { /* ignore */ }
  }, [convId, handleNewChat, loadConversations]);

  // ── 自动滚动到底部 ──
  useEffect(() => {
    if (msgListRef.current) {
      msgListRef.current.scrollTop = msgListRef.current.scrollHeight;
    }
  }, [messages, thinkingText, activeToolCalls]);

  // ── 发送消息 ──
  const handleSend = useCallback(async () => {
    const text = inputValue.trim();
    if (!text || streaming) return;

    setInputValue('');

    const userMsg: UIMessage = {
      id: `user_${Date.now()}`,
      role: 'user',
      content: text,
    };
    setMessages((prev) => [...prev, userMsg]);

    const assistantMsg: UIMessage = {
      id: `assistant_${Date.now()}`,
      role: 'assistant',
      content: '',
      toolCalls: [],
    };
    setMessages((prev) => [...prev, assistantMsg]);
    setStreaming(true);
    setThinkingText('正在分析您的问题...');
    setActiveToolCalls([]);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const token = getAccessToken();
      const resp = await fetch('/api/copilot/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          message: text,
          conversation_id: convId || undefined,
          doc_context: docContext,
          include_history: true,
        }),
        signal: controller.signal,
      });

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || `请求失败 (${resp.status})`);
      }

      // 从响应头获取 conversation_id
      const newConvId = resp.headers.get('X-Conversation-Id');
      if (newConvId && !convId) {
        const id = parseInt(newConvId, 10);
        setConvId(id);
        loadConversations();
      }

      // 读取 SSE 流
      const reader = resp.body?.getReader();
      if (!reader) throw new Error('不支持流式响应');

      const decoder = new TextDecoder();
      let buffer = '';
      let fullContent = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let eventType = '';
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            const dataStr = line.slice(6);
            try {
              const data = JSON.parse(dataStr);
              handleSSEEvent(eventType, data, assistantMsg.id, (chunk) => {
                fullContent += chunk;
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMsg.id
                      ? { ...m, content: m.content + chunk }
                      : m,
                  ),
                );
              });
            } catch { /* skip malformed JSON */ }
            eventType = '';
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return;
      const errorText = err instanceof Error ? err.message : '连接失败';
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsg.id && !m.content
            ? { ...m, content: `错误: ${errorText}` }
            : m,
        ),
      );
    } finally {
      setStreaming(false);
      setThinkingText('');
      setActiveToolCalls([]);
      abortRef.current = null;
    }
  }, [inputValue, streaming, convId, docContext, loadConversations]);

  // ── SSE 事件处理 ──
  function handleSSEEvent(
    event: string,
    data: Record<string, unknown>,
    assistantId: string,
    onChunk: (text: string) => void,
  ) {
    switch (event) {
      case 'thinking':
        setThinkingText(String(data.message || ''));
        break;
      case 'tool_call': {
        const tc: ToolCallState = {
          name: String(data.tool || ''),
          args: (data.args || {}) as Record<string, unknown>,
          status: 'running',
        };
        setActiveToolCalls((prev) => [...prev, tc]);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, toolCalls: [...(m.toolCalls || []), tc] }
              : m,
          ),
        );
        break;
      }
      case 'tool_result': {
        const toolName = String(data.tool || '');
        const result = String(data.result || '');
        setActiveToolCalls((prev) =>
          prev.map((tc) =>
            tc.name === toolName && tc.status === 'running'
              ? { ...tc, result, status: 'done' }
              : tc,
          ),
        );
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  toolCalls: (m.toolCalls || []).map((tc) =>
                    tc.name === toolName && tc.status === 'running'
                      ? { ...tc, result, status: 'done' }
                      : tc,
                  ),
                }
              : m,
          ),
        );
        break;
      }
      case 'chunk':
        onChunk(String(data.text || ''));
        setThinkingText('');
        break;
      case 'error':
        onChunk(`\n\n⚠️ ${data.message || '未知错误'}`);
        break;
      case 'doc_modified':
        if (data.content && onDocumentModified) {
          onDocumentModified(String(data.content));
        }
        break;
      case 'done':
        setThinkingText('');
        break;
    }
  }

  // ── 停止生成 ──
  const handleStop = useCallback(() => {
    abortRef.current?.abort();
    setStreaming(false);
    setThinkingText('');
  }, []);

  // ── 键盘发送 ──
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  // ── 渲染工具调用卡片 ──
  function renderToolCall(tc: ToolCallState, idx: number) {
    const label = TOOL_LABELS[tc.name] || tc.name;
    const icon = TOOL_ANT_ICONS[tc.name] || <ToolOutlined />;
    const emoji = TOOL_ICONS[tc.name] || '';

    return (
      <div
        key={`${tc.name}_${idx}`}
        className="mb-2 p-2 rounded-lg border border-blue-200 bg-blue-50/60 animate-fade-in"
      >
        <div className="flex items-center gap-2">
          <span className="text-sm">{emoji}</span>
          <span className="text-xs font-medium text-blue-700">
            {label}
          </span>
          {tc.status === 'running' && (
            <Spin indicator={<LoadingOutlined style={{ fontSize: 12 }} spin />} size="small" />
          )}
          {tc.status === 'done' && (
            <CheckCircleOutlined className="text-green-500 text-xs" />
          )}
        </div>
        {tc.result && tc.status === 'done' && (
          <div className="mt-1.5 text-xs text-slate-600 bg-white/70 rounded p-1.5 max-h-[120px] overflow-auto whitespace-pre-wrap">
            {tc.result.length > 500 ? tc.result.slice(0, 500) + '...' : tc.result}
          </div>
        )}
      </div>
    );
  }

  // ── 渲染 ──
  return (
    <div className="h-full flex flex-col min-h-0 bg-white rounded-xl shadow-sm border-0">
      {/* Header: 会话选择 */}
      <div className="flex-shrink-0 px-3 py-2.5 border-b border-slate-100 flex items-center gap-2">
        <span className="text-sm font-semibold text-slate-700 flex-shrink-0 flex items-center gap-1.5">
          <RobotOutlined className="text-police-600" />
          AI 助手
        </span>
        <Select
          size="small"
          value={convId}
          onChange={handleSwitchConv}
          placeholder={loadingConvs ? '加载中...' : '选择对话'}
          className="flex-1 min-w-0"
          showSearch
          filterOption={(input, option) =>
            (option?.label as string)?.toLowerCase().includes(input.toLowerCase())
          }
          options={conversations.map((c) => ({
            label: c.title || '新对话',
            value: c.id,
          }))}
          notFoundContent={<span className="text-xs text-slate-400">暂无对话</span>}
          dropdownRender={(menu) => (
            <div>
              {menu}
              {conversations.length > 0 && (
                <div className="border-t border-slate-100 pt-1 mt-1 px-2">
                  {conversations.slice(0, 10).map((c) => (
                    <div
                      key={c.id}
                      className="flex items-center justify-between py-1 hover:bg-slate-50 rounded px-1"
                    >
                      <span
                        className="text-xs text-slate-600 truncate flex-1 cursor-pointer"
                        onClick={() => handleSwitchConv(c.id)}
                      >
                        {c.title || '新对话'}
                      </span>
                      <Popconfirm
                        title="确认删除该对话?"
                        onConfirm={(e) => {
                          e?.stopPropagation();
                          handleDeleteConv(c.id);
                        }}
                        okText="确认"
                        cancelText="取消"
                      >
                        <Button
                          type="text"
                          size="small"
                          danger
                          icon={<DeleteOutlined />}
                          className="flex-shrink-0 ml-1"
                          onClick={(e) => e.stopPropagation()}
                        />
                      </Popconfirm>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        />
        <Button
          type="text"
          size="small"
          icon={<PlusOutlined />}
          onClick={handleNewChat}
          title="新对话"
        />
      </div>

      {/* 消息列表 */}
      <div
        ref={msgListRef}
        className="flex-1 min-h-0 overflow-auto px-3 py-3 space-y-3"
        style={{ scrollBehavior: 'smooth' }}
      >
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                <span className="text-xs text-slate-400">
                  我是您的警务 AI 助手，可以帮您：<br />
                  检索法条 · 查询程序 · 生成/润色文书<br />
                  分析案情 · 检查期限 · 处罚参考 · 证据指引
                </span>
              }
            />
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] ${
                msg.role === 'user'
                  ? 'bg-police-600 text-white rounded-xl rounded-br-md'
                  : 'bg-slate-50 text-slate-800 rounded-xl rounded-bl-md border border-slate-100'
              } px-3.5 py-2.5 animate-fade-in`}
            >
              {/* 工具调用卡片 */}
              {msg.toolCalls && msg.toolCalls.length > 0 && (
                <div className="mb-2">
                  {msg.toolCalls.map((tc, i) => renderToolCall(tc, i))}
                </div>
              )}

              {/* 文本内容 */}
              {msg.content && (
                <div className={`text-sm whitespace-pre-wrap break-words leading-relaxed ${
                  msg.role === 'user' ? '' : 'document-preview text-sm'
                }`}>
                  {msg.content}
                  {msg.role === 'assistant' && streaming && msg.id === messages[messages.length - 1]?.id && (
                    <span className="inline-block w-1.5 h-4 bg-police-500 ml-0.5 animate-pulse align-middle" />
                  )}
                </div>
              )}

              {/* 空内容 + 进行中 */}
              {!msg.content && msg.role === 'assistant' && (
                <div className="flex items-center gap-2 text-xs text-slate-400">
                  <Spin indicator={<LoadingOutlined style={{ fontSize: 14 }} spin />} size="small" />
                  {thinkingText || '思考中...'}
                </div>
              )}
            </div>
          </div>
        ))}

        {/* 活跃的工具调用 (流式进行中) */}
        {activeToolCalls.filter((tc) => tc.status === 'running').map((tc, i) => (
          <div key={`active_tc_${i}`} className="flex justify-start">
            <div className="bg-blue-50/80 border border-blue-200 rounded-lg px-3 py-2 animate-fade-in max-w-[85%]">
              {renderToolCall(tc, i)}
            </div>
          </div>
        ))}
      </div>

      {/* 输入区域 */}
      <div className="flex-shrink-0 px-3 py-2.5 border-t border-slate-100">
        {docContext && (
          <Tag color="blue" className="mb-2 text-xs">
            <ThunderboltOutlined className="mr-1" />
            当前文书: {docType || '文书'} ({docContext.length} 字)
          </Tag>
        )}
        <div className="flex items-end gap-2">
          <Input.TextArea
            ref={inputRef as React.Ref<any>}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入消息... (Enter 发送，Shift+Enter 换行)"
            rows={2}
            disabled={streaming}
            className="text-sm flex-1"
            autoSize={{ minRows: 1, maxRows: 4 }}
          />
          {streaming ? (
            <Button
              type="primary"
              danger
              onClick={handleStop}
              className="flex-shrink-0"
            >
              停止
            </Button>
          ) : (
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSend}
              disabled={!inputValue.trim()}
              className="flex-shrink-0"
              style={{
                background: 'linear-gradient(135deg, #1a3a5c 0%, #1e4470 100%)',
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}
