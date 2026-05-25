import { useState, useEffect } from 'react';
import { Modal, Form, Select, Input, Button, Space, App, Alert } from 'antd';
import { ApiOutlined, CheckCircleOutlined } from '@ant-design/icons';
import client from '../api/client';
import type { ModelProvider, ModelTestResult } from '../types';

interface Props {
  open: boolean;
  onClose: () => void;
  models: ModelProvider[];
  onSaved: () => void;
}

const PROVIDER_PRESETS: Record<string, { base_url: string; model_name: string; model_name_large: string }> = {
  'DeepSeek': {
    base_url: 'https://api.deepseek.com/v1',
    model_name: 'deepseek-v4-pro',
    model_name_large: 'deepseek-v4-pro',
  },
  'MiniMax': {
    base_url: 'https://api.minimax.chat/v1',
    model_name: 'MiniMax-M2.7',
    model_name_large: 'MiniMax-M2.7',
  },
};

export default function ModelSettings({ open, onClose, models, onSaved }: Props) {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState<ModelTestResult | null>(null);

  const handleModelSelect = (modelId: string) => {
    const model = models.find((m) => m.id === modelId);
    if (model) {
      form.setFieldsValue({
        edit_id: model.id,
        name: model.name,
        provider: model.provider,
        base_url: model.base_url,
        model_name: model.model_name,
        model_name_large: model.model_name_large || '',
        api_key: '',
      });
      setTestResult(null);
    }
  };

  const handleProviderChange = (provider: string) => {
    const preset = PROVIDER_PRESETS[provider];
    if (preset) {
      form.setFieldsValue({
        base_url: preset.base_url,
        model_name: preset.model_name,
        model_name_large: preset.model_name_large,
      });
    } else {
      form.setFieldsValue({ edit_id: '' });
    }
    setTestResult(null);
  };

  const handleTest = async () => {
    const values = form.getFieldsValue();
    if (!values.base_url || !values.model_name) {
      message.warning('请先填写 API 地址和模型名称');
      return;
    }
    setTesting(true);
    setTestResult(null);
    try {
      const { data } = await client.post<ModelTestResult>('/models/test', {
        base_url: values.base_url,
        api_key: values.api_key || '',
        model_name: values.model_name,
      });
      setTestResult(data);
      if (data.success) {
        message.success(data.message);
      } else {
        message.warning(data.message);
      }
    } catch {
      setTestResult({ success: false, message: '测试请求失败' });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      const { data } = await client.post('/models/config', {
        id: values.edit_id || '',
        name: values.name,
        provider: values.provider || '自定义',
        base_url: values.base_url,
        model_name: values.model_name,
        model_name_large: values.model_name_large || '',
        api_key: values.api_key || '',
      });
      const action = data.is_new ? '添加' : '更新';
      message.success(`模型${action}成功`);
      form.resetFields();
      setTestResult(null);
      onSaved();
      onClose();
    } catch (err) {
      console.error('保存模型配置失败:', err);
      message.error(`保存失败: ${err instanceof Error ? err.message : '未知错误'}`);
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    if (!open) {
      setTestResult(null);
      form.resetFields();
    }
  }, [open, form]);

  return (
    <Modal
      title="模型配置"
      open={open}
      onCancel={onClose}
      footer={null}
      width={520}
      destroyOnClose
    >
      <Form form={form} layout="vertical" size="middle">
        <Form.Item label="选择已有模型" name="edit_id">
          <Select
            placeholder="选择一个已有模型进行编辑，或留空新增"
            allowClear
            onChange={(val) => val && handleModelSelect(val)}
            options={(Array.isArray(models) ? models : []).filter((m) => m.id !== 'custom')
              .map((m) => ({
                label: `${m.name}${m.is_active ? ' (当前)' : ''}`,
                value: m.id,
              }))}
          />
        </Form.Item>

        <Form.Item
          label="厂商"
          name="provider"
          rules={[{ required: true, message: '请选择厂商' }]}
        >
          <Select
            placeholder="选择模型厂商"
            onChange={handleProviderChange}
            options={[
              { label: 'DeepSeek', value: 'DeepSeek' },
              { label: 'MiniMax', value: 'MiniMax' },
              { label: '自定义', value: '自定义' },
            ]}
          />
        </Form.Item>

        <Form.Item
          label="API 地址"
          name="base_url"
          rules={[{ required: true, message: '请输入 API 地址' }]}
        >
          <Input placeholder="https://api.example.com/v1" />
        </Form.Item>

        <Form.Item
          label="模型名称"
          name="model_name"
          rules={[{ required: true, message: '请输入模型名称' }]}
        >
          <Input placeholder="model-name" />
        </Form.Item>

        <Form.Item label="大模型名称（可选）" name="model_name_large">
          <Input placeholder="留空则使用上述模型名" />
        </Form.Item>

        <Form.Item
          label="显示名称"
          name="name"
          rules={[{ required: true, message: '请输入显示名称' }]}
        >
          <Input placeholder="例如：我的 DeepSeek" />
        </Form.Item>

        <Form.Item label="API Key" name="api_key">
          <Input.Password placeholder="输入 API Key" />
        </Form.Item>

        {testResult && (
          <Alert
            type={testResult.success ? 'success' : 'error'}
            message={testResult.message}
            showIcon
            icon={testResult.success ? <CheckCircleOutlined /> : undefined}
            style={{ marginBottom: 16 }}
          />
        )}

        <div className="flex justify-end gap-2">
          <Button onClick={handleTest} loading={testing} icon={<ApiOutlined />}>
            测试连接
          </Button>
          <Button type="primary" onClick={handleSave} loading={saving}>
            保存配置
          </Button>
        </div>
      </Form>
    </Modal>
  );
}
