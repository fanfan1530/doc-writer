/** 文书生成器 v2 —— 精简为布局编排组件 (~120行，原版490行)。
 *
 * 旧版 490 行的 God Component 拆分为了:
 *   DocumentGeneratorV2 (本文件) → AiModePanel + ManualModePanel
 *   + FileUploadZone + LoadingIndicator + FieldFormItem
 *   + useGeneration / useFileUpload (业务逻辑 Hooks)
 */

import { useState, useEffect, useCallback } from 'react';
import {
  Card, Select, Segmented, Divider, Space, Tag, Typography, Alert, App,
} from 'antd';
import { ThunderboltOutlined, EditOutlined, WarningOutlined } from '@ant-design/icons';
import { DOC_TYPES } from '../constants/docTypes';
import { useGeneration } from '../hooks/useGeneration';
import AiModePanel from './generator/AiModePanel';
import ManualModePanel from './generator/ManualModePanel';
import type { GenerationResult } from '../types';

const { Text } = Typography;

interface Props {
  docType: string;
  inputText: string;
  onDocTypeChange: (t: string) => void;
  onInputChange: (text: string) => void;
  onResultChange: (r: GenerationResult | null, loading: boolean) => void;
}

export default function DocumentGeneratorV2({
  docType, inputText,
  onDocTypeChange, onInputChange, onResultChange,
}: Props) {
  const { message } = App.useApp();
  const [mode, setMode] = useState<'ai' | 'manual'>('ai');

  const {
    generating, result, fieldSchema, schemaLoading, deadlineWarnings,
    loadSchema, generateFromText, generateFromFields,
    setResult,
  } = useGeneration();

  // 切换到手填模式时加载字段定义
  useEffect(() => {
    if (mode === 'manual') loadSchema(docType);
  }, [mode, docType, loadSchema]);

  // 同步 Hook 内部状态到父组件 (父组件需要 result/generating 传给 DocumentPreview)
  useEffect(() => {
    onResultChange(result, generating);
  }, [result, generating]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleDocTypeChange = (v: string) => {
    onDocTypeChange(v);
    setResult(null);
  };

  const handleModeChange = (v: 'ai' | 'manual') => {
    setMode(v as 'ai' | 'manual');
    setResult(null);
  };

  const handleAiGenerate = useCallback(async () => {
    if (!inputText.trim()) {
      message.warning('请输入案情描述');
      return;
    }
    await generateFromText(docType, inputText);
  }, [docType, inputText, generateFromText, message]);

  const handleManualGenerate = useCallback(async (fields: Record<string, string>) => {
    await generateFromFields(docType, fields);
  }, [docType, generateFromFields]);

  return (
    <Card className="shadow-sm border-0 rounded-xl h-full flex flex-col min-h-0"
      styles={{ body: { padding: '14px', display: 'flex', flexDirection: 'column', overflow: 'hidden', height: '100%' } }}>

      <div className="flex items-center gap-2 mb-2 flex-shrink-0">
        <Segmented
          size="small"
          value={mode}
          onChange={(v) => handleModeChange(v as 'ai' | 'manual')}
          options={[
            { label: 'AI', value: 'ai', icon: <ThunderboltOutlined /> },
            { label: '手动', value: 'manual', icon: <EditOutlined /> },
          ]}
        />
        <Select
          value={docType}
          onChange={handleDocTypeChange}
          size="small"
          className="flex-1 min-w-0"
          showSearch
          options={DOC_TYPES.map((t) => ({ label: t, value: t }))}
        />
      </div>

      <div className="flex-1 min-h-0 overflow-auto">
        {mode === 'ai' ? (
          <AiModePanel
            docType={docType}
            inputText={inputText}
            generating={generating}
            onInputChange={onInputChange}
            onGenerate={handleAiGenerate}
          />
        ) : (
          <ManualModePanel
            docType={docType}
            fieldSchema={fieldSchema}
            schemaLoading={schemaLoading}
            generating={generating}
            onGenerate={handleManualGenerate}
          />
        )}
      </div>

      <div className="flex-shrink-0">
        {result?.suggested_laws && result.suggested_laws.length > 0 && (
          <>
            <Divider className="!my-2" />
            <div>
              <Text strong className="text-xs text-slate-400">推荐法条</Text>
              <Space wrap className="mt-1" size={[2, 2]}>
                {result.suggested_laws.map((law, i) => (
                  <Tag key={i} color="blue" className="text-xs">
                    {law.length > 60 ? law.substring(0, 60) + '...' : law}
                  </Tag>
                ))}
              </Space>
            </div>
          </>
        )}
        {deadlineWarnings.length > 0 && (
          <>
            <Divider className="!my-2" />
            <div>
              <Space className="mb-1">
                <WarningOutlined className="text-orange-500 text-xs" />
                <Text strong className="text-xs text-orange-600">法律期限预警</Text>
              </Space>
              {deadlineWarnings.map((w, i) => (
                <Alert key={i}
                  type={w.level === 'critical' ? 'error' : 'warning'}
                  message={
                    <div className="text-xs">
                      {w.message}
                      {w.law_ref && <Text type="secondary" className="ml-1">({w.law_ref})</Text>}
                    </div>
                  }
                  className="mb-1" showIcon={false} />
              ))}
            </div>
          </>
        )}
      </div>
    </Card>
  );
}
