/** 知识库 —— 三 Tab 统一浏览：文书模板 / 法律法规 / 填写规范 */
import { useState, useEffect, useCallback } from 'react';
import { Tabs, Spin } from 'antd';
import { BookOutlined, FileTextOutlined, ReadOutlined } from '@ant-design/icons';
import TemplateBrowser from './TemplateBrowser';
import LawBrowser from './LawBrowser';
import UsageGuidePanel from './UsageGuidePanel';
import client from '../../api/client';
import type { TemplateCategory } from '../../types';

export interface KnowledgeStats {
  total_laws: number;
  law_categories: number;
  with_penalty: number;
  total_templates: number;
  official_templates: number;
  top_laws: [string, number][];
}

export default function KnowledgeBasePage() {
  const [activeTab, setActiveTab] = useState('templates');
  const [stats, setStats] = useState<KnowledgeStats | null>(null);

  const loadStats = useCallback(async () => {
    try {
      const { data } = await client.get('/knowledge/stats');
      setStats(data);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadStats(); }, [loadStats]);

  return (
    <div className="p-4 page-enter h-full flex flex-col min-h-0">
      <h2 className="text-lg font-bold text-slate-800 mb-3 flex items-center gap-2 flex-shrink-0">
        <BookOutlined className="text-police-500" />
        知识库
        {stats && (
          <span className="text-xs font-normal text-slate-400 ml-2">
            {stats.total_templates} 模板 · {stats.total_laws} 法条 · {stats.official_templates} 官方
          </span>
        )}
      </h2>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        className="flex-1 flex flex-col min-h-0"
        style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
        items={[
          {
            key: 'templates',
            label: <span><FileTextOutlined />文书模板</span>,
            children: (
              <div className="flex-1 min-h-0" style={{ height: 'calc(100vh - 200px)' }}>
                <TemplateBrowser />
              </div>
            ),
          },
          {
            key: 'laws',
            label: <span><BookOutlined />法律法规</span>,
            children: (
              <div className="flex-1 min-h-0" style={{ height: 'calc(100vh - 200px)' }}>
                <LawBrowser />
              </div>
            ),
          },
          {
            key: 'guides',
            label: <span><ReadOutlined />填写规范</span>,
            children: (
              <div className="flex-1 min-h-0" style={{ height: 'calc(100vh - 200px)' }}>
                <UsageGuidePanel />
              </div>
            ),
          },
        ]}
      />
    </div>
  );
}
