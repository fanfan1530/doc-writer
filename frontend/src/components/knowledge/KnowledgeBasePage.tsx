/** 知识库浏览页面 —— 法律法规检索与浏览 */
import { useState, useEffect } from 'react';
import { Input, Card, Empty, Spin, Tag, Pagination, Typography, Select } from 'antd';
import { BookOutlined, SearchOutlined, CopyOutlined } from '@ant-design/icons';
import { App } from 'antd';

const { Text } = Typography;
const { Search } = Input;

interface LawItem {
  id: string | number;
  law_name: string;
  article_number: string;
  content: string;
  penalty_range?: string;
  applicable_doc_types?: string[];
}

export default function KnowledgeBasePage() {
  const { message } = App.useApp();
  const [laws, setLaws] = useState<LawItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [docTypeFilter, setDocTypeFilter] = useState<string>('');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 12;

  useEffect(() => {
    loadLaws();
  }, [page, docTypeFilter]);

  const loadLaws = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('page_size', String(pageSize));
      if (search) params.set('search', search);
      if (docTypeFilter) params.set('doc_type', docTypeFilter);

      const resp = await fetch(`/api/knowledge/laws?${params}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (resp.ok) {
        const data = await resp.json();
        setLaws(data.laws || []);
        setTotal(data.total || 0);
      }
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    setPage(1);
    loadLaws();
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      message.success('已复制到剪贴板');
    }).catch(() => {
      message.error('复制失败');
    });
  };

  return (
    <div className="p-5 page-enter max-w-[1200px] mx-auto h-full flex flex-col min-h-0">
      <h2 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
        <BookOutlined className="text-police-500" />
        知识库
      </h2>

      {/* 搜索 + 过滤 */}
      <Card className="rounded-xl shadow-sm border-0 mb-4 flex-shrink-0">
        <div className="flex gap-3 flex-wrap">
          <Search
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onSearch={handleSearch}
            placeholder="搜索法律名称、条款内容..."
            className="max-w-sm"
            allowClear
            enterButton={<><SearchOutlined /> 搜索</>}
          />
          <Select
            value={docTypeFilter || undefined}
            onChange={(v) => { setDocTypeFilter(v || ''); setPage(1); }}
            placeholder="按文书类型筛选"
            allowClear
            className="min-w-[160px]"
            options={[
              { label: '行政处罚决定书', value: '行政处罚决定书' },
              { label: '检查笔录', value: '检查笔录' },
              { label: '现场勘查笔录', value: '现场勘查笔录' },
              { label: '辨认笔录', value: '辨认笔录' },
              { label: '扣押决定书', value: '扣押决定书' },
              { label: '指认笔录', value: '指认笔录' },
            ]}
          />
        </div>
      </Card>

      {/* 法条列表 */}
      <div className="flex-1 min-h-0 overflow-auto">
        {loading ? (
          <div className="flex justify-center py-20"><Spin /></div>
        ) : laws.length === 0 ? (
          <Empty description="暂无匹配的法律法规" />
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
              {laws.map((law) => (
                <Card
                  key={law.id}
                  className="rounded-xl shadow-sm border-slate-100 hover:border-police-200 transition-colors"
                  size="small"
                  extra={
                    <button
                      onClick={() => handleCopy(
                        `《${law.law_name}》${law.article_number}: ${law.content}`
                      )}
                      className="text-police-400 hover:text-police-600 transition-colors"
                      title="复制引用"
                    >
                      <CopyOutlined />
                    </button>
                  }
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <Tag color="blue" className="text-xs font-mono">
                      {law.article_number}
                    </Tag>
                    <Text strong className="text-sm text-slate-700">{law.law_name}</Text>
                  </div>
                  <Text className="text-xs text-slate-600 leading-relaxed line-clamp-3 block">
                    {law.content}
                  </Text>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {law.penalty_range && (
                      <Tag color="orange" className="text-xs">处罚: {law.penalty_range}</Tag>
                    )}
                    {(law.applicable_doc_types || []).slice(0, 3).map((dt, i) => (
                      <Tag key={i} className="text-xs bg-slate-50 text-slate-500 border-slate-200">
                        {dt}
                      </Tag>
                    ))}
                  </div>
                </Card>
              ))}
            </div>

            {total > pageSize && (
              <div className="flex justify-center pb-4">
                <Pagination
                  current={page}
                  pageSize={pageSize}
                  total={total}
                  onChange={setPage}
                  showSizeChanger={false}
                  size="small"
                />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
