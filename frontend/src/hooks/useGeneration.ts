/** 文书生成相关业务逻辑 Hook — 从 DocumentGenerator 组件中提取。 */

import { useState, useCallback } from 'react';
import { App } from 'antd';
import client from '../api/client';
import type { GenerationResult, FieldSchema } from '../types';

export function useGeneration() {
  const { message } = App.useApp();
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [fieldSchema, setFieldSchema] = useState<FieldSchema[]>([]);
  const [schemaLoading, setSchemaLoading] = useState(false);
  const [deadlineWarnings, setDeadlineWarnings] = useState<
    Array<{ level: string; message: string; law_ref: string }>
  >([]);

  const loadSchema = useCallback(async (docType: string) => {
    setSchemaLoading(true);
    try {
      const { data } = await client.get(`/generation/templates/${encodeURIComponent(docType)}`);
      setFieldSchema((data.schema_fields || []) as FieldSchema[]);
    } catch {
      message.error('加载模板字段失败');
      setFieldSchema([]);
    } finally {
      setSchemaLoading(false);
    }
  }, [message]);

  const generateFromText = useCallback(async (docType: string, inputText: string) => {
    if (!inputText.trim()) {
      message.warning('请输入案情描述');
      return;
    }
    setGenerating(true);
    try {
      const { data } = await client.post<GenerationResult>('/generation/document', {
        doc_type: docType,
        input_text: inputText,
      }, { timeout: 120000 });
      setResult(data);
      if (!data.content) {
        message.warning('文书生成完成，但内容为空，请检查输入或更换文书类型');
      } else {
        message.success('文书生成完成');
      }
    } catch (err) {
      setResult(null);
      message.error(`生成失败: ${err instanceof Error ? err.message : '未知错误'}`);
    } finally {
      setGenerating(false);
    }
  }, [message]);

  const generateFromFields = useCallback(async (
    docType: string, fields: Record<string, string>,
  ) => {
    setGenerating(true);
    setDeadlineWarnings([]);
    try {
      const { data } = await client.post('/generation/fill-template', {
        doc_type: docType, fields,
      }, { timeout: 120000 });
      setResult({
        doc_type: docType,
        elements: data.elements,
        suggested_laws: data.suggested_laws || [],
        case_nature: data.case_nature || '',
        content: data.content,
      });
      if (data.deadline_warnings?.length > 0) setDeadlineWarnings(data.deadline_warnings);
      message.success('文书填充完成');
    } catch (err) {
      setResult(null);
      if (err && typeof err === 'object' && 'errorFields' in err) return;
      message.error(`填充失败: ${err instanceof Error ? err.message : '未知错误'}`);
    } finally {
      setGenerating(false);
    }
  }, [message]);

  const clear = useCallback(() => {
    setResult(null);
    setDeadlineWarnings([]);
  }, []);

  return {
    generating, result, fieldSchema, schemaLoading, deadlineWarnings,
    loadSchema, generateFromText, generateFromFields,
    setResult, setGenerating, clear,
  };
}
