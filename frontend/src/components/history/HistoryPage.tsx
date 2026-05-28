/** 历史文书页面 —— 浏览、搜索、查看过往生成的所有文书（服务端排序 + URL 状态持久化） */
import { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Card, Table, Tag, Input, Select, Button, Statistic, Row, Col,
  Skeleton, Empty, App, Space, Tooltip,
} from 'antd';
import type { TableProps } from 'antd';
import {
  FileTextOutlined, ClockCircleOutlined, CheckCircleOutlined,
  SearchOutlined, EyeOutlined, CopyOutlined,
  ReloadOutlined, ClearOutlined, DownloadOutlined,
  SortAscendingOutlined,
} from '@ant-design/icons';
import client from '../../api/client';
import { DOC_TYPES } from '../../constants/docTypes';
import { useHistoryStats } from '../../hooks/useHistoryStats';
import HistoryDrawer from './HistoryDrawer';

interface HistoryItem {
  id: number;
  doc_type: string;
  input_text: string;
  output_content: string;
  model_used: string;
  latency_ms: number;
  elements: Record<string, string>;
  suggested_laws: string[];
  created_at: string;
}

type SortField = 'created_at' | 'doc_type' | 'latency_ms' | 'id';

export default function HistoryPage() {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [items, setItems] = useState<HistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const { stats, loading: statsLoading } = useHistoryStats();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  // 筛选和排序状态 —— 从 URL 参数初始化
  const [keyword, setKeyword] = useState(searchParams.get('keyword') || '');
  const [docType, setDocType] = useState(searchParams.get('doc_type') || '');
  const [activeFilter, setActiveFilter] = useState(searchParams.get('filter') || '');
  const [page, setPage] = useState(Number(searchParams.get('page')) || 1);
  const [sortField, setSortField] = useState<SortField>(
    (searchParams.get('sort') as SortField) || 'created_at',
  );
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>(
    (searchParams.get('order') as 'asc' | 'desc') || 'desc',
  );
  const pageSize = 15;
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  const fetchHistory = useCallback(async (
    p: number, kw: string, dt: string, filter: string,
    sf: SortField, so: string,
  ) => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = {
        limit: pageSize,
        offset: (p - 1) * pageSize,
        sort_by: sf,
        sort_order: so,
      };
      if (kw) params.keyword = kw;
      if (dt) params.doc_type = dt;
      if (filter === 'recent') {
        const d = new Date(Date.now() - 7 * 24 * 3600 * 1000);
        params.since = d.toISOString();
      }

      const { data } = await client.get('/generation/history', { params });
      setItems(data.history || []);
      setTotal(data.total || 0);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHistory(page, keyword, docType, activeFilter, sortField, sortOrder);
  }, [page, keyword, docType, activeFilter, sortField, sortOrder, fetchHistory]);

  // 同步筛选到 URL（debounced for keyword）
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      const params: Record<string, string> = {};
      if (activeFilter) params.filter = activeFilter;
      if (docType) params.doc_type = docType;
      if (keyword) params.keyword = keyword;
      if (page > 1) params.page = String(page);
      if (sortField !== 'created_at') params.sort = sortField;
      if (sortOrder !== 'desc') params.order = sortOrder;
      setSearchParams(params, { replace: true });
    }, 200);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [activeFilter, docType, keyword, page, sortField, sortOrder, setSearchParams]);

  const handleFilterClick = (filter: string) => {
    setActiveFilter((prev) => (prev === filter ? '' : filter));
    setPage(1);
  };

  const handleSortChange = (field: SortField) => {
    if (sortField === field) {
      setSortOrder((prev) => (prev === 'desc' ? 'asc' : 'desc'));
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
    setPage(1);
  };

  const handleView = (id: number) => {
    setSelectedId(id);
    setDrawerOpen(true);
  };

  const handleCopy = async (content: string) => {
    await navigator.clipboard.writeText(content);
    message.success('已复制到剪贴板');
  };

  const handleReuse = (item: HistoryItem) => {
    navigate(`/documents?input=${encodeURIComponent(item.input_text)}&doc_type=${encodeURIComponent(item.doc_type)}`);
  };

  const handleDownload = async (item: HistoryItem) => {
    try {
      const resp = await client.get(`/generation/history/${item.id}/export`, { responseType: 'blob' });
      const blob = resp.data instanceof Blob ? resp.data : new Blob([resp.data]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${item.doc_type || '文书'}_${item.id}.docx`;
      a.click();
      URL.revokeObjectURL(url);
      message.success('下载成功');
    } catch (err) {
      message.error(err instanceof Error ? err.message : '下载失败');
    }
  };

  const handleClearFilters = () => {
    setKeyword('');
    setDocType('');
    setActiveFilter('');
    setSortField('created_at');
    setSortOrder('desc');
    setPage(1);
  };

  // 服务端排序的列定义
  const sortableHeader = (label: string, field: SortField) => {
    const active = sortField === field;
    return (
      <button
        onClick={() => handleSortChange(field)}
        className="flex items-center gap-1 hover:text-police-600 transition-colors"
      >
        {label}
        <SortAscendingOutlined
          className={`text-[10px] transition-all ${
            active ? 'text-police-500' : 'text-slate-300'
          } ${active && sortOrder === 'asc' ? 'rotate-180' : ''}`}
        />
      </button>
    );
  };

  const columns: TableProps<HistoryItem>['columns'] = [
    {
      title: sortableHeader('ID', 'id'),
      dataIndex: 'id',
      width: 70,
      render: (id: number) => <span className="text-slate-400 text-xs">#{id}</span>,
    },
    {
      title: sortableHeader('文书类型', 'doc_type'),
      dataIndex: 'doc_type',
      width: 150,
      render: (t: string) => (
        <Tag color={
          t.includes('行政') ? 'blue' :
          t.includes('刑事') ? 'red' :
          t.includes('民事') ? 'green' : 'default'
        }>{t}</Tag>
      ),
    },
    {
      title: '输入摘要',
      dataIndex: 'input_text',
      ellipsis: true,
      render: (text: string, item) => (
        <div className="min-w-0">
          <div className="text-slate-700 text-sm truncate" title={formatCaseSummary(text)}>
            {formatCaseSummary(text)}
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5 truncate">
            {item.model_used || '未记录模型'}
          </div>
        </div>
      ),
    },
    {
      title: '状态',
      width: 80,
      render: (_, item) => (
        item.output_content
          ? <Tag color="success" className="m-0">成功</Tag>
          : <Tag color="warning" className="m-0">空内容</Tag>
      ),
    },
    {
      title: sortableHeader('生成时间', 'created_at'),
      dataIndex: 'created_at',
      width: 175,
      render: (t: string) => {
        if (!t) return '-';
        const d = new Date(t);
        return <span className="text-slate-500 text-sm">{d.toLocaleString('zh-CN')}</span>;
      },
    },
    {
      title: sortableHeader('耗时', 'latency_ms'),
      dataIndex: 'latency_ms',
      width: 90,
      render: (ms: number) => ms ? <span className="text-slate-400 text-xs">{ms}ms</span> : '-',
    },
    {
      title: '操作',
      width: 170,
      render: (_, item) => (
        <Space size={0}>
          <Button type="link" size="small" icon={<EyeOutlined />}
            onClick={() => handleView(item.id)}>查看</Button>
          <Tooltip title="下载 Word">
            <Button type="link" size="small" icon={<DownloadOutlined />}
              onClick={() => handleDownload(item)} />
          </Tooltip>
          <Tooltip title="复制内容">
            <Button type="link" size="small" icon={<CopyOutlined />}
              onClick={() => handleCopy(item.output_content)} />
          </Tooltip>
          <Tooltip title="带入文书生成页重新生成">
            <Button type="link" size="small" icon={<ReloadOutlined />}
              onClick={() => handleReuse(item)} />
          </Tooltip>
        </Space>
      ),
    },
  ];

  const hasFilters = keyword || docType || activeFilter || sortField !== 'created_at' || sortOrder !== 'desc';

  return (
    <div className="p-5 page-enter max-w-[1400px] mx-auto">
      <h2 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
        <ClockCircleOutlined className="text-police-500" />
        历史文书
      </h2>

      {/* 统计卡片 */}
      {statsLoading ? (
        <Row gutter={[16, 16]} className="mb-4">
          {[1, 2, 3].map((i) => (
            <Col xs={24} sm={8} key={i}><Card><Skeleton active paragraph={{ rows: 1 }} /></Card></Col>
          ))}
        </Row>
      ) : (
        <Row gutter={[16, 16]} className="mb-4">
          <Col xs={24} sm={8}>
            <Card
              className={`stat-card rounded-xl shadow-sm border-0 transition-all ${!hasFilters ? 'ring-2 ring-police-200' : 'cursor-pointer hover:shadow-md'}`}
              onClick={handleClearFilters}
            >
              <Statistic
                title={<span className="text-xs text-slate-500">历史文书总数</span>}
                value={stats.total}
                prefix={<FileTextOutlined className="text-police-500" />}
                valueStyle={{ fontSize: 28, fontWeight: 700, color: '#1a3a5c' }}
              />
            </Card>
          </Col>
          <Col xs={24} sm={8}>
            <Card
              className={`stat-card rounded-xl shadow-sm border-0 transition-all ${activeFilter === 'recent' ? 'ring-2 ring-blue-200' : 'cursor-pointer hover:shadow-md'}`}
              onClick={() => handleFilterClick('recent')}
            >
              <Statistic
                title={<span className="text-xs text-slate-500">近 7 天生成</span>}
                value={stats.recent}
                prefix={<ClockCircleOutlined className="text-blue-500" />}
                valueStyle={{ fontSize: 28, fontWeight: 700, color: '#1e4470' }}
              />
            </Card>
          </Col>
          <Col xs={24} sm={8}>
            <Card className="stat-card rounded-xl shadow-sm border-0 cursor-default">
              <Statistic
                title={<span className="text-xs text-slate-500">涵盖文书类型</span>}
                value={stats.types}
                prefix={<CheckCircleOutlined className="text-green-500" />}
                valueStyle={{ fontSize: 28, fontWeight: 700, color: '#2c5f2d' }}
              />
            </Card>
          </Col>
        </Row>
      )}

      {/* 搜索筛选栏 */}
      <Card className="rounded-xl shadow-sm border-0 mb-4" styles={{ body: { padding: '12px 16px' } }}>
        <div className="flex items-center gap-3 flex-wrap">
          <Input
            placeholder="搜索案情关键词..."
            prefix={<SearchOutlined className="text-slate-400" />}
            value={keyword}
            onChange={(e) => { setKeyword(e.target.value); setPage(1); }}
            className="w-56"
            size="small"
            allowClear
          />
          <Select
            placeholder="文书类型"
            value={docType || undefined}
            onChange={(v) => { setDocType(v || ''); setPage(1); }}
            className="w-40"
            size="small"
            allowClear
            options={DOC_TYPES.map((t) => ({ label: t, value: t }))}
          />
          {/* 活跃排序指示 */}
          {sortField !== 'created_at' && (
            <Tag color="purple" closable onClose={() => { setSortField('created_at'); setSortOrder('desc'); }}>
              排序: {sortField === 'doc_type' ? '文书类型' : sortField === 'latency_ms' ? '耗时' : 'ID'}
              ({sortOrder === 'asc' ? '升序' : '降序'})
            </Tag>
          )}
          {activeFilter === 'recent' && (
            <Tag color="blue" closable onClose={() => { setActiveFilter(''); setPage(1); }}>
              近7天
            </Tag>
          )}
          {hasFilters && (
            <Button size="small" icon={<ClearOutlined />} onClick={handleClearFilters}>重置</Button>
          )}
          <span className="text-xs text-slate-400 ml-auto">
            共 {total} 条记录
          </span>
        </div>
      </Card>

      {/* 列表 */}
      <Card className="rounded-xl shadow-sm border-0" styles={{ body: { padding: '0' } }}>
        <Table<HistoryItem>
          columns={columns}
          dataSource={items}
          rowKey="id"
          loading={loading}
          size="middle"
          showSorterTooltip={false}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: false,
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p) => setPage(p),
          }}
          locale={{ emptyText: <Empty description="暂无生成记录" /> }}
          onRow={(item) => ({
            style: { cursor: 'pointer' },
            onDoubleClick: () => handleView(item.id),
          })}
        />
      </Card>

      {/* 详情 Drawer */}
      <HistoryDrawer
        open={drawerOpen}
        historyId={selectedId}
        onClose={() => setDrawerOpen(false)}
        onCopy={handleCopy}
        onReuse={handleReuse}
      />
    </div>
  );
}

function formatCaseSummary(text: string): string {
  if (!text || !text.trim()) return '无案情输入';

  const raw = text.trim();
  try {
    const parsed = JSON.parse(raw);
    const flat = flattenObject(parsed);
    const time = pickValue(flat, ['案发时间', '时间', '发生时间']);
    const place = pickValue(flat, ['案发地点', '地点', '发生地点']);
    const person = pickValue(flat, ['违法嫌疑人', '当事人', '姓名']);
    const nature = pickValue(flat, ['案件性质', '案由', '违法性质']);
    const parts = [time, place, person, nature].filter(Boolean);
    if (parts.length > 0) return parts.join(' · ');
  } catch {
    // 非 JSON 输入继续按普通文本处理
  }

  const fuzzyTime = matchField(raw, ['案发时间', '发生时间']);
  const fuzzyPlace = matchField(raw, ['案发地点', '发生地点']);
  const fuzzyNature = matchField(raw, ['案件性质', '案由', '违法性质']);
  const fuzzyParts = [fuzzyTime, fuzzyPlace, fuzzyNature].filter(Boolean);
  if (fuzzyParts.length > 0) return fuzzyParts.join(' · ');

  const cleaned = raw
    .replace(/[{}[\]"'#*_`>-]/g, ' ')
    .replace(/\\n/g, ' ')
    .replace(/[：:]\s*/g, '：')
    .replace(/[,，]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  return cleaned.length > 90 ? `${cleaned.slice(0, 90)}...` : cleaned;
}

function flattenObject(value: unknown, result: Record<string, string> = {}): Record<string, string> {
  if (!value || typeof value !== 'object') return result;
  for (const [key, val] of Object.entries(value as Record<string, unknown>)) {
    if (val && typeof val === 'object' && !Array.isArray(val)) {
      flattenObject(val, result);
    } else if (val !== undefined && val !== null) {
      result[key] = Array.isArray(val) ? val.join('、') : String(val);
    }
  }
  return result;
}

function pickValue(source: Record<string, string>, names: string[]): string {
  for (const name of names) {
    if (source[name]) return source[name];
    const fuzzyKey = Object.keys(source).find((key) => key.includes(name));
    if (fuzzyKey && source[fuzzyKey]) return source[fuzzyKey];
  }
  return '';
}

function matchField(text: string, names: string[]): string {
  for (const name of names) {
    const pattern = new RegExp(`${name}["'：:\\s]*([^,，。\\n}"']{2,40})`);
    const match = text.match(pattern);
    if (match?.[1]) return `${name}：${match[1].trim()}`;
  }
  return '';
}
