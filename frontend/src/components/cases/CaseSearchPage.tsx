/** 类案检索页面 —— 语义搜索相似案例 + 详情抽屉 + 跨模块联动 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Input, Button, Card, Empty, Tag, Spin, Segmented, Typography, Alert,
  Drawer, Descriptions, Divider, App,
} from 'antd';
import {
  SearchOutlined, SafetyCertificateOutlined, AimOutlined,
  CopyOutlined, FileTextOutlined, BulbOutlined,
} from '@ant-design/icons';
import client from '../../api/client';
import { useSharedTranscript } from '../../hooks/useSharedTranscript';
import { useAppContext } from '../../context/AppContext';
import ErrorBoundary from '../ErrorBoundary';
import type { CaseSearchResult } from '../../types';

const { TextArea } = Input;
const { Text } = Typography;

export default function CaseSearchPage() {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const { setSharedTranscript } = useAppContext();
  const [query, setQuery] = useState('');
  const [caseType, setCaseType] = useState<string>('all');
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<CaseSearchResult[]>([]);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState('');
  const [detailCase, setDetailCase] = useState<CaseSearchResult | null>(null);
  useSharedTranscript(setQuery);

  const handleSearch = async () => {
    if (!query.trim() || searching) return;
    setSearching(true);
    setSearched(true);
    setError('');
    try {
      const { data } = await client.post('/cases/search', {
        description: query.trim(),
        case_type: caseType === 'all' ? undefined : caseType,
        limit: 10,
      });
      setResults(data.cases || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : '检索失败，请稍后重试');
    } finally {
      setSearching(false);
    }
  };

  const handleAnalyzeCase = (caseItem: CaseSearchResult) => {
    setSharedTranscript({
      text: caseItem.key_facts,
      rawText: '',
      fileName: caseItem.title,
      uploadedAt: Date.now(),
    });
    navigate('/analysis');
  };

  const handleCopyCase = (caseItem: CaseSearchResult) => {
    const parts = [
      `标题: ${caseItem.title}`,
      `类型: ${caseItem.case_type}`,
      `关键事实: ${caseItem.key_facts}`,
      `处理结果: ${caseItem.penalty_outcome}`,
      `适用法律: ${(caseItem.laws || []).join('、')}`,
      `证据清单: ${(caseItem.evidence_list || []).join('、')}`,
    ];
    if (caseItem.procedural_notes) {
      parts.push(`执法提示: ${caseItem.procedural_notes}`);
    }
    navigator.clipboard.writeText(parts.join('\n\n')).then(
      () => message.success('案例信息已复制'),
    );
  };

  return (
    <div className="p-5 page-enter max-w-[1100px] mx-auto h-full flex flex-col min-h-0">
      <h2 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
        <SearchOutlined className="text-police-500" />
        类案检索
      </h2>

      {/* 搜索区 */}
      <Card className="rounded-xl shadow-sm border-0 mb-4 flex-shrink-0">
        <div className="flex gap-3 mb-3">
          <TextArea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="请输入案件描述，系统将检索相似案例。例如：2024年3月，嫌疑人张某在某小区内盗窃电动车一辆，价值约3000元..."
            rows={3}
            className="text-sm flex-1"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSearch();
              }
            }}
          />
        </div>
        <div className="flex items-center justify-between">
          <Segmented
            size="small"
            value={caseType}
            onChange={(v) => setCaseType(v as string)}
            options={[
              { label: '全部', value: 'all' },
              { label: '刑事', value: '刑事' },
              { label: '行政', value: '行政' },
              { label: '民事', value: '民事' },
            ]}
          />
          <button
            onClick={handleSearch}
            disabled={!query.trim() || searching}
            className="px-5 py-1.5 rounded-lg text-sm font-medium text-white flex items-center gap-1.5 transition-all"
            style={{
              background: query.trim()
                ? 'linear-gradient(135deg, #1a3a5c 0%, #1e4470 100%)'
                : '#cbd5e1',
            }}
          >
            {searching ? <Spin size="small" /> : <SearchOutlined />}
            检索
          </button>
        </div>
      </Card>

      {error && (
        <Alert type="error" message={error} closable onClose={() => setError('')}
          className="mb-3 rounded-lg" />
      )}

      {/* 结果区 */}
      <div className="flex-1 min-h-0 overflow-auto">
        {!searched ? (
          <div className="flex items-center justify-center h-full">
            <Empty description="输入案情描述后开始检索相似案例" />
          </div>
        ) : searching ? (
          <div className="flex items-center justify-center h-40">
            <Spin tip="正在检索相似案例..." />
          </div>
        ) : results.length === 0 ? (
          <Empty description="未找到相似案例，请尝试调整描述" />
        ) : (
          <ErrorBoundary
            FallbackComponent={({ error: err, onRetry }) => (
              <Empty
                description={
                  <span className="text-xs text-slate-400">
                    结果展示出错: {err?.message}
                    <br />
                    <Button size="small" type="link" onClick={onRetry}>重试</Button>
                  </span>
                }
              />
            )}
          >
            <div className="space-y-3">
              {results.map((c, i) => (
                <Card
                  key={c.id || i}
                  className="case-card rounded-xl shadow-sm border-slate-100 cursor-pointer"
                  hoverable
                  onClick={() => setDetailCase(c)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Text strong className="text-slate-800">
                          {c.title || '未命名案例'}
                        </Text>
                        {c.case_type && (
                          <Tag
                            color={
                              c.case_type === '刑事' ? 'red' :
                              c.case_type === '行政' ? 'blue' : 'green'
                            }
                            className="text-xs"
                          >
                            {c.case_type}
                          </Tag>
                        )}
                      </div>
                      <Text className="text-xs text-slate-500 line-clamp-2 block">
                        {c.key_facts || '暂无摘要'}
                      </Text>
                      <div className="mt-1.5 flex flex-wrap gap-1 items-center">
                        {c.penalty_outcome && (
                          <Tag color="orange" className="text-xs">
                            处理: {c.penalty_outcome.length > 40
                              ? c.penalty_outcome.slice(0, 40) + '...' : c.penalty_outcome}
                          </Tag>
                        )}
                        {c.laws && c.laws.length > 0 && (
                          <Tag className="text-xs bg-slate-50 text-slate-500 border-slate-200">
                            法条: {c.laws.length} 条
                          </Tag>
                        )}
                        {c.evidence_list && c.evidence_list.length > 0 && (
                          <Tag className="text-xs bg-green-50 text-green-600 border-green-200">
                            证据: {c.evidence_list.length} 项
                          </Tag>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0 ml-3">
                      <Button
                        type="text"
                        size="small"
                        icon={<AimOutlined />}
                        className="text-police-400 hover:text-police-600"
                        title="分析此案例"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleAnalyzeCase(c);
                        }}
                      />
                      {c.similarity_score != null && (
                        <div className="text-center">
                          <div
                            className="w-14 h-14 rounded-full flex items-center justify-center text-sm font-bold"
                            style={{
                              background: `conic-gradient(#1a3a5c ${c.similarity_score * 360}deg, #e2e8f0 0deg)`,
                              color: '#1a3a5c',
                            }}
                          >
                            <div className="w-11 h-11 rounded-full bg-white flex items-center justify-center">
                              {Math.round(c.similarity_score * 100)}%
                            </div>
                          </div>
                          <div className="text-[10px] text-slate-400 mt-1">相似度</div>
                        </div>
                      )}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </ErrorBoundary>
        )}
      </div>

      {/* 案例详情抽屉 */}
      <Drawer
        title={
          <span className="flex items-center gap-2">
            <FileTextOutlined className="text-police-500" />
            <span className="text-base font-semibold">{detailCase?.title || '案例详情'}</span>
            {detailCase?.case_type && (
              <Tag color={
                detailCase.case_type === '刑事' ? 'red' :
                detailCase.case_type === '行政' ? 'blue' : 'green'
              }>{detailCase.case_type}</Tag>
            )}
          </span>
        }
        placement="right"
        width={640}
        open={!!detailCase}
        onClose={() => setDetailCase(null)}
        extra={
          <div className="flex gap-2">
            <Button size="small" icon={<CopyOutlined />}
              onClick={() => detailCase && handleCopyCase(detailCase)}>
              复制
            </Button>
            <Button size="small" type="primary" icon={<AimOutlined />}
              onClick={() => detailCase && handleAnalyzeCase(detailCase)}>
              分析此案例
            </Button>
          </div>
        }
      >
        {detailCase && (
          <div className="space-y-4">
            <Card size="small" className="rounded-lg border-slate-100">
              <Descriptions column={1} size="small" colon={false}
                labelStyle={{ color: '#64748b', fontSize: 12 }}
                contentStyle={{ color: '#334155', fontSize: 13 }}
              >
                <Descriptions.Item label="关键事实">
                  <div className="whitespace-pre-wrap leading-relaxed">{detailCase.key_facts}</div>
                </Descriptions.Item>
                <Descriptions.Item label="处理结果">
                  <Tag color="orange">{detailCase.penalty_outcome}</Tag>
                </Descriptions.Item>
                {detailCase.similarity_score != null && (
                  <Descriptions.Item label="相似度">
                    <span className="font-bold text-police-600">
                      {Math.round(detailCase.similarity_score * 100)}%
                    </span>
                  </Descriptions.Item>
                )}
              </Descriptions>
            </Card>

            <Divider className="!my-2" />

            <Card size="small" className="rounded-lg border-slate-100" title={
              <span className="text-sm font-medium flex items-center gap-1.5">
                <SafetyCertificateOutlined className="text-blue-500" />
                适用法律
              </span>
            }>
              <div className="flex flex-wrap gap-1.5">
                {(detailCase.laws || []).map((law, j) => (
                  <Tag key={j} color="blue" className="text-xs">{law}</Tag>
                ))}
              </div>
            </Card>

            <Card size="small" className="rounded-lg border-slate-100" title={
              <span className="text-sm font-medium flex items-center gap-1.5">
                <FileTextOutlined className="text-green-500" />
                证据清单 ({detailCase.evidence_list?.length || 0} 项)
              </span>
            }>
              <ul className="list-disc list-inside space-y-1 m-0">
                {(detailCase.evidence_list || []).map((ev, j) => (
                  <li key={j} className="text-xs text-slate-600">{ev}</li>
                ))}
              </ul>
            </Card>

            {detailCase.procedural_notes && (
              <Card size="small" className="rounded-lg border-amber-200 bg-amber-50/50" title={
                <span className="text-sm font-medium flex items-center gap-1.5">
                  <BulbOutlined className="text-amber-500" />
                  执法操作提示
                </span>
              }>
                <div className="text-xs text-slate-700 leading-relaxed whitespace-pre-wrap">
                  {detailCase.procedural_notes}
                </div>
              </Card>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
}
