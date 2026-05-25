import { useState, useEffect, useCallback } from 'react';
import {
  Card, Select, Input, Button, Typography, Space, Tag, Divider,
  Segmented, Form, DatePicker, InputNumber, Alert, Upload, App, Spin,
} from 'antd';
import {
  ThunderboltOutlined, EditOutlined, FormOutlined,
  InfoCircleOutlined, WarningOutlined, InboxOutlined,
  FileTextOutlined, LoadingOutlined, SendOutlined,
} from '@ant-design/icons';
import type { UploadProps } from 'antd';
import client from '../api/client';
import type {
  GenerationResult, CaseFileSummaryResponse, FieldSchema,
} from '../types';

const { Text } = Typography;

const DOC_TYPES = [
  '行政处罚决定书', '检查笔录', '现场勘查笔录', '辨认笔录',
  '搜查笔录', '行政处罚告知笔录', '调解协议书', '扣押决定书',
  '指认笔录', '结案报告',
];

const FIELD_GUIDE: Record<string, string> = {
  '行政处罚决定书': '需填写：当事人信息（姓名、性别、年龄、身份证号、住址）、案发日期与地点、违法事实描述、证据列表、处罚依据（具体法条）、处罚内容（拘留天数/罚款金额）、告知日期、处罚决定日期、权利告知、办案民警及单位。注意：告知日期必须在处罚决定日期之前。',
  '检查笔录': '需填写：公安机关名称、检查起止时间（精确到分钟）、检查地点（留空则默认为"公安机关名称+检查室"）、被检查人姓名、违法性质、检查人姓名及工作单位、见证人基本情况（姓名、性别、身份证件种类及号码）、有无发现涉案物品、有无发现损伤。检查地点、事由和目的、过程和结果由系统自动生成。',
  '现场勘查笔录': '需填写：案件编号、勘查起止时间、勘查地点、天气及照明条件、勘查人员、记录人、见证人≥2人、现场保护情况、现场方位及中心现场描述、提取痕迹物证情况、现场照片数量、现场图信息、录像信息、办案民警及单位。',
  '辨认笔录': '需填写：公安机关名称、辨认起止时间（精确到分钟）、辨认地点（留空则默认为"公安机关名称+询问室"）、办案人员姓名及单位、辨认人姓名及证件号及身份（被害人/证人/涉案人员）、见证人姓名及住址、辨认对象（如"N组十二张不同男性正面彩色免冠照片组"）、案发日期、案发地点、案件性质/案由、案件背景及辨认准备过程、辨认结果（每行一条，如"辨认照片X组中（X）号照片的人就是XX"）、记录人。辨认目的、辨认操作描述、辨认结论、确认声明由系统自动生成。',
  '搜查笔录': '需填写：案件编号、搜查起止时间、搜查地点、搜查人员≥2人、记录人、被搜查人及见证人、搜查证编号、搜查范围、搜查过程记录、查获物品及存放位置、扣押物品清单、搜查中损坏物品情况、被搜查人意见、办案民警及单位。',
  '行政处罚告知笔录': '需填写：案件编号、告知时间、告知地点、告知人、被告知人及身份证号、违法事实摘要、拟处罚内容、处罚依据（法条）、权利告知、被告知人陈述申辩内容、是否提出陈述申辩（是/否）、是否要求听证（是/否）、办案民警及单位。',
  '调解协议书': '需填写：案件编号、调解时间、调解地点、主持人、记录人、甲方（姓名、身份证号、住址、电话）、乙方（姓名、身份证号、住址、电话）、纠纷事实、调解协议内容（须具体可执行）、赔偿金额、履行期限、履行方式、自愿调解声明、办案民警及单位。',
  '扣押决定书': '需填写：案件编号、扣押日期、扣押地点、物品持有人及身份证号、扣押依据（法条）、扣押物品清单（逐项列明名称、数量、特征）、物品总数、保管地点、保管人、权利告知、持有人意见、处理决定备注、办案民警及单位。',
  '指认笔录': '需填写：公安机关名称、指认起止时间（精确到分钟）、指认地点（案发现场，默认为案发地点）、侦查人员姓名及单位、指认人姓名及性别及户籍地址、见证人姓名及单位/住址、案发日期、案发地点、案发经过简述、案件性质/案由、指认确认内容、指认对象、记录人。指认目的、指认地点和指认确认内容可由系统自动生成。',
  '结案报告': '需填写：案件编号、案件性质、违法/犯罪嫌疑人姓名及身份证号、发案时间与地点、立案日期、侦查/调查经过、证据情况综述、案件事实认定结论、法律适用说明、处理意见、呈请结案日期、办案民警及单位、审批意见。',
};

interface Props {
  docType: string;
  inputText: string;
  generating: boolean;
  result: GenerationResult | null;
  onDocTypeChange: (t: string) => void;
  onInputChange: (text: string) => void;
  onResultChange: (r: GenerationResult | null, loading: boolean) => void;
}

export default function DocumentGenerator({
  docType, inputText, generating, result,
  onDocTypeChange, onInputChange, onResultChange,
}: Props) {
  const { message } = App.useApp();
  const [mode, setMode] = useState<'ai' | 'manual'>('ai');
  const [uploading, setUploading] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [rawTextPreview, setRawTextPreview] = useState<string | null>(null);
  const [showRawText, setShowRawText] = useState(false);
  const [fieldSchema, setFieldSchema] = useState<FieldSchema[]>([]);
  const [schemaLoading, setSchemaLoading] = useState(false);
  const [deadlineWarnings, setDeadlineWarnings] = useState<
    Array<{ level: string; message: string; law_ref: string }>
  >([]);
  const [form] = Form.useForm();

  const loadSchema = useCallback(async (type: string) => {
    setSchemaLoading(true);
    try {
      const { data } = await client.get(`/generation/templates/${encodeURIComponent(type)}`);
      setFieldSchema((data.schema_fields || []) as FieldSchema[]);
      form.resetFields();
    } catch {
      message.error('加载模板字段失败');
      setFieldSchema([]);
    } finally {
      setSchemaLoading(false);
    }
  }, [form, message]);

  useEffect(() => {
    if (mode === 'manual') loadSchema(docType);
  }, [mode, docType, loadSchema]);

  const handleDocTypeChange = (v: string) => {
    onDocTypeChange(v);
    setDeadlineWarnings([]);
    form.resetFields();
  };

  const handleAiGenerate = async () => {
    if (!inputText.trim()) {
      message.warning('请输入案情描述');
      return;
    }
    onResultChange(null, true);
    try {
      const { data } = await client.post<GenerationResult>('/generation/document', {
        doc_type: docType,
        input_text: inputText,
      });
      onResultChange(data, false);
      message.success('文书生成完成');
    } catch (err) {
      onResultChange(null, false);
      message.error(`生成失败: ${err instanceof Error ? err.message : '未知错误'}`);
    }
  };

  const handleFileUpload = async (file: File) => {
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
          onInputChange(data.summary);
          message.success(`解析完成：从 ${data.raw_char_count} 字原文中提取了 ${data.char_count} 字的案件摘要，已填入输入框`);
          if (data.warning) message.warning(data.warning);
        } else {
          setUploadedFileName(null);
          message.error(data.warning || '文件文字已提取但 AI 无法生成摘要，请检查模型配置或手动输入', 5);
        }
      }
    } catch (err) {
      message.error(`上传解析失败: ${err instanceof Error ? err.message : '文件处理失败'}`);
      setUploadedFileName(null);
    } finally {
      setUploading(false);
    }
  };

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
      handleFileUpload(file as unknown as File);
      return false;
    },
  };

  const handleManualGenerate = async () => {
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
      onResultChange(null, true);
      setDeadlineWarnings([]);
      const { data } = await client.post('/generation/fill-template', { doc_type: docType, fields });
      onResultChange({
        doc_type: docType,
        elements: data.elements,
        suggested_laws: data.suggested_laws || [],
        case_nature: data.case_nature || '',
        content: data.content,
      }, false);
      if (data.deadline_warnings?.length > 0) setDeadlineWarnings(data.deadline_warnings);
      message.success('文书填充完成');
    } catch (err) {
      onResultChange(null, false);
      if (err && typeof err === 'object' && 'errorFields' in err) return;
      message.error(`填充失败: ${err instanceof Error ? err.message : '未知错误'}`);
    }
  };

  const renderFieldInput = (field: FieldSchema) => {
    const commonProps = {
      style: { width: '100%' },
      placeholder: `请输入${field.label}${field.required ? '（必填）' : ''}`,
    };
    switch (field.type) {
      case 'date':
        return (
          <Form.Item key={field.key} name={field.key} label={field.label}
            rules={field.required ? [{ required: true, message: `请选择${field.label}` }] : []}>
            <DatePicker {...commonProps} placeholder={`选择${field.label}`} />
          </Form.Item>
        );
      case 'datetime':
        return (
          <Form.Item key={field.key} name={field.key} label={field.label}
            rules={field.required ? [{ required: true, message: `请选择${field.label}` }] : []}>
            <DatePicker showTime format="YYYY-MM-DD HH:mm:ss" {...commonProps} placeholder={`选择${field.label}`} />
          </Form.Item>
        );
      case 'number':
        return (
          <Form.Item key={field.key} name={field.key} label={field.label}
            rules={field.required ? [{ required: true, message: `请输入${field.label}` }] : []}>
            <InputNumber {...commonProps} style={{ width: '100%' }} />
          </Form.Item>
        );
      case 'dict':
        if (field.dict_values?.length) {
          return (
            <Form.Item key={field.key} name={field.key} label={field.label}
              rules={field.required ? [{ required: true, message: `请选择${field.label}` }] : []}>
              <Select {...commonProps} placeholder={`选择${field.label}`} allowClear
                options={field.dict_values.map((v) => ({ label: v, value: v }))} />
            </Form.Item>
          );
        }
        return (
          <Form.Item key={field.key} name={field.key} label={field.label}
            rules={field.required ? [{ required: true, message: `请输入${field.label}` }] : []}>
            <Input {...commonProps} />
          </Form.Item>
        );
      case 'text': {
        const textareaKeys = [
          'illegal_fact', 'case_brief', 'case_fact', 'fact_description',
          'dispute_fact', 'inspection_process', 'inspection_findings',
          'search_process', 'investigation_summary', 'case_summary',
          'scene_description', 'identification_process', 'case_conclusion',
          'evidence_list', 'evidence_summary', 'qa_content', 'rights_statement',
          'seized_items_list', 'mediation_agreement', 'illegal_fact_summary',
          'handling_suggestion', 'law_application', 'items_seized', 'items_found',
          'evidence_collected', 'case_background', 'identification_results',
        ];
        if (textareaKeys.includes(field.key)) {
          return (
            <Form.Item key={field.key} name={field.key} label={field.label}
              rules={field.required ? [{ required: true, message: `请输入${field.label}` }] : []}>
              <Input.TextArea rows={3} {...commonProps} />
            </Form.Item>
          );
        }
        return (
          <Form.Item key={field.key} name={field.key} label={field.label}
            rules={field.required ? [{ required: true, message: `请输入${field.label}` }] : []}>
            <Input {...commonProps} />
          </Form.Item>
        );
      }
      default:
        return (
          <Form.Item key={field.key} name={field.key} label={field.label}
            rules={field.required ? [{ required: true, message: `请输入${field.label}` }] : []}>
            <Input {...commonProps} />
          </Form.Item>
        );
    }
  };

  return (
    <Card className="shadow-sm border-0 rounded-xl h-full flex flex-col min-h-0"
      bodyStyle={{ padding: '14px', display: 'flex', flexDirection: 'column', overflow: 'hidden', height: '100%' }}>

      {/* Row 1: Mode + Doc Type (compact one-row) */}
      <div className="flex items-center gap-2 mb-2 flex-shrink-0">
        <Segmented
          size="small"
          value={mode}
          onChange={(v) => {
            setMode(v as 'ai' | 'manual');
            onResultChange(null, false);
            setDeadlineWarnings([]);
          }}
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

      {/* Scrollable content area */}
      <div className="flex-1 min-h-0 overflow-auto">

        {mode === 'ai' ? (
          <>
            {/* Compact upload zone */}
            <div className="mb-2">
              <Upload.Dragger {...uploadProps}
                className="rounded-lg hover:border-police-400 transition-colors"
                style={{ padding: '16px 0' }}>
                <div className="flex items-center justify-center gap-2">
                  <InboxOutlined className="text-lg text-police-400" />
                  <span className="text-xs text-slate-500">上传 .doc/.docx 文书文件自动提取案情</span>
                </div>
              </Upload.Dragger>

              {/* Upload progress card */}
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

              {/* Raw text toggle */}
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

            {/* Main input area */}
            <div className="mb-2">
              <Input.TextArea
                rows={6}
                value={inputText}
                onChange={(e) => onInputChange(e.target.value)}
                placeholder="在此输入案情描述，或上传文书文件自动提取..."
                className="text-sm"
              />
            </div>

            {/* Generating indicator */}
            {generating && (
              <div className="mb-2 p-3 bg-gradient-to-r from-police-50 via-white to-police-50 border border-police-200 rounded-lg animate-fade-in overflow-hidden relative">
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/40 to-transparent animate-shimmer" />
                <div className="flex items-center gap-2 relative">
                  <div className="flex-shrink-0 w-7 h-7 rounded-full bg-police-600 flex items-center justify-center">
                    <Spin indicator={<LoadingOutlined style={{ fontSize: 14, color: '#fff' }} spin />} />
                  </div>
                  <span className="text-xs font-medium text-police-700">AI 正在分析案情、抽取关键要素、生成文书...</span>
                  <span className="inline-flex gap-0.5">
                    <span className="w-1 h-1 rounded-full bg-police-400 animate-dot-bounce [animation-delay:0ms]" />
                    <span className="w-1 h-1 rounded-full bg-police-400 animate-dot-bounce [animation-delay:150ms]" />
                    <span className="w-1 h-1 rounded-full bg-police-400 animate-dot-bounce [animation-delay:300ms]" />
                  </span>
                </div>
              </div>
            )}

            {/* Generate button - prominent gradient CTA */}
            <Button
              type="primary"
              size="large"
              block
              loading={generating}
              onClick={handleAiGenerate}
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
        ) : (
          <>
            {/* Field Guide */}
            {FIELD_GUIDE[docType] && (
              <Alert
                type="info"
                message={<span className="text-xs">{FIELD_GUIDE[docType]}</span>}
                showIcon
                icon={<InfoCircleOutlined />}
                className="mb-2"
              />
            )}

            {/* Dynamic Form */}
            {schemaLoading ? (
              <div className="text-center py-8 text-slate-400 text-sm">加载字段中...</div>
            ) : (
              <Form form={form} layout="vertical" size="small" className="max-h-[350px] overflow-auto pr-1">
                {fieldSchema.map(renderFieldInput)}
              </Form>
            )}

            {/* Generating indicator */}
            {generating && (
              <div className="my-2 p-3 bg-gradient-to-r from-police-50 via-white to-police-50 border border-police-200 rounded-lg animate-fade-in overflow-hidden relative">
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/40 to-transparent animate-shimmer" />
                <div className="flex items-center gap-2 relative">
                  <div className="flex-shrink-0 w-7 h-7 rounded-full bg-police-600 flex items-center justify-center">
                    <Spin indicator={<LoadingOutlined style={{ fontSize: 14, color: '#fff' }} spin />} />
                  </div>
                  <span className="text-xs font-medium text-police-700">AI 正在填充模板、生成文书...</span>
                  <span className="inline-flex gap-0.5">
                    <span className="w-1 h-1 rounded-full bg-police-400 animate-dot-bounce [animation-delay:0ms]" />
                    <span className="w-1 h-1 rounded-full bg-police-400 animate-dot-bounce [animation-delay:150ms]" />
                    <span className="w-1 h-1 rounded-full bg-police-400 animate-dot-bounce [animation-delay:300ms]" />
                  </span>
                </div>
              </div>
            )}

            <Button
              type="primary"
              size="large"
              block
              loading={generating}
              onClick={handleManualGenerate}
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
        )}
      </div>

      {/* Footer: Law suggestions + warnings - always visible */}
      <div className="flex-shrink-0">
        {result?.suggested_laws && result.suggested_laws.length > 0 && (
          <>
            <Divider className="!my-2" />
            <div>
              <Text strong className="text-xs text-slate-400">推荐法条</Text>
              <Space wrap className="mt-1" size={[2, 2]}>
                {result.suggested_laws.map((law, i) => (
                  <Tag key={i} color="blue" className="text-xs">{law.length > 60 ? law.substring(0, 60) + '...' : law}</Tag>
                ))}
              </Space>
            </div>
          </>
        )}
        {deadlineWarnings.length > 0 && (
          <>
            <Divider className="!my-2" />
            <div>
              <Space className="mb-1"><WarningOutlined className="text-orange-500 text-xs" /><Text strong className="text-xs text-orange-600">法律期限预警</Text></Space>
              {deadlineWarnings.map((w, i) => (
                <Alert key={i} type={w.level === 'critical' ? 'error' : 'warning'}
                  message={<div className="text-xs">{w.message}{w.law_ref && <Text type="secondary" className="ml-1">({w.law_ref})</Text>}</div>}
                  className="mb-1" showIcon={false} />
              ))}
            </div>
          </>
        )}
      </div>
    </Card>
  );
}
