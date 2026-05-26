/** 文件上传区域组件。 */

import { useState } from 'react';
import { Upload, Button, Spin, App } from 'antd';
import { InboxOutlined, LoadingOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { useFileUpload } from '../../hooks/useFileUpload';

interface Props {
  docType: string;
  onTextExtracted: (text: string) => void;
}

export default function FileUploadZone({ docType, onTextExtracted }: Props) {
  const { message } = App.useApp();
  const {
    uploading, uploadedFileName, rawTextPreview,
    showRawText, setShowRawText, uploadFile,
  } = useFileUpload(onTextExtracted);

  const uploadProps: UploadProps = {
    name: 'file',
    accept: '.doc,.docx',
    maxCount: 1,
    showUploadList: false,
    beforeUpload: (file) => {
      const lower = file.name.toLowerCase();
      if (!lower.endsWith('.doc') && !lower.endsWith('.docx')) {
        message.warning('仅支持 .doc 和 .docx 格式');
        return Upload.LIST_IGNORE;
      }
      if ((file.size ?? 0) > 10 * 1024 * 1024) {
        message.warning('文件大小不能超过 10 MB');
        return Upload.LIST_IGNORE;
      }
      uploadFile(file as unknown as File, docType);
      return false;
    },
  };

  return (
    <div className="mb-2">
      <Upload.Dragger {...uploadProps}
        className="rounded-lg hover:border-police-400 transition-colors"
        style={{ padding: '16px 0' }}>
        <div className="flex items-center justify-center gap-2">
          <InboxOutlined className="text-lg text-police-400" />
          <span className="text-xs text-slate-500">上传 .doc/.docx 文书文件自动提取案情</span>
        </div>
      </Upload.Dragger>

      {uploading && uploadedFileName && (
        <div className="mt-2 p-3 bg-gradient-to-r from-blue-50 to-sky-50 border border-blue-200 rounded-lg animate-fade-in overflow-hidden relative">
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/50 to-transparent animate-shimmer" />
          <div className="flex items-center gap-2 relative">
            <div className="flex-shrink-0 w-7 h-7 rounded-full bg-blue-500 flex items-center justify-center">
              <Spin indicator={<LoadingOutlined style={{ fontSize: 14, color: '#fff' }} spin />} />
            </div>
            <div className="flex-1 min-w-0">
              <span className="text-xs font-medium text-blue-700 truncate block">{uploadedFileName}</span>
              <span className="text-xs text-blue-500">AI 正在解析文书内容</span>
              <span className="inline-flex gap-0.5 ml-1.5">
                <span className="w-1 h-1 rounded-full bg-blue-400 animate-dot-bounce [animation-delay:0ms]" />
                <span className="w-1 h-1 rounded-full bg-blue-400 animate-dot-bounce [animation-delay:150ms]" />
                <span className="w-1 h-1 rounded-full bg-blue-400 animate-dot-bounce [animation-delay:300ms]" />
              </span>
            </div>
          </div>
        </div>
      )}

      {rawTextPreview && (
        <div className="mt-1">
          <Button type="link" size="small" onClick={() => setShowRawText(!showRawText)}>
            {showRawText ? '收起' : '查看'}提取的原文
          </Button>
          {showRawText && (
            <div className="p-2 bg-slate-50 rounded text-xs text-slate-600 max-h-[120px] overflow-auto whitespace-pre-wrap border border-slate-200">
              {rawTextPreview}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
