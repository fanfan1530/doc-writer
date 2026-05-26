/** 文件上传相关逻辑 Hook。 */

import { useState, useCallback } from 'react';
import { App } from 'antd';
import client from '../api/client';
import type { CaseFileSummaryResponse } from '../types';

export function useFileUpload(onTextExtracted: (text: string) => void) {
  const { message } = App.useApp();
  const [uploading, setUploading] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [rawTextPreview, setRawTextPreview] = useState<string | null>(null);
  const [showRawText, setShowRawText] = useState(false);

  const uploadFile = useCallback(async (file: File, docType: string) => {
    setUploading(true);
    setUploadedFileName(file.name);
    setRawTextPreview(null);
    setShowRawText(false);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('doc_type', docType);
    try {
      const { data } = await client.post<CaseFileSummaryResponse>(
        '/generation/summarize-case-file', formData,
        { headers: { 'Content-Type': 'multipart/form-data' } },
      );
      if (data.success) {
        if (data.raw_text) setRawTextPreview(data.raw_text);
        if (data.summary) {
          onTextExtracted(data.summary);
          message.success(
            `解析完成：从 ${data.raw_char_count} 字原文中提取了 ${data.char_count} 字的案件摘要，已填入输入框`,
          );
          if (data.warning) message.warning(data.warning);
        } else {
          setUploadedFileName(null);
          message.error(data.warning || 'AI 无法生成摘要，请检查模型配置或手动输入', 5);
        }
      }
    } catch (err) {
      message.error(`上传解析失败: ${err instanceof Error ? err.message : '文件处理失败'}`);
      setUploadedFileName(null);
    } finally {
      setUploading(false);
    }
  }, [message, onTextExtracted]);

  return {
    uploading, uploadedFileName, rawTextPreview, showRawText,
    setShowRawText, uploadFile,
  };
}
