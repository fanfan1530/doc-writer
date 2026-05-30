/** 文书生成页面 —— 双栏布局：左侧输入 + 右侧预览 */
import { useState, useCallback, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  CheckCircleOutlined,
  DownOutlined,
  EditOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  FormOutlined,
  SafetyCertificateOutlined,
  UpOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import { App, Button, Card, Tooltip } from 'antd';
import DocumentGeneratorV2 from '../DocumentGenerator_v2';
import DocumentPreview from '../DocumentPreview';
import ExtractedElementsPanel from './ExtractedElementsPanel';
import RiskCheckPanel from './RiskCheckPanel';
import { DEFAULT_DOC_TYPE } from '../../constants/docTypes';
import { useSharedTranscript } from '../../hooks/useSharedTranscript';
import { useAppContext } from '../../context/AppContext';
import client from '../../api/client';
import type { FieldSchema, GenerationResult } from '../../types';

export default function DocumentGenPage() {
  const { message } = App.useApp();
  const [searchParams] = useSearchParams();
  const urlInput = searchParams.get('input') || '';
  const urlDocType = searchParams.get('doc_type') || '';

  const [docType, setDocType] = useState(urlDocType || DEFAULT_DOC_TYPE);
  const [inputText, setInputText] = useState(urlInput);
  const [extractedElements, setExtractedElements] = useState<Record<string, string>>({});
  const [suggestedLaws, setSuggestedLaws] = useState<string[]>([]);
  const [caseNature, setCaseNature] = useState('');
  const [fieldLabels, setFieldLabels] = useState<Record<string, string>>({});
  const [extracting, setExtracting] = useState(false);
  const [confirmedGenerating, setConfirmedGenerating] = useState(false);
  const [confirmedResult, setConfirmedResult] = useState<GenerationResult | null>(null);
  const [activeElement, setActiveElement] = useState<{ key: string; label: string; value: string } | null>(null);
  const [collapsed, setCollapsed] = useState({
    generator: false,
    elements: false,
    preview: false,
    risk: false,
  });
  const {
    sharedTranscript, setSharedTranscript,
    generationTask, startGeneration, clearGeneration,
  } = useAppContext();

  useSharedTranscript(setInputText, !!urlInput);

  useEffect(() => {
    if (urlInput && urlInput.length > 30) {
      setSharedTranscript({
        text: urlInput,
        rawText: '',
        fileName: '历史记录回填',
        uploadedAt: Date.now(),
      });
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    const loadTemplateLabels = async () => {
      try {
        const { data } = await client.get(`/generation/templates/${encodeURIComponent(docType)}`);
        if (cancelled) return;
        const labels: Record<string, string> = {};
        ((data.schema_fields || []) as FieldSchema[]).forEach((field) => {
          if (field.key && field.label) labels[field.key] = field.label;
        });
        setFieldLabels(labels);
      } catch {
        if (!cancelled) setFieldLabels({});
      }
    };
    loadTemplateLabels();
    return () => { cancelled = true; };
  }, [docType]);

  const handleDocTypeChange = useCallback((t: string) => {
    setDocType(t);
    setExtractedElements({});
    setSuggestedLaws([]);
    setCaseNature('');
    setConfirmedResult(null);
    setActiveElement(null);
    clearGeneration();
  }, [clearGeneration]);

  const handleInputChange = useCallback((text: string) => {
    setInputText(text);
    setConfirmedResult(null);
    setActiveElement(null);
    if (text.length > 80) {
      setSharedTranscript({
        text,
        rawText: '',
        fileName: sharedTranscript?.fileName || '手动输入',
        uploadedAt: Date.now(),
      });
    }
  }, [sharedTranscript, setSharedTranscript]);

  const handleExtractElements = useCallback(async () => {
    if (!inputText.trim()) {
      message.warning('请先输入案情或上传材料');
      return;
    }
    setExtracting(true);
    try {
      const { data } = await client.post('/generation/extract-elements', {
        doc_type: docType,
        input_text: inputText,
      }, { timeout: 120000 });
      setExtractedElements(data.elements || {});
      setSuggestedLaws(data.suggested_laws || []);
      setCaseNature(data.case_nature || '');
      setConfirmedResult(null);
      setActiveElement(null);
      message.success('要素提取完成，请核对后生成');
    } catch (err) {
      message.error(err instanceof Error ? err.message : '要素提取失败');
    } finally {
      setExtracting(false);
    }
  }, [docType, inputText, message]);

  const handleElementChange = useCallback((key: string, value: string) => {
    setExtractedElements((prev) => ({ ...prev, [key]: value }));
    setActiveElement((prev) => (prev?.key === key ? { ...prev, value } : prev));
  }, []);

  const handleGenerateFromElements = useCallback(async () => {
    const fields = Object.fromEntries(
      Object.entries(extractedElements)
        .map(([key, value]) => [key, cleanElementValue(value)])
        .filter(([, value]) => String(value ?? '').trim()),
    );
    if (Object.keys(fields).length === 0) {
      message.warning('请先提取或填写案件要素');
      return;
    }
    setConfirmedGenerating(true);
    try {
      const { data } = await client.post('/generation/fill-template', {
        doc_type: docType,
        fields,
      }, { timeout: 120000 });
      setConfirmedResult({
        doc_type: docType,
        elements: data.elements || fields,
        suggested_laws: data.suggested_laws || suggestedLaws,
        case_nature: data.case_nature || caseNature,
        content: data.content || '',
      });
      setSuggestedLaws(data.suggested_laws || suggestedLaws);
      setCaseNature(data.case_nature || caseNature);
      message.success('已按确认要素生成文书');
    } catch (err) {
      message.error(err instanceof Error ? err.message : '生成失败');
    } finally {
      setConfirmedGenerating(false);
    }
  }, [caseNature, docType, extractedElements, message, suggestedLaws]);

  const handleResultChange = useCallback(
    (_r: GenerationResult | null, _loading: boolean) => {},
    [],
  );

  const rawGeneratedResult = generationTask.status === 'done' ? generationTask.result : null;
  const effectiveGenerating = generationTask.status === 'running' || confirmedGenerating;
  const effectiveResult = confirmedResult || rawGeneratedResult;
  const hasInput = inputText.trim().length > 0;
  const hasResult = !!effectiveResult?.content;

  useEffect(() => {
    if (!rawGeneratedResult) return;
    setExtractedElements(rawGeneratedResult.elements || {});
    setSuggestedLaws(rawGeneratedResult.suggested_laws || []);
    setCaseNature(rawGeneratedResult.case_nature || '');
  }, [rawGeneratedResult]);

  const flowSteps = [
    { title: '选择类型', icon: <FileTextOutlined />, active: true },
    { title: '录入案情', icon: <UploadOutlined />, active: hasInput || effectiveGenerating || hasResult },
    { title: '核对要素', icon: <FileSearchOutlined />, active: effectiveGenerating || hasResult },
    { title: '生成导出', icon: hasResult ? <CheckCircleOutlined /> : <EditOutlined />, active: hasResult },
  ];

  const togglePanel = (key: keyof typeof collapsed) => {
    setCollapsed((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const leftWidth = collapsed.generator ? '56px' : '420px';
  const elementsWidth = collapsed.elements ? '56px' : '380px';

  return (
    <div className="h-full flex flex-col p-4 page-enter min-h-0">
      <div className="max-w-[1600px] mx-auto w-full flex flex-col gap-3 flex-1 min-h-0">
        <div className="bg-white rounded-xl shadow-sm border border-slate-100 px-4 py-3 flex-shrink-0">
          <div className="grid grid-cols-4 gap-2">
            {flowSteps.map((step, index) => (
              <div
                key={step.title}
                className={`relative flex items-center gap-2 rounded-lg px-3 py-2 ${
                  step.active ? 'bg-police-50 text-police-700' : 'bg-slate-50 text-slate-400'
                }`}
              >
                {index > 0 && (
                  <span className="hidden lg:block absolute -left-2 top-1/2 h-px w-2 bg-slate-200" />
                )}
                <span className={`w-7 h-7 rounded-lg flex items-center justify-center ${
                  step.active ? 'bg-police-600 text-white' : 'bg-white text-slate-400'
                }`}>
                  {step.icon}
                </span>
                <span className="text-sm font-medium truncate">{step.title}</span>
              </div>
            ))}
          </div>
        </div>

        <div
          className="grid gap-3 flex-1 min-h-0"
          style={{ gridTemplateColumns: `${leftWidth} ${elementsWidth} minmax(420px, 1fr)` }}
        >
        <div className="flex flex-col min-h-0">
          {collapsed.generator ? (
            <CollapsedRail
              title="文书生成"
              icon={<FormOutlined />}
              onExpand={() => togglePanel('generator')}
            />
          ) : (
            <PanelShell title="文书生成" onCollapse={() => togglePanel('generator')}>
              <DocumentGeneratorV2
                docType={docType}
                inputText={inputText}
                onDocTypeChange={handleDocTypeChange}
                onInputChange={handleInputChange}
                onResultChange={handleResultChange}
                onGenerateText={startGeneration}
                externalGenerating={effectiveGenerating}
                externalResult={effectiveResult}
              />
            </PanelShell>
          )}
        </div>
        <div className="min-h-0">
          {collapsed.elements ? (
            <CollapsedRail
              title="要素确认"
              icon={<FileSearchOutlined />}
              onExpand={() => togglePanel('elements')}
            />
          ) : (
            <PanelShell title="要素确认" onCollapse={() => togglePanel('elements')}>
              <ExtractedElementsPanel
                elements={extractedElements}
                fieldLabels={fieldLabels}
                caseNature={caseNature}
                extracting={extracting}
                generating={confirmedGenerating}
                canExtract={hasInput && !effectiveGenerating}
                onExtract={handleExtractElements}
                onElementChange={handleElementChange}
                onElementFocus={(key, label, value) => setActiveElement({ key, label, value })}
                onGenerateFromElements={handleGenerateFromElements}
              />
            </PanelShell>
          )}
        </div>
        <div className="min-w-0 min-h-0 flex flex-col">
          {collapsed.preview ? (
            <CollapsedStrip
              title="文书预览"
              icon={<FileTextOutlined />}
              onExpand={() => togglePanel('preview')}
            />
          ) : (
            <>
              <div className="flex-shrink-0 pb-2 flex items-center justify-between">
                <span className="text-sm font-semibold text-slate-700 flex items-center gap-1.5">
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-police-500" />
                  文书预览与导出
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-400">生成后可复制、打印或下载 Word</span>
                  <Tooltip title="收起文书预览">
                    <Button size="small" type="text" icon={<UpOutlined />} onClick={() => togglePanel('preview')} />
                  </Tooltip>
                </div>
              </div>
              <div className="flex-1 min-h-0">
                <DocumentPreview
                  result={effectiveResult}
                  generating={effectiveGenerating}
                  docType={docType}
                  highlightText={activeElement?.value}
                  highlightLabel={activeElement?.label}
                />
              </div>
            </>
          )}
          {collapsed.risk ? (
            <CollapsedStrip
              title="风险检查"
              icon={<SafetyCertificateOutlined />}
              onExpand={() => togglePanel('risk')}
              className="mt-3"
            />
          ) : (
            <div className="flex-shrink-0 mt-3 relative">
              <div className="absolute right-2 top-2 z-10">
                <Tooltip title="收起风险检查">
                  <Button size="small" type="text" icon={<DownOutlined />} onClick={() => togglePanel('risk')} />
                </Tooltip>
              </div>
              <RiskCheckPanel result={effectiveResult} elements={extractedElements} />
            </div>
          )}
        </div>
        </div>
      </div>
    </div>
  );
}

function cleanElementValue(value: unknown): string {
  return String(value ?? '')
    .replace(/\uFFFD/g, '')
    .replace(/\r\n/g, '\n')
    .trim();
}

function PanelShell({
  title,
  children,
  onCollapse,
}: {
  title: string;
  children: React.ReactNode;
  onCollapse: () => void;
}) {
  return (
    <div className="relative h-full min-h-0">
      <div className="absolute right-2 top-2 z-20">
        <Tooltip title={`收起${title}`}>
          <Button size="small" type="text" icon={<UpOutlined />} onClick={onCollapse} />
        </Tooltip>
      </div>
      {children}
    </div>
  );
}

function CollapsedRail({
  title,
  icon,
  onExpand,
}: {
  title: string;
  icon: React.ReactNode;
  onExpand: () => void;
}) {
  return (
    <Card
      className="h-full rounded-xl shadow-sm border-0 cursor-pointer hover:shadow-md transition-all"
      styles={{ body: { padding: 0, height: '100%' } }}
      onClick={onExpand}
    >
      <Tooltip title={`展开${title}`} placement="right">
        <div className="h-full flex flex-col items-center justify-start py-4 gap-3 text-police-600">
          <Button type="text" size="small" icon={<DownOutlined />} />
          <div className="text-lg">{icon}</div>
          <div
            className="text-xs font-semibold tracking-wide"
            style={{ writingMode: 'vertical-rl' }}
          >
            {title}
          </div>
        </div>
      </Tooltip>
    </Card>
  );
}

function CollapsedStrip({
  title,
  icon,
  onExpand,
  className = '',
}: {
  title: string;
  icon: React.ReactNode;
  onExpand: () => void;
  className?: string;
}) {
  return (
    <Card
      size="small"
      className={`rounded-xl shadow-sm border-0 cursor-pointer hover:shadow-md transition-all ${className}`}
      styles={{ body: { padding: '10px 12px' } }}
      onClick={onExpand}
    >
      <div className="flex items-center justify-between text-police-600">
        <div className="flex items-center gap-2 text-sm font-semibold">
          {icon}
          {title}
        </div>
        <Button type="text" size="small" icon={<DownOutlined />} />
      </div>
    </Card>
  );
}
