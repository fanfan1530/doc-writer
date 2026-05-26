/** 案件分析页面 —— 上传笔录 → 一键分析 → 时间线 + 定性 双栏展示 */
import { useState, useCallback, useEffect, useRef } from 'react';
import {
  Input, Button, Card, Spin, Timeline, Tag, Empty, Typography,
  Upload, App, Progress, Descriptions, Divider,
} from 'antd';
import {
  ClockCircleOutlined, SafetyCertificateOutlined,
  EnvironmentOutlined, UserOutlined, InboxOutlined,
  LoadingOutlined, ThunderboltOutlined, FileTextOutlined,
  ClearOutlined, CopyOutlined, AimOutlined,
} from '@ant-design/icons';
import { useFileUpload } from '../../hooks/useFileUpload';
import { useAppContext } from '../../context/AppContext';
import type { UploadProps } from 'antd';

const { TextArea } = Input;
const { Text, Title } = Typography;

const EVENT_ICONS: Record<string, React.ReactNode> = {
  arrest: <span className="text-lg">🚔</span>,
  investigation: <span className="text-lg">🔍</span>,
  evidence: <span className="text-lg">📋</span>,
  court: <span className="text-lg">⚖️</span>,
  report: <span className="text-lg">📝</span>,
  other: <span className="text-lg">📌</span>,
};

const EVENT_COLORS: Record<string, string> = {
  arrest: '#ef4444',
  investigation: '#3b82f6',
  evidence: '#22c55e',
  court: '#d4a853',
  report: '#a855f7',
  other: '#94a3b8',
};

const EVENT_LABELS: Record<string, string> = {
  arrest: '抓捕/到案',
  investigation: '侦查',
  evidence: '取证',
  court: '庭审/裁决',
  report: '报案/受理',
  other: '其他',
};

export default function CaseAnalysisPage() {
  const { message } = App.useApp();
  const [caseText, setCaseText] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState('');
  const [timeline, setTimeline] = useState<any[]>([]);
  const [analysis, setAnalysis] = useState('');
  const { sharedTranscript, setSharedTranscript } = useAppContext();

  // 从共享笔录恢复（切换页面后自动填充）
  useEffect(() => {
    if (sharedTranscript && !caseText) {
      setCaseText(sharedTranscript.text);
    }
  }, []);

  // refs: 解决 useFileUpload 与回调之间循环依赖
  const uploadedFileNameRef = useRef('');
  const rawTextPreviewRef = useRef('');

  // 文件上传 —— 上传完成后自动触发分析 + 写入全局共享笔录
  const handleTextExtracted = useCallback((text: string) => {
    setCaseText(text);
    setSharedTranscript({
      text,
      rawText: rawTextPreviewRef.current || '',
      fileName: uploadedFileNameRef.current || '笔录文件',
      uploadedAt: Date.now(),
    });
    // 自动触发全部分析
    setTimeout(() => runFullAnalysis(text), 300);
  }, [setSharedTranscript]);

  const {
    uploading, uploadedFileName, rawTextPreview,
    showRawText, setShowRawText, uploadFile,
  } = useFileUpload(handleTextExtracted);

  // 同步 refs
  uploadedFileNameRef.current = uploadedFileName || '';
  rawTextPreviewRef.current = rawTextPreview || '';

  const uploadProps: UploadProps = {
    name: 'file',
    accept: '.doc,.docx',
    maxCount: 1,
    showUploadList: false,
    beforeUpload: (file) => {
      const lower = file.name.toLowerCase();
      if (!lower.endsWith('.doc') && !lower.endsWith('.docx')) {
        message.warning('仅支持 .doc 和 .docx 格式的笔录文件');
        return Upload.LIST_IGNORE;
      }
      if ((file.size ?? 0) > 10 * 1024 * 1024) {
        message.warning('文件大小不能超过 10 MB');
        return Upload.LIST_IGNORE;
      }
      uploadFile(file as unknown as File, '行政处罚决定书');
      return false;
    },
  };

  const handleClear = () => {
    setCaseText('');
    setTimeline([]);
    setAnalysis('');
  };

  const handleCopyTimeline = () => {
    const text = timeline.map((e, i) =>
      `${i + 1}. [${e.timestamp}] ${EVENT_LABELS[e.event_type] || '事件'}: ${e.description}`
    ).join('\n');
    navigator.clipboard.writeText(text).then(() => message.success('时间线已复制'));
  };

  // ── 一键全部分析 ──
  const runFullAnalysis = async (text?: string) => {
    const content = (text || caseText).trim();
    if (!content) return;

    setLoading(true);
    setTimeline([]);
    setAnalysis('');

    const token = localStorage.getItem('access_token');
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };

    // 并行请求
    setLoadingStep('正在提取时间线...');
    const timelinePromise = fetch('/api/generation/extract-timeline', {
      method: 'POST', headers,
      body: JSON.stringify({ case_text: content }),
    }).then(r => r.ok ? r.json() : { events: [] }).catch(() => ({ events: [] }));

    setLoadingStep('正在定性分析...');
    const analysisPromise = fetch('/api/generation/extract-elements', {
      method: 'POST', headers,
      body: JSON.stringify({ input_text: content, doc_type: '行政处罚决定书' }),
    }).then(r => r.ok ? r.json() : { elements: {} }).catch(() => ({ elements: {} }));

    try {
      const [timelineData, analysisData] = await Promise.all([timelinePromise, analysisPromise]);
      setTimeline(timelineData.events || []);

      const el = analysisData.elements || {};
      if (el.case_nature || el.suspect_name || el.illegal_fact) {
        const parts: string[] = [];
        if (el.case_nature) parts.push(`案件性质: ${el.case_nature}`);
        if (el.suspect_name) parts.push(`涉案人员: ${el.suspect_name}`);
        if (el.case_cause) parts.push(`案由: ${el.case_cause}`);
        if (el.illegal_fact) parts.push(`违法事实: ${el.illegal_fact}`);
        if (el.suggested_laws && Array.isArray(el.suggested_laws) && el.suggested_laws.length > 0) {
          parts.push(`适用法律: ${el.suggested_laws.join('；')}`);
        }
        setAnalysis(parts.join('\n\n'));
      } else {
        setAnalysis('（AI 未能提取到足够信息，请检查案情描述是否完整）');
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
      setLoadingStep('');
    }
  };

  const hasContent = caseText.trim().length > 0;
  const hasResults = timeline.length > 0 || analysis.length > 0;

  // ── 上传进度条 ──
  const uploadBar = uploading && uploadedFileName && (
    <div className="mb-3 p-3 bg-gradient-to-r from-blue-50 to-sky-50 border border-blue-200 rounded-xl animate-fade-in relative overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/40 to-transparent animate-shimmer" />
      <div className="flex items-center gap-2.5 relative">
        <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center flex-shrink-0">
          <Spin indicator={<LoadingOutlined style={{ fontSize: 14, color: '#fff' }} spin />} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-xs font-medium text-blue-700 truncate">{uploadedFileName}</div>
          <div className="text-[11px] text-blue-500">AI 正在解析文书内容，分析完成后将自动展示结果...</div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="p-5 page-enter max-w-[1400px] mx-auto h-full flex flex-col min-h-0">
      {/* 页面标题 */}
      <div className="flex items-center justify-between mb-4 flex-shrink-0">
        <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2 m-0">
          <AimOutlined className="text-police-500" />
          案件分析
        </h2>
        {hasContent && (
          <Button size="small" icon={<ClearOutlined />} onClick={handleClear} disabled={loading}>
            清空
          </Button>
        )}
      </div>

      <div className="flex-1 min-h-0 flex flex-col lg:flex-row gap-4">
        {/* ── 左侧：输入区 ── */}
        <div className="w-full lg:w-[400px] flex-shrink-0 flex flex-col gap-3 min-h-0">
          {/* 上传卡片 */}
          <Card size="small" className="rounded-xl shadow-sm border-0 flex-shrink-0"
            styles={{ body: { padding: '12px' } }}>
            <Upload.Dragger
              {...uploadProps}
              className="rounded-lg hover:border-police-400 transition-colors"
              style={{ padding: '10px 0' }}
              disabled={uploading}
            >
              <div className="flex items-center justify-center gap-2">
                <InboxOutlined className="text-base text-police-400" />
                <span className="text-[11px] text-slate-500">
                  拖入或点击上传 .doc/.docx 笔录
                </span>
              </div>
            </Upload.Dragger>
          </Card>

          {uploadBar}

          {/* 文本输入 */}
          <Card size="small" className="rounded-xl shadow-sm border-0 flex-1 flex flex-col min-h-0"
            styles={{ body: { padding: '12px', display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 } }}>
            <div className="flex items-center justify-between mb-2 flex-shrink-0">
              <Text className="text-xs font-medium text-slate-500 flex items-center gap-1">
                <FileTextOutlined /> 案情描述
              </Text>
              <Text className="text-[10px] text-slate-400">{caseText.length} 字</Text>
            </div>
            <TextArea
              value={caseText}
              onChange={(e) => setCaseText(e.target.value)}
              placeholder="上传笔录文件自动提取，或在此手动输入案情..."
              className="text-sm flex-1"
              style={{ resize: 'none', minHeight: 0 }}
              styles={{ textarea: { height: '100%' } }}
            />
          </Card>

          {/* 操作按钮 */}
          <Button
            type="primary"
            size="large"
            block
            icon={loading ? <LoadingOutlined /> : <ThunderboltOutlined />}
            onClick={() => runFullAnalysis()}
            loading={loading}
            disabled={!hasContent}
            className="flex-shrink-0 h-11 text-base font-semibold rounded-xl"
            style={{
              background: hasContent
                ? 'linear-gradient(135deg, #1a3a5c 0%, #1e4470 100%)'
                : undefined,
            }}
          >
            {loading ? loadingStep || '分析中...' : '一键全部分析'}
          </Button>

          {/* 笔录原文展开 */}
          {rawTextPreview && (
            <div className="flex-shrink-0">
              <Button type="link" size="small" onClick={() => setShowRawText(!showRawText)}>
                {showRawText ? '收起' : '查看'}笔录原文 ({rawTextPreview.length} 字)
              </Button>
              {showRawText && (
                <div className="p-2.5 bg-slate-50 rounded-lg text-xs text-slate-600 max-h-[120px] overflow-auto whitespace-pre-wrap border border-slate-200 leading-relaxed mt-1">
                  {rawTextPreview}
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── 右侧：结果区 —— 上下两栏 ── */}
        <div className="flex-1 min-w-0 min-h-0 flex flex-col gap-3">
          {!hasResults && !loading && (
            <div className="flex-1 flex items-center justify-center min-h-0">
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={
                  <span className="text-xs text-slate-400">
                    上传 Word 笔录或输入案情后<br />点击「一键全部分析」即可查看结果
                  </span>
                }
              />
            </div>
          )}

          {loading && (
            <div className="flex-1 flex flex-col items-center justify-center gap-3 min-h-0">
              <Spin size="large" />
              <Text className="text-sm text-slate-400">{loadingStep}</Text>
            </div>
          )}

          {hasResults && (
            <>
              {/* 时间线 */}
              <Card
                size="small"
                title={
                  <span className="text-sm font-semibold flex items-center gap-1.5">
                    <ClockCircleOutlined className="text-police-500" /> 案件时间线
                  </span>
                }
                extra={
                  timeline.length > 0 && (
                    <Button size="small" type="text" icon={<CopyOutlined />}
                      onClick={handleCopyTimeline} className="text-xs" />
                  )
                }
                className="rounded-xl shadow-sm border-0 flex-shrink-0"
                styles={{ body: { padding: '8px 16px', maxHeight: 360, overflow: 'auto' } }}
              >
                {timeline.length === 0 ? (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="未提取到时间线事件" className="py-4" />
                ) : (
                  <Timeline className="case-timeline mt-1">
                    {timeline.map((event, i) => (
                      <Timeline.Item
                        key={i}
                        color={EVENT_COLORS[event.event_type] || EVENT_COLORS.other}
                        dot={EVENT_ICONS[event.event_type] || EVENT_ICONS.other}
                      >
                        <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                          <Text strong className="text-slate-700 text-sm">
                            {event.timestamp || `事件 ${i + 1}`}
                          </Text>
                          <Tag className="text-[10px] leading-tight" color={
                            event.event_type === 'arrest' ? 'red' :
                            event.event_type === 'investigation' ? 'blue' :
                            event.event_type === 'evidence' ? 'green' :
                            event.event_type === 'court' ? 'gold' : 'default'
                          }>
                            {EVENT_LABELS[event.event_type] || '其他'}
                          </Tag>
                        </div>
                        <Text className="text-sm text-slate-600">{event.description}</Text>
                        {(event.location || event.involved_parties) && (
                          <div className="mt-1 flex gap-3 text-xs text-slate-400">
                            {event.location && (
                              <span><EnvironmentOutlined className="mr-0.5" />{event.location}</span>
                            )}
                            {event.involved_parties && (
                              <span><UserOutlined className="mr-0.5" />{event.involved_parties}</span>
                            )}
                          </div>
                        )}
                      </Timeline.Item>
                    ))}
                  </Timeline>
                )}
              </Card>

              {/* 案件定性 */}
              <Card
                size="small"
                title={
                  <span className="text-sm font-semibold flex items-center gap-1.5">
                    <SafetyCertificateOutlined className="text-police-500" /> 案件定性分析
                  </span>
                }
                className="rounded-xl shadow-sm border-0 flex-1 min-h-0"
                styles={{ body: { padding: '12px 16px', overflow: 'auto', flex: 1, minHeight: 0 } }}
              >
                {!analysis ? (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="未生成分析结果" className="py-4" />
                ) : (
                  <pre className="text-sm text-slate-700 whitespace-pre-wrap font-sans leading-relaxed m-0">
                    {analysis}
                  </pre>
                )}
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
