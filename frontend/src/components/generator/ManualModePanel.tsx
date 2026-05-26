/** 手动模式面板 — 动态表单 + AI 填充生成。 */

import { Button, Form, Alert } from 'antd';
import { FormOutlined, InfoCircleOutlined } from '@ant-design/icons';
import type { FieldSchema } from '../../types';
import { FIELD_GUIDE } from '../../constants/docTypes';
import FieldFormItem from './FieldFormItem';
import LoadingIndicator from './LoadingIndicator';

interface Props {
  docType: string;
  fieldSchema: FieldSchema[];
  schemaLoading: boolean;
  generating: boolean;
  onGenerate: (values: Record<string, string>) => void;
}

export default function ManualModePanel({
  docType, fieldSchema, schemaLoading, generating, onGenerate,
}: Props) {
  const [form] = Form.useForm();

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const fields: Record<string, string> = {};
      for (const [k, v] of Object.entries(values)) {
        if (v === undefined || v === null) {
          fields[k] = '';
        } else if (v !== null && typeof v === 'object' && '_isAMomentObject' in v) {
          const schema = fieldSchema.find((f) => f.key === k);
          const fmt = schema?.type === 'datetime' ? 'YYYY-MM-DD HH:mm:ss' : 'YYYY-MM-DD';
          fields[k] = (v as unknown as { format: (f: string) => string }).format(fmt);
        } else {
          fields[k] = String(v);
        }
      }
      onGenerate(fields);
    } catch {
      // 表单校验失败，antd 会自动提示
    }
  };

  return (
    <>
      {FIELD_GUIDE[docType] && (
        <Alert
          type="info"
          message={<span className="text-xs">{FIELD_GUIDE[docType]}</span>}
          showIcon
          icon={<InfoCircleOutlined />}
          className="mb-2"
        />
      )}

      <Form form={form} layout="vertical" size="small" className="max-h-[350px] overflow-auto pr-1">
        {schemaLoading ? (
          <div className="text-center py-8 text-slate-400 text-sm">加载字段中...</div>
        ) : (
          fieldSchema.map((f) => <FieldFormItem key={f.key} field={f} />)
        )}
      </Form>

      {generating && (
        <LoadingIndicator
          text="AI 正在填充模板、生成文书..."
          color="police"
        />
      )}

      <Button
        type="primary"
        size="large"
        block
        loading={generating}
        onClick={handleSubmit}
        className="h-11 text-base font-semibold border-0"
        icon={!generating ? <FormOutlined /> : undefined}
        style={{
          background: generating ? undefined : 'linear-gradient(135deg, #1a3a5c 0%, #1e4470 100%)',
          boxShadow: '0 2px 8px rgba(26,58,92,0.3)',
        }}
      >
        {generating ? '文书生成中...' : '填充生成文书'}
      </Button>
    </>
  );
}
