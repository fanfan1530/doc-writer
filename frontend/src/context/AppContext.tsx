/** 全局应用状态上下文 —— 模型列表 + 共享笔录 + 后台生成任务 + 跨页面通信 + RBAC。 */

import { createContext, useContext, useState, useCallback, useEffect, useRef, type ReactNode } from 'react';
import { clearTokens } from '../api/client';
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

export interface UserInfo {
  username: string;
  role: string;
  role_label: string;
  permissions: string[];
  display_name: string;
  unit: string;
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
  // RBAC
  userInfo: UserInfo | null;
  userPermissions: string[];
  userRole: string;
  hasPermission: (perm: string) => boolean;
  refreshUserInfo: () => void;
}

const INITIAL_TASK: GenerationTask = {
  status: 'idle', docType: '', inputText: '', result: null, error: null, startedAt: 0,
};

const DEFAULT_USER: UserInfo = {
  username: '', role: 'user', role_label: '普通用户', permissions: [], display_name: '', unit: '',
};

function loadUserInfo(): UserInfo | null {
  try {
    const raw = localStorage.getItem('user_info');
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return null;
}

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
  userInfo: null,
  userPermissions: [],
  userRole: 'user',
  hasPermission: () => false,
  refreshUserInfo: () => {},
});

export function AppProvider({ children }: { children: ReactNode }) {
  const [models, setModels] = useState<ModelProvider[]>([]);
  const [currentModelId, setCurrentModelId] = useState('');
  const [sharedTranscript, setSharedTranscript] = useState<SharedTranscript | null>(null);
  const [generationTask, setGenerationTask] = useState<GenerationTask>(INITIAL_TASK);
  const [userInfo, setUserInfo] = useState<UserInfo | null>(loadUserInfo);
  const abortRef = useRef<AbortController | null>(null);

  const userPermissions = userInfo?.permissions || [];
  const userRole = userInfo?.role || 'user';

  const hasPermission = useCallback(
    (perm: string) => userPermissions.includes(perm),
    [userPermissions],
  );

  const refreshUserInfo = useCallback(() => {
    const info = loadUserInfo();
    setUserInfo(info);
    // 如果用户信息不存在，触发登出
    if (!info) {
      clearTokens();
      window.dispatchEvent(new Event('auth:logout'));
    }
  }, []);

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
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      setGenerationTask((prev) => ({
        ...prev,
        status: 'error',
        error: err instanceof Error ? err.message : '生成失败',
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

  // 监听登出事件
  useEffect(() => {
    const handler = () => {
      setUserInfo(null);
      localStorage.removeItem('user_info');
    };
    window.addEventListener('auth:logout', handler);
    return () => window.removeEventListener('auth:logout', handler);
  }, []);

  useEffect(() => {
    refreshModels();
  }, [refreshModels]);

  return (
    <AppContext.Provider value={{
      models, currentModelId, refreshModels,
      sharedTranscript, setSharedTranscript, clearSharedTranscript,
      generationTask, startGeneration, abortGeneration, clearGeneration, updateGenerationContent,
      userInfo, userPermissions, userRole, hasPermission, refreshUserInfo,
    }}>
      {children}
    </AppContext.Provider>
  );
}

export function useAppContext() {
  return useContext(AppContext);
}
