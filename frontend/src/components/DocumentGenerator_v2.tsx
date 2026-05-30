/** 文书生成器 v2 —— 精简为布局编排组件 (~120行，原版490行)。
 *
 * 旧版 490 行的 God Component 拆分为了:
 *   DocumentGeneratorV2 (本文件) → AiModePanel + ManualModePanel
 *   + FileUploadZone + LoadingIndicator + FieldFormItem
 *   + useGeneration / useFileUpload (业务逻辑 Hooks)
 */

import { useState, useEffect, useCallback } from 'react';
import {
  Card, Select, Segmented, Divider, Space, Typography, Alert, App,
} from 'antd';
import {
  ThunderboltOutlined, EditOutlined, WarningOutlined,
  FileDoneOutlined, FormOutlined,
} from '@ant-design/icons';
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
  /** 外部生成函数 —— 由父组件注入，用于后台持久化生成 */
  onGenerateText?: (docType: string, inputText: string) => Promise<void>;
  /** 外部生成状态 —— 用于恢复后台运行中的任务 */
  externalGenerating?: boolean;
  externalResult?: GenerationResult | null;
}

export default function DocumentGeneratorV2({
  docType, inputText,
  onDocTypeChange, onInputChange, onResultChange,
  onGenerateText, externalGenerating, externalResult,
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

  // 同步状态到父组件 —— 优先使用外部注入的状态（后台持久化），否则使用本地 Hook 状态
  const effectiveGenerating = externalGenerating ?? generating;
  const effectiveResult = externalResult ?? result;

  useEffect(() => {
    onResultChange(effectiveResult, effectiveGenerating);
  }, [effectiveResult, effectiveGenerating]); // eslint-disable-line react-hooks/exhaustive-deps

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
    if (onGenerateText) {
      await onGenerateText(docType, inputText);
    } else {
      await generateFromText(docType, inputText);
    }
  }, [docType, inputText, generateFromText, onGenerateText, message]);

  const handleManualGenerate = useCallback(async (fields: Record<string, string>) => {
    await generateFromFields(docType, fields);
  }, [docType, generateFromFields]);

  return (
    <Card className="shadow-sm border-0 rounded-xl h-full flex flex-col min-h-0"
      styles={{ body: { padding: '16px', display: 'flex', flexDirection: 'column', overflow: 'hidden', height: '100%' } }}>

      <div className="flex-shrink-0 mb-3">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div>
            <div className="text-base font-semibold text-slate-800 flex items-center gap-2">
              <FileDoneOutlined className="text-police-500" />
              文书生成
            </div>
            <div className="text-xs text-slate-400 mt-1">
              先补全案情，再核对右侧预览内容
            </div>
          </div>
          <Segmented
            size="small"
            value={mode}
            onChange={(v) => handleModeChange(v as 'ai' | 'manual')}
            options={[
              { label: 'AI', value: 'ai', icon: <ThunderboltOutlined /> },
              { label: '手填', value: 'manual', icon: <EditOutlined /> },
            ]}
          />
        </div>

        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
          <div className="text-xs font-medium text-slate-500 mb-1.5 flex items-center gap-1">
            <FormOutlined />
            文书类型
          </div>
          <Select
            value={docType}
            onChange={handleDocTypeChange}
            size="middle"
            className="w-full"
            showSearch
            options={DOC_TYPES.map((t) => ({ label: t, value: t }))}
          />
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-auto">
        {mode === 'ai' ? (
          <AiModePanel
            docType={docType}
            inputText={inputText}
            generating={effectiveGenerating}
            onInputChange={onInputChange}
            onGenerate={handleAiGenerate}
          />
        ) : (
          <ManualModePanel
            docType={docType}
            fieldSchema={fieldSchema}
            schemaLoading={schemaLoading}
            generating={effectiveGenerating}
            onGenerate={handleManualGenerate}
          />
        )}
      </div>

      <div className="flex-shrink-0">
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
