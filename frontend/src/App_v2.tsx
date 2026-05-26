/** 应用根组件 v2 —— 全局状态 + 文书生成 + 文书预览 + AI 助手（上下分屏）+ 认证。 */

import { useState, useCallback, useEffect, useRef } from 'react';
import Header from './components/Header';
import DocumentGeneratorV2 from './components/DocumentGenerator_v2';
import DocumentPreview from './components/DocumentPreview';
import ChatPanel from './components/ChatPanel';
import LoginPage from './components/LoginPage';
import { AppProvider } from './context/AppContext';
import { DEFAULT_DOC_TYPE } from './constants/docTypes';
import { getAccessToken } from './api/client';
import type { GenerationResult } from './types';

function AppV2() {
  const [loggedIn, setLoggedIn] = useState(!!getAccessToken());
  const [docType, setDocType] = useState(DEFAULT_DOC_TYPE);
  const [inputText, setInputText] = useState('');
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [generating, setGenerating] = useState(false);

  // 分屏拖拽
  const [splitRatio, setSplitRatio] = useState(55); // 上 55% / 下 45%
  const rightPanelRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  useEffect(() => {
    const handler = () => setLoggedIn(false);
    window.addEventListener('auth:logout', handler);
    return () => window.removeEventListener('auth:logout', handler);
  }, []);

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

  // AI 助手修改文书后，替换预览内容
  const handleDocumentModified = useCallback((content: string) => {
    setResult((prev) => prev ? { ...prev, content } : null);
  }, []);

  // ── 拖拽分屏 ──
  const handleMouseDown = useCallback(() => {
    dragging.current = true;
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!dragging.current || !rightPanelRef.current) return;
      const rect = rightPanelRef.current.getBoundingClientRect();
      const y = e.clientY - rect.top;
      const pct = (y / rect.height) * 100;
      setSplitRatio(Math.min(80, Math.max(20, pct)));
    };
    const handleMouseUp = () => {
      if (dragging.current) {
        dragging.current = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      }
    };
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  if (!loggedIn) {
    return <LoginPage onLogin={() => setLoggedIn(true)} />;
  }

  return (
    <AppProvider>
      <div className="h-screen flex flex-col bg-[#f2f3f7] overflow-hidden">
        <Header />
        <main className="flex-1 min-h-0 flex flex-col p-3 lg:p-4">
          <div className="flex flex-col lg:flex-row gap-3 lg:gap-4 flex-1 min-h-0 max-w-[1600px] mx-auto w-full">
            {/* Left: Input Workbench */}
            <div className="w-full lg:w-[420px] flex-shrink-0 flex flex-col min-h-0">
              <DocumentGeneratorV2
                docType={docType}
                inputText={inputText}
                onDocTypeChange={handleDocTypeChange}
                onInputChange={handleInputChange}
                onResultChange={handleResultChange}
              />
            </div>

            {/* Right: 上下分屏 — 文书预览 + AI 助手 */}
            <div ref={rightPanelRef} className="flex-1 min-w-0 min-h-0 flex flex-col gap-1">
              {/* 文书预览 */}
              <div style={{ flex: splitRatio }} className="min-h-0 flex flex-col">
                <div className="flex-shrink-0 pb-1.5">
                  <span className="text-xs font-medium text-slate-500 flex items-center gap-1">
                    <span className="inline-block w-1.5 h-1.5 rounded-full bg-police-500" />
                    文书预览
                  </span>
                </div>
                <div className="flex-1 min-h-0">
                  <DocumentPreview
                    result={result}
                    generating={generating}
                    docType={docType}
                  />
                </div>
              </div>

              {/* 拖拽把手 */}
              <div
                className="flex-shrink-0 h-2 cursor-row-resize rounded-full bg-slate-200 hover:bg-police-400 transition-colors mx-8 relative group"
                onMouseDown={handleMouseDown}
              >
                <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 flex items-center">
                  <div className="w-8 h-1 rounded-full bg-slate-300 group-hover:bg-police-500 transition-colors" />
                </div>
              </div>

              {/* AI 助手 */}
              <div style={{ flex: 100 - splitRatio }} className="min-h-0 flex flex-col">
                <div className="flex-shrink-0 pb-1.5">
                  <span className="text-xs font-medium text-slate-500 flex items-center gap-1">
                    <span className="inline-block w-1.5 h-1.5 rounded-full bg-blue-500" />
                    AI 助手
                  </span>
                </div>
                <div className="flex-1 min-h-0">
                  <ChatPanel
                    docContext={result?.content || ''}
                    docType={docType}
                    onDocumentModified={handleDocumentModified}
                  />
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    </AppProvider>
  );
}

export default AppV2;
