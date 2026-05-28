/** 文书生成页面 —— 双栏布局：左侧输入 + 右侧预览 */
import { useState, useCallback, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { CheckCircleOutlined, EditOutlined, FileSearchOutlined, FileTextOutlined, UploadOutlined } from '@ant-design/icons';
import DocumentGeneratorV2 from '../DocumentGenerator_v2';
import DocumentPreview from '../DocumentPreview';
import { DEFAULT_DOC_TYPE } from '../../constants/docTypes';
import { useSharedTranscript } from '../../hooks/useSharedTranscript';
import { useAppContext } from '../../context/AppContext';
import type { GenerationResult } from '../../types';

export default function DocumentGenPage() {
  const [searchParams] = useSearchParams();
  const urlInput = searchParams.get('input') || '';
  const urlDocType = searchParams.get('doc_type') || '';

  const [docType, setDocType] = useState(urlDocType || DEFAULT_DOC_TYPE);
  const [inputText, setInputText] = useState(urlInput);
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

  const handleDocTypeChange = useCallback((t: string) => {
    setDocType(t);
    clearGeneration();
  }, [clearGeneration]);

  const handleInputChange = useCallback((text: string) => {
    setInputText(text);
    if (text.length > 80) {
      setSharedTranscript({
        text,
        rawText: '',
        fileName: sharedTranscript?.fileName || '手动输入',
        uploadedAt: Date.now(),
      });
    }
  }, [sharedTranscript, setSharedTranscript]);

  const handleResultChange = useCallback(
    (_r: GenerationResult | null, _loading: boolean) => {},
    [],
  );

  const effectiveGenerating = generationTask.status === 'running';
  const effectiveResult = generationTask.status === 'done' ? generationTask.result : null;
  const hasInput = inputText.trim().length > 0;
  const hasResult = !!effectiveResult?.content;

  const flowSteps = [
    { title: '选择类型', icon: <FileTextOutlined />, active: true },
    { title: '录入案情', icon: <UploadOutlined />, active: hasInput || effectiveGenerating || hasResult },
    { title: '核对要素', icon: <FileSearchOutlined />, active: effectiveGenerating || hasResult },
    { title: '生成导出', icon: hasResult ? <CheckCircleOutlined /> : <EditOutlined />, active: hasResult },
  ];

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

        <div className="flex flex-col lg:flex-row gap-3 flex-1 min-h-0">
        <div className="w-full lg:w-[500px] flex-shrink-0 flex flex-col min-h-0">
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
        </div>
        <div className="flex-1 min-w-0 min-h-0 flex flex-col">
          <div className="flex-shrink-0 pb-2 flex items-center justify-between">
            <span className="text-sm font-semibold text-slate-700 flex items-center gap-1.5">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-police-500" />
              文书预览与导出
            </span>
            <span className="text-xs text-slate-400">生成后可复制、打印或下载 Word</span>
          </div>
          <div className="flex-1 min-h-0">
            <DocumentPreview result={effectiveResult} generating={effectiveGenerating} docType={docType} />
          </div>
        </div>
        </div>
      </div>
    </div>
  );
}
