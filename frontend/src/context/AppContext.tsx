/** 全局应用状态上下文 — 模型列表、当前模型等跨组件共享状态。 */

import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react';
import client from '../api/client';
import type { ModelProvider } from '../types';

interface AppState {
  models: ModelProvider[];
  currentModelId: string;
  refreshModels: () => Promise<void>;
}

const AppContext = createContext<AppState>({
  models: [],
  currentModelId: '',
  refreshModels: async () => {},
});

export function AppProvider({ children }: { children: ReactNode }) {
  const [models, setModels] = useState<ModelProvider[]>([]);
  const [currentModelId, setCurrentModelId] = useState('');

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

  useEffect(() => {
    refreshModels();
  }, [refreshModels]);

  return (
    <AppContext.Provider value={{ models, currentModelId, refreshModels }}>
      {children}
    </AppContext.Provider>
  );
}

export function useAppContext() {
  return useContext(AppContext);
}
