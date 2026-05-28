/** 用户管理页面 —— 用户列表 + 角色分配 + 启用/禁用。 */
import { useEffect, useState, useCallback } from 'react';
import { Table, Select, Button, Tag, Popconfirm, App, Card, Typography, Space } from 'antd';
import { ReloadOutlined, UserOutlined } from '@ant-design/icons';
import client from '../../api/client';

const { Title, Text } = Typography;

interface UserItem {
  id: number;
  username: string;
  display_name: string;
  unit: string;
  role: string;
  role_label: string;
  permissions: string[];
  is_active: boolean;
  created_at: string;
}

interface RoleOption {
  key: string;
  label: string;
}

export default function UserManagementPage() {
  const { message } = App.useApp();
  const [users, setUsers] = useState<UserItem[]>([]);
  const [roles, setRoles] = useState<RoleOption[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await client.get('/admin/users', {
        params: { limit: 30, offset: (page - 1) * 30 },
      });
      setUsers(data.users || []);
      setRoles(data.roles || []);
      setTotal(data.total || 0);
    } catch {
      message.error('获取用户列表失败');
    } finally {
      setLoading(false);
    }
  }, [page, message]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleRoleChange = async (userId: number, newRole: string) => {
    try {
      await client.put(`/admin/users/${userId}`, { role: newRole, display_name: '', unit: '' });
      message.success('角色更新成功');
      fetchUsers();
    } catch {
      message.error('角色更新失败');
    }
  };

  const handleToggleStatus = async (userId: number, isActive: boolean) => {
    try {
      await client.put(`/admin/users/${userId}/status`, { is_active: isActive });
      message.success(isActive ? '用户已启用' : '用户已禁用');
      fetchUsers();
    } catch {
      message.error('操作失败');
    }
  };

  const columns = [
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
      width: 120,
      render: (text: string, record: UserItem) => (
        <div>
          <div className="font-medium text-slate-800">{record.display_name || text}</div>
          <div className="text-xs text-slate-400">@{text}</div>
        </div>
      ),
    },
    {
      title: '单位',
      dataIndex: 'unit',
      key: 'unit',
      width: 120,
      render: (text: string) => text || <span className="text-slate-300">-</span>,
    },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      width: 180,
      render: (role: string, record: UserItem) => (
        <Select
          size="small"
          value={role}
          onChange={(v) => handleRoleChange(record.id, v)}
          className="w-32"
          options={roles.map((r) => ({ label: r.label, value: r.key }))}
        />
      ),
    },
    {
      title: '权限数',
      dataIndex: 'permissions',
      key: 'permissions',
      width: 80,
      render: (perms: string[]) => (
        <Tag color="blue">{perms.length}</Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 80,
      render: (active: boolean) => (
        <Tag color={active ? 'green' : 'red'}>{active ? '正常' : '禁用'}</Tag>
      ),
    },
    {
      title: '注册时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (text: string) => text ? new Date(text).toLocaleString('zh-CN') : '-',
    },
    {
      title: '操作',
      key: 'actions',
      width: 80,
      render: (_: unknown, record: UserItem) => (
        <Popconfirm
          title={record.is_active ? '确认禁用该用户？' : '确认启用该用户？'}
          onConfirm={() => handleToggleStatus(record.id, !record.is_active)}
        >
          <Button size="small" type="link" danger={record.is_active}>
            {record.is_active ? '禁用' : '启用'}
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div className="p-6 h-full overflow-auto">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <UserOutlined className="text-police-500 text-lg" />
            <Title level={4} className="!mb-0">用户管理</Title>
            <Text className="text-slate-400 text-sm">共 {total} 个用户</Text>
          </div>
          <Button icon={<ReloadOutlined />} onClick={fetchUsers}>刷新</Button>
        </div>

        <Card className="border-0 shadow-sm">
          <Table
            columns={columns}
            dataSource={users}
            rowKey="id"
            loading={loading}
            pagination={{
              current: page,
              total,
              pageSize: 30,
              onChange: setPage,
              showTotal: (t) => `共 ${t} 个用户`,
            }}
            size="middle"
            scroll={{ x: 900 }}
          />
        </Card>
      </div>
    </div>
  );
}
