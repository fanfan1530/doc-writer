import { useEffect, useMemo, useState } from 'react';
import {
  Card, Button, Tag, Space, Typography, Collapse, Descriptions, Spin, App,
  Alert, Modal, Tooltip,
} from 'antd';
import {
  CopyOutlined, DownloadOutlined, PrinterOutlined,
  ThunderboltOutlined, CheckCircleOutlined, WarningOutlined,
  FullscreenOutlined,
} from '@ant-design/icons';
import client from '../api/client';
import type { GenerationResult } from '../types';
import EmptyState from './preview/EmptyState';

const { Text } = Typography;

interface DocumentPreviewProps {
  result: GenerationResult | null;
  generating: boolean;
  docType: string;
  highlightText?: string;
  highlightLabel?: string;
}

export default function DocumentPreview({
  result, generating, docType, highlightText, highlightLabel,
}: DocumentPreviewProps) {
  const { message } = App.useApp();
  const [downloading, setDownloading] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const displayContent = cleanTemplatePlaceholders(result?.content || '');
  const normalizedHighlight = useMemo(() => normalizeHighlightText(highlightText || ''), [highlightText]);

  useEffect(() => {
    if (!normalizedHighlight) return;
    window.setTimeout(() => {
      document.querySelector('[data-element-highlight="true"]')?.scrollIntoView({
        block: 'center',
        behavior: 'smooth',
      });
    }, 60);
  }, [normalizedHighlight, displayContent]);

  const handlePrint = () => {
    window.print();
  };

  const handleCopy = async () => {
    if (!result?.content) return;
    try {
      await navigator.clipboard.writeText(displayContent);
      message.success('已复制到剪贴板');
    } catch {
      message.info('请手动复制文书内容');
    }
  };

  const handleDownload = async () => {
    if (!result?.content) return;
    setDownloading(true);
    try {
      const resp = await client.post(
        '/generation/export-docx',
        { content: displayContent, doc_type: result.doc_type || docType },
        { responseType: 'blob' },
      );
      const blob = resp.data instanceof Blob
        ? resp.data
        : new Blob([resp.data], {
          type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const typeName = (result.doc_type || docType).replace(/[<>:"/\\|?*]/g, '_');
      const date = new Date().toISOString().slice(0, 10).replace(/-/g, '');
      a.download = `${typeName}_${date}.docx`;
      a.click();
      window.URL.revokeObjectURL(url);
      message.success('下载完成');
    } catch (err) {
      message.error(err instanceof Error ? err.message : '下载失败');
    } finally {
      setDownloading(false);
    }
  };

  // ─── Empty State ───
  if (!result && !generating) {
    return (
      <Card className="shadow-sm border-0 rounded-xl h-full flex items-center justify-center bg-white"
        styles={{ body: { width: '100%' } }}>
        <EmptyState />
      </Card>
    );
  }

  // ─── Loading State ───
  if (generating) {
    return (
      <Card className="shadow-sm border-0 rounded-xl h-full flex items-center justify-center bg-white">
        <div className="text-center py-8">
          <div className="relative mx-auto mb-4 w-12 h-12">
            <div className="absolute inset-0 rounded-full border-2 border-police-200 animate-pulse" />
            <div className="absolute inset-2 rounded-full border-2 border-police-400 animate-pulse [animation-delay:200ms]" />
            <div className="absolute inset-4 rounded-full bg-police-500 flex items-center justify-center">
              <Spin indicator={<ThunderboltOutlined style={{ fontSize: 14, color: '#fff' }} spin={false} />} />
            </div>
          </div>
          <div className="text-sm text-slate-600 font-medium">AI 正在生成文书</div>
          <div className="text-xs text-slate-400 mt-1">分析案情、抽取要素、匹配法条...</div>
        </div>
      </Card>
    );
  }

  if (!result) return null;

  const filledElements = Object.entries(result.elements).filter(
    ([, v]) => v && String(v).trim(),
  );

  return (
    <Card className="shadow-sm border-0 rounded-xl animate-fade-in h-full flex flex-col min-h-0 bg-white"
      styles={{ body: { padding: '16px', display: 'flex', flexDirection: 'column', overflow: 'hidden', height: '100%' } }}>

      {/* Toolbar */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-100 flex-shrink-0 flex-wrap gap-2">
        <Space wrap size={[4, 4]}>
          <Tag color="police-600" className="text-xs font-medium border-0"
            style={{ background: '#e8eef5', color: '#1a3a5c' }}>
            {result.doc_type || docType}
          </Tag>
          {result.case_nature && (
            <Tag color="blue" className="text-xs">{result.case_nature}</Tag>
          )}
          {result.content && (
            <Text type="secondary" className="text-xs">
              共 {displayContent.length} 字
            </Text>
          )}
          {normalizedHighlight && (
            <Tag color="gold" className="text-xs">
              定位：{highlightLabel || '当前要素'}
            </Tag>
          )}
        </Space>
        <Space size={4}>
          <Tooltip title="双击正文也可放大预览">
            <Button icon={<FullscreenOutlined />} onClick={() => setPreviewOpen(true)} size="small" className="text-xs">
              放大
            </Button>
          </Tooltip>
          <Button icon={<CopyOutlined />} onClick={handleCopy} size="small" className="text-xs">
            复制
          </Button>
          <Button
            icon={<PrinterOutlined />}
            size="small"
            onClick={handlePrint}
            className="text-xs"
          >
            打印
          </Button>
          <Button
            icon={<DownloadOutlined />}
            type="primary"
            ghost
            size="small"
            onClick={handleDownload}
            loading={downloading}
            className="text-xs"
          >
            下载 .docx
          </Button>
        </Space>
      </div>

      {/* Empty content warning */}
      {!result.content && (
        <Alert
          type="warning"
          icon={<WarningOutlined />}
          message="文书内容为空"
          description="AI 未能生成有效文书内容，可能是输入信息不足或所选文书类型不匹配。请尝试补充更多案情细节或更换文书类型后重新生成。"
          className="mb-2 flex-shrink-0 text-xs rounded-lg"
          showIcon
        />
      )}

      {/* Paper document preview */}
      <div className="flex-1 min-h-0 overflow-auto py-3 px-1">
        <div className="document-preview bg-[#fdfaf5] p-8 rounded-sm min-h-full
          border border-amber-200/50
          shadow-[inset_0_0_20px_rgba(139,119,80,0.06)]
          cursor-zoom-in
          "
          title="双击打开标准版式预览"
          onDoubleClick={() => setPreviewOpen(true)}
          style={{
            backgroundImage: 'linear-gradient(rgba(180,160,120,0.03) 1px, transparent 1px)',
            backgroundSize: '100% 32px',
          }}>
          <FormattedDocumentContent
            content={displayContent || '（无内容）'}
            docType={result.doc_type || docType}
            highlightText={normalizedHighlight}
          />
        </div>
      </div>

      {/* Footer: elements collapsible */}
      {filledElements.length > 0 && (
        <div className="flex-shrink-0 mt-1">
          <Collapse
            size="small"
            ghost
            items={[{
              key: 'elements',
              label: (
                <span className="text-xs text-slate-400">
                  <CheckCircleOutlined className="mr-1 text-emerald-500" />
                  已抽取 {filledElements.length} 个关键要素
                </span>
              ),
              children: (
                <Descriptions size="small" column={{ xs: 1, sm: 2 }} bordered>
                  {filledElements.slice(0, 30).map(([k, v]) => (
                    <Descriptions.Item key={k} label={<span className="text-xs">{k}</span>}>
                      <span className="text-xs">
                        {String(v).length > 80 ? String(v).substring(0, 80) + '...' : String(v)}
                      </span>
                    </Descriptions.Item>
                  ))}
                </Descriptions>
              ),
            }]}
          />
        </div>
      )}

      <Modal
        open={previewOpen}
        onCancel={() => setPreviewOpen(false)}
        footer={null}
        width="min(96vw, 980px)"
        centered
        className="document-preview-modal"
        title={
          <div className="flex items-center justify-between gap-3 pr-8">
            <Space wrap size={[6, 4]}>
              <Tag color="blue" className="m-0">{result.doc_type || docType}</Tag>
              {displayContent && <Text type="secondary" className="text-xs">共 {displayContent.length} 字</Text>}
              {normalizedHighlight && <Tag color="gold" className="m-0">定位：{highlightLabel || '当前要素'}</Tag>}
            </Space>
            <Space size={6}>
              <Button size="small" icon={<CopyOutlined />} onClick={handleCopy}>复制</Button>
              <Button size="small" icon={<PrinterOutlined />} onClick={handlePrint}>打印</Button>
              <Button
                size="small"
                type="primary"
                ghost
                icon={<DownloadOutlined />}
                loading={downloading}
                onClick={handleDownload}
              >
                下载 .docx
              </Button>
            </Space>
          </div>
        }
        styles={{ body: { background: '#f2f3f7', padding: '18px', maxHeight: '82vh', overflow: 'auto' } }}
      >
        <div className="mx-auto bg-white text-slate-900 border border-slate-200 shadow-xl"
          style={{
            width: '794px',
            minHeight: '1123px',
            maxWidth: '100%',
            padding: '96px 90px',
            boxSizing: 'border-box',
          }}
        >
          <div
            className="whitespace-pre-wrap break-words"
            style={{
              fontFamily: '"FangSong", "仿宋", "STFangsong", serif',
              fontSize: 18,
              lineHeight: 2,
              color: '#111827',
            }}
          >
            <FormattedDocumentContent
              content={displayContent || '（无内容）'}
              docType={result.doc_type || docType}
              highlightText={normalizedHighlight}
            />
          </div>
      </div>
      </Modal>
    </Card>
  );
}

function cleanTemplatePlaceholders(content: string): string {
  return content
    .replace(/{{\s*[\w.-]+\s*}}/g, '____')
    .replace(/\uFFFD/g, '');
}

function FormattedDocumentContent({
  content,
  docType,
  highlightText = '',
}: {
  content: string;
  docType: string;
  highlightText?: string;
}) {
  const lines = content.split('\n');
  const titleIndex = lines.findIndex((line) => line.trim());

  return (
    <>
      {lines.map((line, index) => {
        const trimmed = line.trim();
        const isTitle = index === titleIndex && looksLikeTitle(trimmed, docType);
        const isSignature = /公安机关|办案民警|被处罚人|记录人|检查人|见证人|年\s*月\s*日|\d{4}年\d{1,2}月\d{1,2}日/.test(trimmed)
          && trimmed.length <= 32
          && index > titleIndex;

        return (
          <div
            key={`${index}-${line}`}
            style={{
              minHeight: '1em',
              textAlign: isTitle ? 'center' : isSignature ? 'right' : 'left',
              fontWeight: isTitle ? 600 : 400,
              fontSize: isTitle ? '1.15em' : '1em',
              marginBottom: isTitle ? '1.2em' : undefined,
              textIndent: !isTitle && !isSignature && trimmed ? '2em' : 0,
            }}
          >
            {trimmed ? renderHighlightedText(trimmed, highlightText) : '\u00A0'}
          </div>
        );
      })}
    </>
  );
}

function looksLikeTitle(line: string, docType: string): boolean {
  if (!line) return false;
  if (line === docType) return true;
  return /(?:决定书|笔录|告知书|通知书|报告|协议书|清单|登记表)$/.test(line) && line.length <= 24;
}

function normalizeHighlightText(value: string): string {
  const trimmed = value.replace(/\s+/g, ' ').trim();
  if (!trimmed || trimmed.length < 2) return '';
  return trimmed.length > 80 ? trimmed.slice(0, 80) : trimmed;
}

function renderHighlightedText(text: string, highlightText: string) {
  if (!highlightText) return text;

  const exactParts = splitByHighlight(text, highlightText);
  if (exactParts) return exactParts;

  const shortHighlight = highlightText
    .split(/[，。；;,.、\n]/)
    .map((item) => item.trim())
    .filter((item) => item.length >= 3)
    .sort((a, b) => b.length - a.length)[0];

  if (!shortHighlight || shortHighlight === highlightText) return text;
  return splitByHighlight(text, shortHighlight) || text;
}

function splitByHighlight(text: string, highlightText: string) {
  const index = text.indexOf(highlightText);
  if (index < 0) return null;

  const before = text.slice(0, index);
  const match = text.slice(index, index + highlightText.length);
  const after = text.slice(index + highlightText.length);

  return (
    <>
      {before}
      <mark
        data-element-highlight="true"
        style={{
          background: '#fde68a',
          color: '#7c2d12',
          padding: '0 2px',
          borderRadius: 2,
          boxShadow: '0 0 0 1px rgba(245, 158, 11, 0.28)',
        }}
      >
        {match}
      </mark>
      {after}
    </>
  );
}
