import { useState, useEffect, useCallback } from 'react';
import { Select, Button, App } from 'antd';
import { SettingOutlined } from '@ant-design/icons';
import client from '../api/client';
import ModelSettings from './ModelSettings';
import type { ModelProvider } from '../types';

export default function Header() {
  const { message } = App.useApp();
  const [models, setModels] = useState<ModelProvider[]>([]);
  const [currentId, setCurrentId] = useState('');
  const [settingsOpen, setSettingsOpen] = useState(false);

  const fetchModels = useCallback(async () => {
    try {
      const { data } = await client.get<{ models: ModelProvider[] }>('/models/list');
      const list = data.models || [];
      setModels(list);
      const active = list.find((m) => m.is_active);
      if (active) setCurrentId(active.id);
    } catch {
      // silent
    }
  }, []);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  const handleSwitch = async (id: string) => {
    try {
      await client.post('/models/switch', { model_id: id });
      setCurrentId(id);
      message.success('模型已切换');
    } catch {
      message.error('切换失败');
    }
  };

  const handleSettingsSaved = () => {
    setSettingsOpen(false);
    fetchModels();
  };

  return (
    <>
      <header className="bg-gradient-to-r from-police-900 via-police-700 to-police-600 shadow-md sticky top-0 z-50">
        <div className="max-w-[1600px] mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">&#x2696;</span>
            <h1 className="text-xl font-semibold text-white tracking-wide">
              智能文书编写
            </h1>
            <span className="text-xs text-gold-500 px-2 py-0.5 border border-gold-500/40 rounded-full">
              AI
            </span>
          </div>

          <div className="flex items-center gap-3">
            <Select
              value={currentId || undefined}
              onChange={handleSwitch}
              size="middle"
              variant="borderless"
              className="min-w-[180px] header-select"
              popupMatchSelectWidth={false}
              options={(Array.isArray(models) ? models : []).map((m: ModelProvider) => ({
                label: m.name,
                value: m.id,
              }))}
            />
            <Button
              type="text"
              icon={<SettingOutlined />}
              onClick={() => setSettingsOpen(true)}
              className="text-white/80"
            />
          </div>
        </div>
      </header>

      <ModelSettings
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        models={models}
        onSaved={handleSettingsSaved}
      />
    </>
  );
}
