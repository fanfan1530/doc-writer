import { useState, useCallback } from 'react';
import Header from './components/Header';
import DocumentGenerator from './components/DocumentGenerator';
import DocumentPreview from './components/DocumentPreview';
import type { GenerationResult } from './types';

export default function App() {
  const [docType, setDocType] = useState('行政处罚决定书');
  const [inputText, setInputText] = useState('');
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [generating, setGenerating] = useState(false);

  const handleDocTypeChange = useCallback((t: string) => {
    setDocType(t);
    setResult(null);
  }, []);

  const handleInputChange = useCallback((text: string) => {
    setInputText(text);
  }, []);

  const handleResultChange = useCallback(
    (r: GenerationResult | null, loading: boolean) => {
      setResult(r);
      setGenerating(loading);
    },
    [],
  );

  return (
    <div className="h-screen flex flex-col bg-[#f2f3f7] overflow-hidden">
      <Header />
      <main className="flex-1 min-h-0 flex flex-col p-3 lg:p-4">
        <div className="flex flex-col lg:flex-row gap-3 lg:gap-4 flex-1 min-h-0 max-w-[1600px] mx-auto w-full">
          {/* Left: Input Workbench */}
          <div className="w-full lg:w-[420px] flex-shrink-0 flex flex-col min-h-0">
            <DocumentGenerator
              docType={docType}
              inputText={inputText}
              generating={generating}
              result={result}
              onDocTypeChange={handleDocTypeChange}
              onInputChange={handleInputChange}
              onResultChange={handleResultChange}
            />
          </div>
          {/* Right: Document Workspace */}
          <div className="flex-1 min-w-0 min-h-0">
            <DocumentPreview
              result={result}
              generating={generating}
              docType={docType}
            />
          </div>
        </div>
      </main>
    </div>
  );
}
