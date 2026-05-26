import { useState, useEffect } from 'react';
import { Modal, Form, Select, Input, Button, Space, App, Alert } from 'antd';
import { ApiOutlined, CheckCircleOutlined } from '@ant-design/icons';
import client from '../api/client';
import { PROVIDER_PRESETS } from '../constants/providers';
import type { ModelProvider, ModelTestResult } from '../types';

interface Props {
  open: boolean;
  onClose: () => void;
  models: ModelProvider[];
  onSaved: () => void;
}

export default function ModelSettings({ open, onClose, models, onSaved }: Props) {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState<ModelTestResult | null>(null);
  const watchedApiType = Form.useWatch('api_type', form);

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
        api_type: model.api_type || 'openai',
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
        api_type: preset.api_type || 'openai',
      });
    } else {
      form.setFieldsValue({ edit_id: '', api_type: 'openai' });
    }
    setTestResult(null);
  };

  const handleTest = async () => {
    const values = form.getFieldsValue();
    const isDify = values.api_type === 'dify';
    if (!values.base_url || (!isDify && !values.model_name)) {
      message.warning(isDify ? '请先填写 Dify API 地址' : '请先填写 API 地址和模型名称');
      return;
    }
    setTesting(true);
    setTestResult(null);
    try {
      const { data } = await client.post<ModelTestResult>('/models/test', {
        base_url: values.base_url,
        api_key: values.api_key || '',
        model_name: values.model_name,
        api_type: values.api_type || 'openai',
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
        api_type: values.api_type || 'openai',
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
      form.setFieldsValue({ api_type: 'openai' });
    }
  }, [open, form]);

  return (
    <Modal
      title="模型配置"
      open={open}
      onCancel={onClose}
      footer={null}
      width={520}
      destroyOnHidden
      forceRender
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
              { label: 'Dify', value: 'Dify' },
              { label: '自定义', value: '自定义' },
            ]}
          />
        </Form.Item>

        <Form.Item
          label="协议类型"
          name="api_type"
          rules={[{ required: true, message: '请选择协议类型' }]}
          initialValue="openai"
        >
          <Select
            placeholder="选择 API 协议"
            options={[
              { label: 'OpenAI 兼容', value: 'openai' },
              { label: 'Anthropic', value: 'anthropic' },
              { label: 'Dify 工作流', value: 'dify' },
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
          rules={[
            ({ getFieldValue }) => ({
              required: getFieldValue('api_type') !== 'dify',
              message: '请输入模型名称',
            }),
          ]}
        >
          <Input placeholder={watchedApiType === 'dify' ? 'Dify 工作流无需填写' : 'model-name'} />
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
