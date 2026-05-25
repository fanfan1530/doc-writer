import { useState } from 'react';
import {
  Card, Button, Tag, Space, Typography, Collapse, Descriptions, Spin, App,
} from 'antd';
import {
  CopyOutlined, DownloadOutlined, FileTextOutlined,
  ThunderboltOutlined, CheckCircleOutlined,
} from '@ant-design/icons';
import client from '../api/client';
import type { GenerationResult } from '../types';

const { Text } = Typography;

interface DocumentPreviewProps {
  result: GenerationResult | null;
  generating: boolean;
  docType: string;
}

export default function DocumentPreview({
  result, generating, docType,
}: DocumentPreviewProps) {
  const { message } = App.useApp();
  const [downloading, setDownloading] = useState(false);

  const handleCopy = async () => {
    if (!result?.content) return;
    try {
      await navigator.clipboard.writeText(result.content);
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
        { content: result.content, doc_type: result.doc_type || docType },
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
    } catch {
      message.error('下载失败');
    } finally {
      setDownloading(false);
    }
  };

  // ─── Empty State ───
  if (!result && !generating) {
    return (
      <Card className="shadow-sm border-0 rounded-xl h-full flex items-center justify-center bg-white"
        bodyStyle={{ width: '100%' }}>
        <div className="text-center px-8 py-6">
          {/* Paper illustration */}
          <div className="relative mx-auto mb-5 w-24 h-28">
            <div className="absolute inset-0 bg-white border border-slate-200 rounded-sm shadow-md rotate-[-3deg]" />
            <div className="absolute inset-0 bg-white border border-slate-200 rounded-sm shadow-md rotate-[2deg] scale-95" />
            <div className="absolute inset-0 bg-white border border-slate-200 rounded-sm shadow-sm flex items-center justify-center">
              <FileTextOutlined className="text-2xl text-police-300" />
            </div>
          </div>
          <div className="text-base text-slate-600 font-medium mb-1">AI 智能文书生成</div>
          <div className="text-xs text-slate-400 mb-4">支持多种公安法律文书，输入案情即可一键生成</div>
          <div className="flex flex-wrap justify-center gap-2">
            {['行政处罚决定书', '检查笔录', '辨认笔录', '现场勘查笔录'].map((t) => (
              <Tag key={t} className="text-xs text-slate-500 bg-slate-50 border-slate-200">{t}</Tag>
            ))}
          </div>
        </div>
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
      bodyStyle={{ padding: '16px', display: 'flex', flexDirection: 'column', overflow: 'hidden', height: '100%' }}>

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
              共 {result.content.length} 字
            </Text>
          )}
        </Space>
        <Space size={4}>
          <Button icon={<CopyOutlined />} onClick={handleCopy} size="small" className="text-xs">
            复制
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

      {/* Paper document preview */}
      <div className="flex-1 min-h-0 overflow-auto py-3 px-1">
        <div className="document-preview bg-[#fdfaf5] p-8 rounded-sm min-h-full
          border border-amber-200/50
          shadow-[inset_0_0_20px_rgba(139,119,80,0.06)]
          "
          style={{
            backgroundImage: 'linear-gradient(rgba(180,160,120,0.03) 1px, transparent 1px)',
            backgroundSize: '100% 32px',
          }}>
          {result.content}
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
    </Card>
  );
}
