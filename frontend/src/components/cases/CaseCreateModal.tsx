/** 创建案件模态框。 */
import { useState } from 'react';
import { Modal, Form, Input, Select, DatePicker, App } from 'antd';
import client from '../../api/client';

const { TextArea } = Input;

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}

export default function CaseCreateModal({ open, onClose, onCreated }: Props) {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);
      await client.post('/cases', {
        title: values.title,
        case_type: values.case_type || '刑事',
        description: values.description || '',
        unit: values.unit || '',
        incident_date: values.incident_date ? values.incident_date.format('YYYY-MM-DD') : null,
        location: values.location || '',
      });
      message.success('案件创建成功');
      form.resetFields();
      onCreated();
    } catch (err: any) {
      if (err?.errorFields) return; // 表单验证失败
      message.error(err?.message || '创建失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      title="新建案件"
      open={open}
      onOk={handleOk}
      onCancel={onClose}
      confirmLoading={loading}
      destroyOnClose
      width={560}
    >
      <Form form={form} layout="vertical" className="mt-4">
        <Form.Item name="title" label="案件名称" rules={[{ required: true, message: '请输入案件名称' }]}>
          <Input placeholder="如: 张三涉嫌盗窃案" maxLength={256} />
        </Form.Item>
        <Form.Item name="case_type" label="案件类型" initialValue="刑事">
          <Select options={[
            { label: '刑事', value: '刑事' },
            { label: '行政', value: '行政' },
            { label: '民事', value: '民事' },
          ]} />
        </Form.Item>
        <Form.Item name="unit" label="办案单位">
          <Input placeholder="如: XX派出所" maxLength={128} />
        </Form.Item>
        <Form.Item name="incident_date" label="案发日期">
          <DatePicker className="w-full" />
        </Form.Item>
        <Form.Item name="location" label="案发地点">
          <Input placeholder="如: XX市XX路XX号" maxLength={256} />
        </Form.Item>
        <Form.Item name="description" label="案件描述">
          <TextArea rows={4} placeholder="简要描述案件事实..." maxLength={10000} showCount />
        </Form.Item>
      </Form>
    </Modal>
  );
}
