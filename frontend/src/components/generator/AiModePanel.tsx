/** AI 模式面板 — 案情输入 + 文件上传 + 生成按钮 + 字符数提示 */
import { Alert, Button, Input, Typography } from 'antd';
import { SendOutlined, ExclamationCircleOutlined, InfoCircleOutlined } from '@ant-design/icons';
import FileUploadZone from './FileUploadZone';
import LoadingIndicator from './LoadingIndicator';

const { Text } = Typography;
const MAX_INPUT_CHARS = 8000;

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
  const overLimit = inputText.length > MAX_INPUT_CHARS;

  return (
    <>
      <Alert
        type="info"
        showIcon
        icon={<InfoCircleOutlined />}
        className="mb-3 rounded-lg"
        message={
          <span className="text-xs">
            建议包含：时间、地点、人员身份、违法事实、证据、处理依据和拟处罚内容。
          </span>
        }
      />

      <FileUploadZone docType={docType} onTextExtracted={onInputChange} />

      <div className="mb-2">
        <div className="flex items-center justify-between mb-1.5">
          <Text className="text-xs font-medium text-slate-600">案情描述</Text>
          <Text className="text-[10px] text-slate-400">支持粘贴笔录、案情摘要或上传 Word 自动提取</Text>
        </div>
        <Input.TextArea
          rows={9}
          value={inputText}
          onChange={(e) => onInputChange(e.target.value)}
          placeholder="请在这里输入案情。例如：2026年5月20日，张三在北京市朝阳区某商场内盗窃一部手机，价值5000元。"
          className="text-sm"
          maxLength={MAX_INPUT_CHARS + 1000}
        />
        <div className="flex items-center justify-between mt-1">
          <Text className={`text-[10px] ${overLimit ? 'text-red-500' : 'text-slate-400'}`}>
            {overLimit ? (
              <span className="flex items-center gap-0.5">
                <ExclamationCircleOutlined /> 超出推荐长度，后端将自动截断
              </span>
            ) : null}
          </Text>
          <Text className={`text-[10px] ${overLimit ? 'text-red-500 font-medium' : 'text-slate-400'}`}>
            {inputText.length} / {MAX_INPUT_CHARS} 字
          </Text>
        </div>
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
