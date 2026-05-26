/** AI 模式面板 — 案情输入 + 文件上传 + 生成按钮。 */

import { Input, Button } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import FileUploadZone from './FileUploadZone';
import LoadingIndicator from './LoadingIndicator';

interface Props {
  docType: string;
  inputText: string;
  generating: boolean;
  onInputChange: (text: string) => void;
  onGenerate: () => void;
}

export default function AiModePanel({
  docType, inputText, generating, onInputChange, onGenerate,
}: Props) {
  return (
    <>
      <FileUploadZone docType={docType} onTextExtracted={onInputChange} />

      <div className="mb-2">
        <Input.TextArea
          rows={6}
          value={inputText}
          onChange={(e) => onInputChange(e.target.value)}
          placeholder="在此输入案情描述，或上传文书文件自动提取..."
          className="text-sm"
        />
      </div>

      {generating && (
        <LoadingIndicator
          text="AI 正在分析案情、抽取关键要素、生成文书..."
          color="police"
        />
      )}

      <Button
        type="primary"
        size="large"
        block
        loading={generating}
        onClick={onGenerate}
        className="h-11 text-base font-semibold border-0"
        icon={!generating ? <SendOutlined /> : undefined}
        style={{
          background: generating ? undefined : 'linear-gradient(135deg, #1a3a5c 0%, #1e4470 100%)',
          boxShadow: '0 2px 8px rgba(26,58,92,0.3)',
        }}
      >
        {generating ? '文书生成中...' : '生成文书'}
      </Button>
    </>
  );
}
