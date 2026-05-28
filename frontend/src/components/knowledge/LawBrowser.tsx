/** 法律法规浏览器 —— 搜索 + 动态文书类型筛选 + 卡片列表 */
import { useState, useEffect, useCallback } from 'react';
import { Input, Card, Empty, Tag, Pagination, Typography, Select, Skeleton, App } from 'antd';
import { SearchOutlined, CopyOutlined } from '@ant-design/icons';
import client from '../../api/client';

const { Text } = Typography;

interface LawItem {
  id: string | number;
  law_name: string;
  article_number: string;
  content: string;
  penalty_range?: string;
  applicable_doc_types?: string[];
}

function highlightText(text: string, keyword: string): React.ReactNode {
  if (!keyword.trim()) return text;
  const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const parts = text.split(new RegExp(`(${escaped})`, 'gi'));
  return parts.map((part, i) =>
    part.toLowerCase() === keyword.toLowerCase()
      ? <mark key={i} className="bg-amber-200 rounded px-0.5">{part}</mark>
      : part,
  );
}

function LawSkeleton() {
  return (
    <Card size="small" className="rounded-xl shadow-sm border-slate-100">
      <div className="flex items-center gap-2 mb-1.5">
        <Skeleton.Button active size="small" style={{ width: 70, height: 22 }} />
        <Skeleton.Input active size="small" style={{ width: 160, height: 20 }} />
      </div>
      <Skeleton.Input active size="small" block style={{ height: 16, marginTop: 4 }} />
      <Skeleton.Input active size="small" block style={{ height: 16, marginTop: 4, width: '70%' }} />
    </Card>
  );
}

export default function LawBrowser() {
  const { message } = App.useApp();
  const [laws, setLaws] = useState<LawItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [docTypeFilter, setDocTypeFilter] = useState('');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [docTypes, setDocTypes] = useState<{ doc_type: string; name: string }[]>([]);
  const pageSize = 12;

  // Load doc type options
  useEffect(() => {
    client.get('/knowledge/doc-types').then(({ data }) => {
      setDocTypes(data.doc_types || []);
    }).catch(() => {});
  }, []);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (page === 1) loadLaws(1);
      else setPage(1);
    }, 400);
    return () => clearTimeout(timer);
  }, [search, docTypeFilter]);

  const loadLaws = useCallback(async (p: number = page) => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { page: p, page_size: pageSize };
      if (search) params.search = search;
      if (docTypeFilter) params.doc_type = docTypeFilter;
      const { data } = await client.get('/knowledge/laws', { params });
      setLaws(data.laws || []);
      setTotal(data.total || 0);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  }, [search, docTypeFilter]);

  useEffect(() => { loadLaws(page); }, [page]);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text).then(() => message.success('已复制')).catch(() => {});
  };

  const hasActiveFilters = !!search || !!docTypeFilter;

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* 搜索栏 */}
      <Card className="rounded-xl shadow-sm border-0 mb-3 flex-shrink-0" size="small">
        <div className="flex gap-3 flex-wrap">
          <Input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="搜索法律名称、条款内容..."
            className="max-w-sm"
            allowClear
            prefix={<SearchOutlined className="text-slate-400" />}
          />
          <Select
            value={docTypeFilter || undefined}
            onChange={v => setDocTypeFilter(v || '')}
            placeholder="按文书类型筛选"
            allowClear
            showSearch
            className="min-w-[200px]"
            options={docTypes.map(d => ({ label: d.name || d.doc_type, value: d.doc_type }))}
          />
          {hasActiveFilters && !loading && (
            <Tag color="blue" className="flex items-center gap-1">{total} 条结果</Tag>
          )}
        </div>
      </Card>

      {/* 法条列表 */}
      <div className="flex-1 overflow-auto min-h-0">
        {loading && laws.length === 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {Array.from({ length: 6 }).map((_, i) => <LawSkeleton key={i} />)}
          </div>
        ) : laws.length === 0 ? (
          <Empty description={hasActiveFilters ? '未找到匹配的法律法规' : '暂无法律法规数据'} />
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
              {laws.map(law => (
                <Card
                  key={law.id}
                  className="rounded-xl shadow-sm border-slate-100 hover:border-police-200 transition-colors"
                  size="small"
                  extra={
                    <button
                      onClick={() => handleCopy(`《${law.law_name}》${law.article_number}: ${law.content}`)}
                      className="text-police-400 hover:text-police-600"
                      title="复制引用"
                    >
                      <CopyOutlined />
                    </button>
                  }
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <Tag color="blue" className="text-xs font-mono">
                      {search ? highlightText(law.article_number, search) : law.article_number}
                    </Tag>
                    <Text strong className="text-sm text-slate-700">
                      {search ? highlightText(law.law_name, search) : law.law_name}
                    </Text>
                  </div>
                  <Text className="text-xs text-slate-600 leading-relaxed line-clamp-3 block">
                    {search ? highlightText(law.content, search) : law.content}
                  </Text>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {law.penalty_range && (
                      <Tag color="orange" className="text-xs">
                        处罚: {search ? highlightText(law.penalty_range, search) : law.penalty_range}
                      </Tag>
                    )}
                    {(law.applicable_doc_types || []).slice(0, 3).map((dt, i) => (
                      <Tag key={i} className="text-xs bg-slate-50 text-slate-500 border-slate-200">
                        {search ? highlightText(dt, search) : dt}
                      </Tag>
                    ))}
                  </div>
                </Card>
              ))}
            </div>

            {total > pageSize && (
              <div className="flex justify-center pb-4">
                <Pagination
                  current={page} pageSize={pageSize} total={total}
                  onChange={setPage} showSizeChanger={false} size="small"
                />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
