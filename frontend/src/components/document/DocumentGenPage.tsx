/** 文书生成页面 —— 双栏布局：左侧输入 + 右侧预览 */
import { useState, useCallback, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import DocumentGeneratorV2 from '../DocumentGenerator_v2';
import DocumentPreview from '../DocumentPreview';
import { DEFAULT_DOC_TYPE } from '../../constants/docTypes';
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

  useEffect(() => {
    if (!urlInput && sharedTranscript && !inputText) {
      setInputText(sharedTranscript.text);
    }
  }, []);

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

  return (
    <div className="h-full flex flex-col p-3 page-enter min-h-0">
      <div className="flex flex-col lg:flex-row gap-3 flex-1 min-h-0 max-w-[1600px] mx-auto w-full">
        <div className="w-full lg:w-[420px] flex-shrink-0 flex flex-col min-h-0">
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
          <div className="flex-shrink-0 pb-1.5">
            <span className="text-xs font-medium text-slate-500 flex items-center gap-1">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-police-500" />
              文书预览
            </span>
          </div>
          <div className="flex-1 min-h-0">
            <DocumentPreview result={effectiveResult} generating={effectiveGenerating} docType={docType} />
          </div>
        </div>
      </div>
    </div>
  );
}
