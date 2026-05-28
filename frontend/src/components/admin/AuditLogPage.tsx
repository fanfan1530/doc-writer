/** 审计日志页面 —— 操作记录时间线 + 筛选。 */
import { useEffect, useState, useCallback } from 'react';
import { Table, Select, Input, Card, Typography, Tag, App, Button, Space } from 'antd';
import { ReloadOutlined, AuditOutlined, SearchOutlined } from '@ant-design/icons';
import client from '../../api/client';

const { Title, Text } = Typography;

interface AuditLogItem {
  id: number;
  user_id: number;
  username: string;
  action: string;
  resource_type: string;
  resource_id: string;
  detail: Record<string, unknown>;
  ip_address: string;
  created_at: string;
}

const ACTION_LABELS: Record<string, { label: string; color: string }> = {
  user_update: { label: '更新用户', color: 'blue' },
  user_enable: { label: '启用用户', color: 'green' },
  user_disable: { label: '禁用用户', color: 'red' },
  role_change: { label: '角色变更', color: 'orange' },
};

export default function AuditLogPage() {
  const { message } = App.useApp();
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [filterAction, setFilterAction] = useState<string | undefined>();
  const [filterUser, setFilterUser] = useState('');

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = {
        limit: 30,
        offset: (page - 1) * 30,
      };
      if (filterAction) params.action = filterAction;
      if (filterUser) params.user_id = Number(filterUser) || undefined;

      const { data } = await client.get('/admin/audit', { params });
      setLogs(data.logs || []);
      setTotal(data.total || 0);
    } catch {
      message.error('获取审计日志失败');
    } finally {
      setLoading(false);
    }
  }, [page, filterAction, filterUser, message]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const getActionTag = (action: string) => {
    const info = ACTION_LABELS[action];
    if (info) return <Tag color={info.color}>{info.label}</Tag>;
    return <Tag>{action}</Tag>;
  };

  const columns = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (text: string) => text ? new Date(text).toLocaleString('zh-CN') : '-',
    },
    {
      title: '操作用户',
      dataIndex: 'username',
      key: 'username',
      width: 120,
    },
    {
      title: '操作',
      dataIndex: 'action',
      key: 'action',
      width: 100,
      render: (action: string) => getActionTag(action),
    },
    {
      title: '资源类型',
      dataIndex: 'resource_type',
      key: 'resource_type',
      width: 100,
    },
    {
      title: '资源ID',
      dataIndex: 'resource_id',
      key: 'resource_id',
      width: 80,
    },
    {
      title: '详情',
      dataIndex: 'detail',
      key: 'detail',
      width: 200,
      render: (detail: Record<string, unknown>) => (
        <Text code className="text-xs" style={{ maxWidth: 200, display: 'inline-block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {JSON.stringify(detail)}
        </Text>
      ),
    },
    {
      title: 'IP',
      dataIndex: 'ip_address',
      key: 'ip_address',
      width: 120,
    },
  ];

  return (
    <div className="p-6 h-full overflow-auto">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <AuditOutlined className="text-police-500 text-lg" />
            <Title level={4} className="!mb-0">审计日志</Title>
            <Text className="text-slate-400 text-sm">共 {total} 条记录</Text>
          </div>
          <Space>
            <Input
              size="small"
              placeholder="用户ID"
              value={filterUser}
              onChange={(e) => { setFilterUser(e.target.value); setPage(1); }}
              className="w-24"
              prefix={<SearchOutlined />}
            />
            <Select
              size="small"
              placeholder="操作类型"
              value={filterAction}
              onChange={(v) => { setFilterAction(v); setPage(1); }}
              allowClear
              className="w-32"
              options={Object.entries(ACTION_LABELS).map(([key, val]) => ({
                label: val.label, value: key,
              }))}
            />
            <Button icon={<ReloadOutlined />} onClick={fetchLogs} size="small">刷新</Button>
          </Space>
        </div>

        <Card className="border-0 shadow-sm">
          <Table
            columns={columns}
            dataSource={logs}
            rowKey="id"
            loading={loading}
            pagination={{
              current: page,
              total,
              pageSize: 30,
              onChange: setPage,
              showTotal: (t) => `共 ${t} 条`,
            }}
            size="middle"
            scroll={{ x: 1000 }}
          />
        </Card>
      </div>
    </div>
  );
}
