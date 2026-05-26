/** 历史文书详情 Drawer —— 查看完整生成内容、要素、法条 */
import { useEffect, useState } from 'react';
import { Drawer, Descriptions, Tag, Button, Spin, Empty, Divider } from 'antd';
import { CopyOutlined, ExportOutlined, ReloadOutlined } from '@ant-design/icons';
import client from '../../api/client';

interface HistoryDetail {
  id: number;
  doc_type: string;
  input_text: string;
  output_content: string;
  model_used: string;
  tokens_used: number;
  latency_ms: number;
  elements: Record<string, string>;
  suggested_laws: string[];
  created_at: string;
}

interface Props {
  open: boolean;
  historyId: number | null;
  onClose: () => void;
  onCopy: (content: string) => void;
  onReuse: (item: HistoryDetail) => void;
}

export default function HistoryDrawer({ open, historyId, onClose, onCopy, onReuse }: Props) {
  const [detail, setDetail] = useState<HistoryDetail | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !historyId) return;
    (async () => {
      setLoading(true);
      setDetail(null);
      try {
        const { data } = await client.get(`/generation/history/${historyId}`);
        setDetail(data);
      } catch {
        setDetail(null);
      } finally {
        setLoading(false);
      }
    })();
  }, [open, historyId]);

  const handleExport = async () => {
    if (!detail?.output_content) return;
    try {
      const resp = await client.post('/generation/export-docx', {
        content: detail.output_content,
        doc_type: detail.doc_type,
      }, { responseType: 'blob' });
      const blob = resp.data instanceof Blob ? resp.data : new Blob([resp.data]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${detail.doc_type || '文书'}_${detail.id}.docx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // ignore
    }
  };

  return (
    <Drawer
      open={open}
      onClose={onClose}
      width={680}
      title={detail ? (
        <span className="flex items-center gap-2">
          <Tag color={
            detail.doc_type.includes('行政') ? 'blue' :
            detail.doc_type.includes('刑事') ? 'red' :
            detail.doc_type.includes('民事') ? 'green' : 'default'
          }>{detail.doc_type}</Tag>
          <span className="text-sm text-slate-600">生成于 {new Date(detail.created_at).toLocaleString('zh-CN')}</span>
        </span>
      ) : '文书详情'}
      styles={{ body: { paddingBottom: 48 } }}
    >
      {loading ? (
        <div className="flex justify-center py-20"><Spin /></div>
      ) : !detail ? (
        <Empty description="加载失败" />
      ) : (
        <div className="space-y-4">
          {/* 基本信息 */}
          <Descriptions size="small" column={2} bordered>
            <Descriptions.Item label="文书类型">{detail.doc_type}</Descriptions.Item>
            <Descriptions.Item label="生成时间">
              {new Date(detail.created_at).toLocaleString('zh-CN')}
            </Descriptions.Item>
            <Descriptions.Item label="模型">{detail.model_used || '-'}</Descriptions.Item>
            <Descriptions.Item label="耗时">{detail.latency_ms ? `${detail.latency_ms}ms` : '-'}</Descriptions.Item>
          </Descriptions>

          {/* 案情输入 */}
          <div>
            <Divider className="!my-2" orientation="left" plain>
              <span className="text-xs text-slate-500 font-medium">案情输入</span>
            </Divider>
            <pre className="text-sm text-slate-700 whitespace-pre-wrap font-sans leading-relaxed bg-slate-50 p-3 rounded-lg max-h-[180px] overflow-auto">
              {detail.input_text}
            </pre>
          </div>

          {/* 提取的要素 */}
          {detail.elements && Object.keys(detail.elements).length > 0 && (
            <div>
              <Divider className="!my-2" orientation="left" plain>
                <span className="text-xs text-slate-500 font-medium">提取要素</span>
              </Divider>
              <Descriptions size="small" column={1} labelStyle={{ color: '#94a3b8', fontSize: 12 }}>
                {Object.entries(detail.elements).map(([k, v]) => (
                  <Descriptions.Item key={k} label={k}>{String(v)}</Descriptions.Item>
                ))}
              </Descriptions>
            </div>
          )}

          {/* 推荐法条 */}
          {detail.suggested_laws && detail.suggested_laws.length > 0 && (
            <div>
              <Divider className="!my-2" orientation="left" plain>
                <span className="text-xs text-slate-500 font-medium">推荐法条</span>
              </Divider>
              <div className="flex flex-wrap gap-1">
                {detail.suggested_laws.map((law, i) => (
                  <Tag key={i} color="blue" className="text-xs">{law}</Tag>
                ))}
              </div>
            </div>
          )}

          {/* 文书全文 */}
          <div>
            <Divider className="!my-2" orientation="left" plain>
              <span className="text-xs text-slate-500 font-medium">文书全文</span>
            </Divider>
            <pre className="text-sm text-slate-700 whitespace-pre-wrap font-sans leading-relaxed bg-white border border-slate-100 p-4 rounded-lg max-h-[400px] overflow-auto">
              {detail.output_content || '（无内容）'}
            </pre>
          </div>

          {/* 操作按钮 */}
          <div className="flex gap-2 pt-2">
            <Button icon={<CopyOutlined />}
              onClick={() => onCopy(detail.output_content)}>复制全文</Button>
            <Button icon={<ExportOutlined />}
              onClick={handleExport}>导出 Word</Button>
            <Button icon={<ReloadOutlined />}
              onClick={() => onReuse(detail)}>基于该案由重新生成</Button>
          </div>
        </div>
      )}
    </Drawer>
  );
}
