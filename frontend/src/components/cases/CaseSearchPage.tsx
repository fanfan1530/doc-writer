/** 类案检索页面 —— 语义搜索相似案例 + 全局共享笔录 */
import { useState, useEffect } from 'react';
import { Input, Card, Empty, Tag, Spin, Segmented, Typography } from 'antd';
import { SearchOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAppContext } from '../../context/AppContext';

const { TextArea } = Input;
const { Text, Title } = Typography;

export default function CaseSearchPage() {
  const [query, setQuery] = useState('');
  const [caseType, setCaseType] = useState<string>('all');
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<any[]>([]);
  const [searched, setSearched] = useState(false);
  const { sharedTranscript } = useAppContext();

  // 从共享笔录恢复
  useEffect(() => {
    if (sharedTranscript && !query) {
      setQuery(sharedTranscript.text);
    }
  }, []);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    setSearched(true);
    try {
      const token = localStorage.getItem('access_token');
      const resp = await fetch('/api/cases/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          description: query.trim(),
          case_type: caseType === 'all' ? undefined : caseType,
          limit: 10,
        }),
      });
      if (resp.ok) {
        const data = await resp.json();
        setResults(data.cases || []);
      }
    } catch { /* ignore */ } finally {
      setSearching(false);
    }
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
          <div className="space-y-3">
            {results.map((c, i) => (
              <Card
                key={c.id || i}
                className="case-card rounded-xl shadow-sm border-slate-100 cursor-pointer"
                hoverable
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
                      {c.key_facts || c.description || '暂无摘要'}
                    </Text>
                    {c.penalty_outcome && (
                      <div className="mt-2">
                        <Tag color="orange" className="text-xs">
                          处理: {c.penalty_outcome}
                        </Tag>
                      </div>
                    )}
                    {c.laws && c.laws.length > 0 && (
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {c.laws.slice(0, 3).map((law: string, j: number) => (
                          <Tag key={j} className="text-xs bg-slate-50 text-slate-500 border-slate-200">
                            {law}
                          </Tag>
                        ))}
                      </div>
                    )}
                  </div>
                  {c.similarity_score != null && (
                    <div className="flex-shrink-0 ml-3 text-center">
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
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
