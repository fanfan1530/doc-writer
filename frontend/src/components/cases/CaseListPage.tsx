/** 案件列表页 —— 表格 + 筛选 + 搜索 + 创建。 */
import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Table, Select, Input, Button, Tag, App, Card, Typography, Space, Modal } from 'antd';
import { PlusOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons';
import client from '../../api/client';
import CaseStatusBadge from './CaseStatusBadge';
import CaseCreateModal from './CaseCreateModal';
import type { DBCase } from '../../types';

const { Title, Text } = Typography;

interface StatusOption {
  key: string;
  label: string;
}

export default function CaseListPage() {
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [cases, setCases] = useState<DBCase[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [statuses, setStatuses] = useState<StatusOption[]>([]);
  const [filterStatus, setFilterStatus] = useState<string | undefined>();
  const [filterType, setFilterType] = useState<string | undefined>();
  const [keyword, setKeyword] = useState('');
  const [createOpen, setCreateOpen] = useState(false);

  const fetchCases = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { limit: 20, offset: (page - 1) * 20 };
      if (filterStatus) params.status = filterStatus;
      if (filterType) params.case_type = filterType;
      if (keyword) params.keyword = keyword;

      const { data } = await client.get('/cases', { params });
      setCases(data.cases || []);
      setTotal(data.total || 0);
      setStatuses(data.statuses || []);
    } catch {
      message.error('获取案件列表失败');
    } finally {
      setLoading(false);
    }
  }, [page, filterStatus, filterType, keyword, message]);

  useEffect(() => {
    fetchCases();
  }, [fetchCases]);

  const columns = [
    {
      title: '案件编号',
      dataIndex: 'case_number',
      key: 'case_number',
      width: 140,
      render: (text: string) => <Text code>{text}</Text>,
    },
    {
      title: '案件名称',
      dataIndex: 'title',
      key: 'title',
      width: 200,
      render: (text: string, record: DBCase) => (
        <a onClick={() => navigate(`/cases/${record.id}`)} className="font-medium text-police-700 hover:text-police-500">
          {text}
        </a>
      ),
    },
    {
      title: '类型',
      dataIndex: 'case_type',
      key: 'case_type',
      width: 80,
      render: (t: string) => <Tag>{t}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (s: string) => <CaseStatusBadge status={s} />,
    },
    {
      title: '单位',
      dataIndex: 'unit',
      key: 'unit',
      width: 120,
      render: (text: string) => text || '-',
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 160,
      render: (text: string) => text ? new Date(text).toLocaleString('zh-CN') : '-',
    },
  ];

  return (
    <div className="p-6 h-full overflow-auto">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Title level={4} className="!mb-0">案件管理</Title>
            <Text className="text-slate-400 text-sm">共 {total} 个案件</Text>
          </div>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={fetchCases}>刷新</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
              新建案件
            </Button>
          </Space>
        </div>

        <div className="flex items-center gap-3 mb-4">
          <Input
            size="small"
            placeholder="搜索案件名称或描述"
            value={keyword}
            onChange={(e) => { setKeyword(e.target.value); setPage(1); }}
            className="w-56"
            prefix={<SearchOutlined />}
            allowClear
          />
          <Select
            size="small"
            placeholder="状态筛选"
            value={filterStatus}
            onChange={(v) => { setFilterStatus(v); setPage(1); }}
            allowClear
            className="w-28"
            options={statuses.map((s) => ({ label: s.label, value: s.key }))}
          />
          <Select
            size="small"
            placeholder="案件类型"
            value={filterType}
            onChange={(v) => { setFilterType(v); setPage(1); }}
            allowClear
            className="w-28"
            options={[
              { label: '刑事', value: '刑事' },
              { label: '行政', value: '行政' },
              { label: '民事', value: '民事' },
            ]}
          />
        </div>

        <Card className="border-0 shadow-sm">
          <Table
            columns={columns}
            dataSource={cases}
            rowKey="id"
            loading={loading}
            pagination={{
              current: page,
              total,
              pageSize: 20,
              onChange: setPage,
              showTotal: (t) => `共 ${t} 个案件`,
            }}
            size="middle"
            scroll={{ x: 900 }}
          />
        </Card>

        <CaseCreateModal
          open={createOpen}
          onClose={() => setCreateOpen(false)}
          onCreated={() => { setCreateOpen(false); fetchCases(); }}
        />
      </div>
    </div>
  );
}
