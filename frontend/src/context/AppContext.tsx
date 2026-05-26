/** 全局应用状态上下文 —— 模型列表 + 共享笔录 + 后台生成任务 + 跨页面通信。 */

import { createContext, useContext, useState, useCallback, useEffect, useRef, type ReactNode } from 'react';
import client from '../api/client';
import type { ModelProvider, GenerationResult } from '../types';

export interface SharedTranscript {
  text: string;       // AI 提取后的摘要文本（用于各模块输入）
  rawText: string;    // Word 文件原始全文
  fileName: string;   // 上传的文件名
  uploadedAt: number; // 时间戳
}

export interface GenerationTask {
  status: 'idle' | 'running' | 'done' | 'error';
  docType: string;
  inputText: string;
  result: GenerationResult | null;
  error: string | null;
  startedAt: number;
}

interface AppState {
  models: ModelProvider[];
  currentModelId: string;
  refreshModels: () => Promise<void>;
  sharedTranscript: SharedTranscript | null;
  setSharedTranscript: (t: SharedTranscript | null) => void;
  clearSharedTranscript: () => void;
  generationTask: GenerationTask;
  startGeneration: (docType: string, inputText: string) => Promise<void>;
  abortGeneration: () => void;
  clearGeneration: () => void;
  updateGenerationContent: (content: string) => void;
}

const INITIAL_TASK: GenerationTask = {
  status: 'idle', docType: '', inputText: '', result: null, error: null, startedAt: 0,
};

const AppContext = createContext<AppState>({
  models: [],
  currentModelId: '',
  refreshModels: async () => {},
  sharedTranscript: null,
  setSharedTranscript: () => {},
  clearSharedTranscript: () => {},
  generationTask: INITIAL_TASK,
  startGeneration: async () => {},
  abortGeneration: () => {},
  clearGeneration: () => {},
  updateGenerationContent: () => {},
});

export function AppProvider({ children }: { children: ReactNode }) {
  const [models, setModels] = useState<ModelProvider[]>([]);
  const [currentModelId, setCurrentModelId] = useState('');
  const [sharedTranscript, setSharedTranscript] = useState<SharedTranscript | null>(null);
  const [generationTask, setGenerationTask] = useState<GenerationTask>(INITIAL_TASK);
  const abortRef = useRef<AbortController | null>(null);

  const refreshModels = useCallback(async () => {
    try {
      const { data } = await client.get<{ models: ModelProvider[] }>('/models/list');
      const list = data.models || [];
      setModels(list);
      const active = list.find((m) => m.is_active);
      if (active) setCurrentModelId(active.id);
      else if (list.length > 0) setCurrentModelId(list[0].id);
    } catch (err) {
      console.error('获取模型列表失败:', err);
    }
  }, []);

  const clearSharedTranscript = useCallback(() => setSharedTranscript(null), []);

  const startGeneration = useCallback(async (docType: string, inputText: string) => {
    const controller = new AbortController();
    abortRef.current = controller;

    setGenerationTask({
      status: 'running', docType, inputText, result: null, error: null, startedAt: Date.now(),
    });

    try {
      const { data } = await client.post<GenerationResult>('/generation/document', {
        doc_type: docType,
        input_text: inputText,
      }, { signal: controller.signal });

      if (controller.signal.aborted) return;

      setGenerationTask((prev) => ({
        ...prev,
        status: 'done',
        result: data,
      }));
    } catch (err: any) {
      if (controller.signal.aborted) return;
      setGenerationTask((prev) => ({
        ...prev,
        status: 'error',
        error: err?.message || '生成失败',
      }));
    }
  }, []);

  const abortGeneration = useCallback(() => {
    abortRef.current?.abort();
    setGenerationTask(INITIAL_TASK);
  }, []);

  const clearGeneration = useCallback(() => {
    setGenerationTask(INITIAL_TASK);
  }, []);

  const updateGenerationContent = useCallback((content: string) => {
    setGenerationTask((prev) => {
      if (prev.status !== 'done' || !prev.result) return prev;
      return {
        ...prev,
        result: { ...prev.result, content },
      };
    });
  }, []);

  useEffect(() => {
    refreshModels();
  }, [refreshModels]);

  return (
    <AppContext.Provider value={{
      models, currentModelId, refreshModels,
      sharedTranscript, setSharedTranscript, clearSharedTranscript,
      generationTask, startGeneration, abortGeneration, clearGeneration, updateGenerationContent,
    }}>
      {children}
    </AppContext.Provider>
  );
}

export function useAppContext() {
  return useContext(AppContext);
}
