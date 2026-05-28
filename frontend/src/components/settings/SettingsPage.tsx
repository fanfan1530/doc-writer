/** 设置页面 —— 模型配置管理 + 系统信息 */
import { useState, useEffect, useCallback } from 'react';
import {
  Card, Table, Button, Tag, App, Popconfirm, Space, Descriptions,
} from 'antd';
import {
  SettingOutlined, PlusOutlined, CheckCircleOutlined,
  ApiOutlined, DatabaseOutlined, RobotOutlined, EditOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import client from '../../api/client';
import ModelSettings from '../ModelSettings';
import type { ModelProvider } from '../../types';

export default function SettingsPage() {
  const { message } = App.useApp();
  const [models, setModels] = useState<ModelProvider[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [switchingId, setSwitchingId] = useState<string | null>(null);

  const fetchModels = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await client.get<{ models: ModelProvider[] }>('/models/list');
      setModels(data.models || []);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  const handleSwitch = async (id: string) => {
    setSwitchingId(id);
    try {
      await client.post('/models/switch', { model_id: id });
      message.success('模型已切换');
      fetchModels();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '切换失败');
    } finally {
      setSwitchingId(null);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await client.post('/models/delete', { model_id: id });
      message.success('模型已删除');
      fetchModels();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '删除失败');
    }
  };

  const handleTestConnection = async (model: ModelProvider) => {
    const hide = message.loading('正在测试连接...', 0);
    try {
      const { data } = await client.post('/models/test-by-id', {
        model_id: model.id,
      });
      hide();
      if (data.success) {
        message.success(data.message);
      } else {
        message.warning(data.message);
      }
    } catch (err) {
      hide();
      message.error(err instanceof Error ? err.message : '测试请求失败');
    }
  };

  const columns: ColumnsType<ModelProvider> = [
    {
      title: '模型名称',
      dataIndex: 'name',
      key: 'name',
      width: 180,
      render: (text: string, record: ModelProvider) => (
        <Space>
          <RobotOutlined className="text-police-500" />
          <span className="font-medium">{text}</span>
          {record.is_active && (
            <Tag color="green" className="ml-1 text-[11px]">当前</Tag>
          )}
        </Space>
      ),
    },
    {
      title: '提供商',
      dataIndex: 'provider',
      key: 'provider',
      width: 100,
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: '协议',
      dataIndex: 'api_type',
      key: 'api_type',
      width: 90,
      render: (v: string) => (
        <Tag color={v === 'openai' ? 'blue' : v === 'dify' ? 'purple' : 'orange'}>
          {v === 'openai' ? 'OpenAI' : v === 'dify' ? 'Dify' : v || 'OpenAI'}
        </Tag>
      ),
    },
    {
      title: 'API 地址',
      dataIndex: 'base_url',
      key: 'base_url',
      ellipsis: true,
      width: 280,
    },
    {
      title: '模型标识',
      dataIndex: 'model_name',
      key: 'model_name',
      width: 180,
      ellipsis: true,
    },
    {
      title: '操作',
      key: 'actions',
      width: 250,
      render: (_: unknown, record: ModelProvider) => (
        <Space size="small">
          {!record.is_active && (
            <Button
              size="small"
              type="primary"
              ghost
              loading={switchingId === record.id}
              onClick={() => handleSwitch(record.id)}
            >
              切换
            </Button>
          )}
          {record.is_active && (
            <Tag color="success" icon={<CheckCircleOutlined />} className="text-[11px]">
              使用中
            </Tag>
          )}
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => {
              // 用临时变量触发 modal 打开并回填数据
              setSelectedModel(record);
              setModalOpen(true);
            }}
          >
            编辑
          </Button>
          <Button
            size="small"
            icon={<ApiOutlined />}
            onClick={() => handleTestConnection(record)}
          >
            测试
          </Button>
          <Popconfirm
            title="确认删除此模型?"
            description={record.is_active ? '当前正在使用，删除后将自动切换到其他模型' : undefined}
            onConfirm={() => handleDelete(record.id)}
            okText="确认"
            cancelText="取消"
          >
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              disabled={models.length <= 1}
            />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const [selectedModel, setSelectedModel] = useState<ModelProvider | null>(null);

  return (
    <div className="p-5 page-enter max-w-[1200px] mx-auto">
      <h2 className="text-lg font-bold text-slate-800 mb-5 flex items-center gap-2">
        <SettingOutlined className="text-slate-500" />
        系统设置
      </h2>

      <Card
        title={
          <span className="text-sm font-semibold flex items-center gap-2">
            <RobotOutlined className="text-police-500" />
            模型配置
          </span>
        }
        extra={
          <Button
            type="primary"
            size="small"
            icon={<PlusOutlined />}
            onClick={() => {
              setSelectedModel(null);
              setModalOpen(true);
            }}
          >
            新增模型
          </Button>
        }
        className="rounded-xl shadow-sm border-0 mb-4"
      >
        <Table
          columns={columns}
          dataSource={models}
          rowKey="id"
          loading={loading}
          size="middle"
          pagination={false}
          scroll={{ x: 1080 }}
          locale={{ emptyText: '暂无模型配置，请点击"新增模型"添加' }}
        />
      </Card>

      <Card
        title={<span className="text-sm font-semibold">系统信息</span>}
        className="rounded-xl shadow-sm border-0"
      >
        <Descriptions size="small" column={2} labelStyle={{ color: '#64748b', fontSize: 13 }}>
          <Descriptions.Item label={<span><ApiOutlined className="mr-1" />应用名称</span>}>
            智慧警务智能工作台
          </Descriptions.Item>
          <Descriptions.Item label="版本">v2.0.0</Descriptions.Item>
          <Descriptions.Item label={<span><DatabaseOutlined className="mr-1" />数据存储</span>}>
            SQLite + ChromaDB
          </Descriptions.Item>
          <Descriptions.Item label="框架">FastAPI + React 18</Descriptions.Item>
          <Descriptions.Item label="LLM 协议">OpenAI 兼容 (支持 DeepSeek / 通义千问 / 自定义)</Descriptions.Item>
          <Descriptions.Item label="部署方式">Docker Compose / 单机直启</Descriptions.Item>
        </Descriptions>
      </Card>

      <ModelSettings
        open={modalOpen}
        onClose={() => {
          setModalOpen(false);
          setSelectedModel(null);
        }}
        models={models}
        editModel={selectedModel}
        onSaved={() => {
          setModalOpen(false);
          setSelectedModel(null);
          fetchModels();
        }}
      />
    </div>
  );
}
