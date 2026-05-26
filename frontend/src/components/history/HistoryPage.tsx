/** 历史文书页面 —— 浏览、搜索、查看过往生成的所有文书 */
import { useEffect, useState, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Card, Table, Tag, Input, Select, Button, Statistic, Row, Col,
  Skeleton, Empty, App,
} from 'antd';
import {
  FileTextOutlined, ClockCircleOutlined, CheckCircleOutlined,
  SearchOutlined, EyeOutlined, CopyOutlined, ExportOutlined,
  ReloadOutlined, ClearOutlined, DownloadOutlined,
} from '@ant-design/icons';
import client from '../../api/client';
import { DOC_TYPES } from '../../constants/docTypes';
import HistoryDrawer from './HistoryDrawer';
import type { ColumnsType } from 'antd/es/table';

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

export default function HistoryPage() {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [items, setItems] = useState<HistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ total: 0, recent: 0, types: 0 });
  const [statsLoading, setStatsLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  // 筛选状态 —— 从 URL 参数初始化
  const [keyword, setKeyword] = useState(searchParams.get('keyword') || '');
  const [docType, setDocType] = useState(searchParams.get('doc_type') || '');
  const [activeFilter, setActiveFilter] = useState(searchParams.get('filter') || '');
  const [page, setPage] = useState(Number(searchParams.get('page')) || 1);
  const pageSize = 15;

  const fetchHistory = useCallback(async (p: number, kw: string, dt: string, filter: string) => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = {
        limit: pageSize,
        offset: (p - 1) * pageSize,
      };
      if (kw) params.keyword = kw;
      if (dt) params.doc_type = dt;

      // 根据 filter 构造时间范围
      if (filter === 'recent') {
        const d = new Date(Date.now() - 7 * 24 * 3600 * 1000);
        params.since = d.toISOString();
      }

      const { data } = await client.get('/generation/history', { params });
      setItems(data.history || []);
      setTotal(data.total || 0);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const { data } = await client.get('/generation/history', { params: { limit: 200 } });
      const all: HistoryItem[] = data.history || [];
      const types = new Set(all.map((h) => h.doc_type));
      setStats({
        total: data.total || all.length,
        recent: all.filter((h) => {
          const d = new Date(h.created_at);
          return (Date.now() - d.getTime()) < 7 * 24 * 3600 * 1000;
        }).length,
        types: types.size,
      });
    } catch { /* ignore */ } finally {
      setStatsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  useEffect(() => {
    fetchHistory(page, keyword, docType, activeFilter);
  }, [page, keyword, docType, activeFilter, fetchHistory]);

  // 同步筛选到 URL
  useEffect(() => {
    const params: Record<string, string> = {};
    if (activeFilter) params.filter = activeFilter;
    if (docType) params.doc_type = docType;
    if (keyword) params.keyword = keyword;
    if (page > 1) params.page = String(page);
    setSearchParams(params, { replace: true });
  }, [activeFilter, docType, keyword, page, setSearchParams]);

  const handleFilterClick = (filter: string) => {
    setActiveFilter((prev) => (prev === filter ? '' : filter));
    setPage(1);
  };

  const handleView = async (id: number) => {
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
    } catch {
      message.error('下载失败');
    }
  };

  const handleClearFilters = () => {
    setKeyword('');
    setDocType('');
    setActiveFilter('');
    setPage(1);
  };

  const columns: ColumnsType<HistoryItem> = [
    {
      title: 'ID',
      dataIndex: 'id',
      width: 60,
      render: (id: number) => <span className="text-slate-400 text-xs">#{id}</span>,
    },
    {
      title: '文书类型',
      dataIndex: 'doc_type',
      width: 140,
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
      render: (text: string) => (
        <span className="text-slate-600 text-sm">{text || <span className="text-slate-300">无输入</span>}</span>
      ),
    },
    {
      title: '生成时间',
      dataIndex: 'created_at',
      width: 170,
      render: (t: string) => {
        if (!t) return '-';
        const d = new Date(t);
        return <span className="text-slate-500 text-sm">{d.toLocaleString('zh-CN')}</span>;
      },
      defaultSortOrder: 'descend',
      sorter: (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    },
    {
      title: '耗时',
      dataIndex: 'latency_ms',
      width: 80,
      render: (ms: number) => ms ? <span className="text-slate-400 text-xs">{ms}ms</span> : '-',
    },
    {
      title: '操作',
      width: 200,
      render: (_, item) => (
        <div className="flex gap-1">
          <Button type="link" size="small" icon={<EyeOutlined />}
            onClick={() => handleView(item.id)}>查看</Button>
          <Button type="link" size="small" icon={<DownloadOutlined />}
            onClick={() => handleDownload(item)} title="下载 Word" />
          <Button type="link" size="small" icon={<CopyOutlined />}
            onClick={() => handleCopy(item.output_content)} title="复制内容" />
          <Button type="link" size="small" icon={<ReloadOutlined />}
            onClick={() => handleReuse(item)} title="基于该案由重新生成" />
        </div>
      ),
    },
  ];

  const hasFilters = keyword || docType || activeFilter;

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
              className={`stat-card rounded-xl shadow-sm border-0 transition-all ${activeFilter === '' && !docType ? 'ring-2 ring-police-200' : 'cursor-pointer hover:shadow-md'}`}
              onClick={() => { setActiveFilter(''); setDocType(''); setKeyword(''); setPage(1); }}
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
            <Card
              className="stat-card rounded-xl shadow-sm border-0 cursor-pointer hover:shadow-md transition-all"
            >
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
          {hasFilters && (
            <Button size="small" icon={<ClearOutlined />} onClick={handleClearFilters}>清除筛选</Button>
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
