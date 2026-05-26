/** 表单字段渲染组件 — 根据字段类型渲染对应的表单控件。 */

import { Form, Input, InputNumber, Select, DatePicker } from 'antd';
import type { FieldSchema } from '../../types';
import { TEXTAREA_FIELD_KEYS } from '../../constants/docTypes';

interface Props {
  field: FieldSchema;
}

export default function FieldFormItem({ field }: Props) {
  const commonProps = {
    style: { width: '100%' as const },
    placeholder: `请输入${field.label}${field.required ? '（必填）' : ''}`,
  };

  const rules = field.required
    ? [{ required: true, message: `请输入${field.label}` }]
    : [];

  switch (field.type) {
    case 'date':
      return (
        <Form.Item key={field.key} name={field.key} label={field.label} rules={rules}>
          <DatePicker {...commonProps} placeholder={`选择${field.label}`} />
        </Form.Item>
      );
    case 'datetime':
      return (
        <Form.Item key={field.key} name={field.key} label={field.label} rules={rules}>
          <DatePicker showTime format="YYYY-MM-DD HH:mm:ss" {...commonProps} placeholder={`选择${field.label}`} />
        </Form.Item>
      );
    case 'number':
      return (
        <Form.Item key={field.key} name={field.key} label={field.label} rules={rules}>
          <InputNumber {...commonProps} style={{ width: '100%' }} />
        </Form.Item>
      );
    case 'dict':
      if (field.dict_values?.length) {
        return (
          <Form.Item key={field.key} name={field.key} label={field.label} rules={rules}>
            <Select {...commonProps} placeholder={`选择${field.label}`} allowClear
              options={field.dict_values.map((v) => ({ label: v, value: v }))} />
          </Form.Item>
        );
      }
      return (
        <Form.Item key={field.key} name={field.key} label={field.label} rules={rules}>
          <Input {...commonProps} />
        </Form.Item>
      );
    case 'text':
    default: {
      const isTextarea = TEXTAREA_FIELD_KEYS.includes(field.key);
      return (
        <Form.Item key={field.key} name={field.key} label={field.label} rules={rules}>
          {isTextarea
            ? <Input.TextArea rows={3} {...commonProps} />
            : <Input {...commonProps} />
          }
        </Form.Item>
      );
    }
  }
}
