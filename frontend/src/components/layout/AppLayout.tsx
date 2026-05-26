/** 应用布局外壳 —— 侧栏 + 顶栏 + 内容区 + 认证守卫。 */
import { useEffect, useState } from 'react';
import { Outlet, useNavigate, useLocation, Navigate } from 'react-router-dom';
import { Layout, Breadcrumb, Select, Button, Dropdown, App } from 'antd';
import {
  UserOutlined, LogoutOutlined, RobotOutlined, CaretDownOutlined,
  LoadingOutlined, FileTextOutlined,
} from '@ant-design/icons';
import { getAccessToken, clearTokens } from '../../api/client';
import client from '../../api/client';
import { useAppContext } from '../../context/AppContext';
import Sidebar from './Sidebar';
import type { ModelProvider } from '../../types';
import type { MenuProps } from 'antd';

const { Content, Header } = Layout;

const BREADCRUMB_MAP: Record<string, string> = {
  dashboard: '工作台',
  documents: '文书生成',
  copilot: 'AI 助手',
  cases: '类案检索',
  analysis: '案件分析',
  knowledge: '知识库',
  history: '历史文书',
  settings: '设置',
};

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [loggedIn, setLoggedIn] = useState(!!getAccessToken());
  const [models, setModels] = useState<ModelProvider[]>([]);
  const [currentId, setCurrentId] = useState('');
  const { sharedTranscript, clearSharedTranscript, generationTask } = useAppContext();

  // 登录状态监听
  useEffect(() => {
    const handler = () => setLoggedIn(false);
    window.addEventListener('auth:logout', handler);
    return () => window.removeEventListener('auth:logout', handler);
  }, []);

  // 加载模型列表
  useEffect(() => {
    if (!loggedIn) return;
    (async () => {
      try {
        const { data } = await client.get<{ models: ModelProvider[] }>('/models/list');
        const list = data.models || [];
        setModels(list);
        const active = list.find((m) => m.is_active);
        if (active) setCurrentId(active.id);
        else if (list.length > 0) setCurrentId(list[0].id);
      } catch { /* ignore */ }
    })();
  }, [loggedIn]);

  if (!loggedIn) {
    return <Navigate to="/login" replace />;
  }

  // 面包屑
  const raw = location.pathname.split('/').filter(Boolean);
  const segments = raw.length === 0 ? ['dashboard'] : raw;
  const pageTitle = BREADCRUMB_MAP[segments[0]] || segments[0];

  // 模型切换
  const handleSwitchModel = async (id: string) => {
    try {
      await client.post('/models/switch', { model_id: id });
      setCurrentId(id);
    } catch { /* ignore */ }
  };

  // 退出登录
  const handleLogout = () => {
    clearTokens();
    setLoggedIn(false);
    window.dispatchEvent(new Event('auth:logout'));
    navigate('/login');
  };

  const userMenuItems: MenuProps['items'] = [
    { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', onClick: handleLogout },
  ];

  return (
    <Layout className="h-screen overflow-hidden">
      <Sidebar />
      <Layout>
        {/* Top Bar */}
        <Header
          className="flex items-center justify-between px-5 h-12 border-b border-slate-100 bg-white/90 backdrop-blur-sm"
          style={{ lineHeight: 'normal' }}
        >
          <div className="flex items-center gap-3">
            <Breadcrumb
              items={[
                { title: '智慧警务' },
                ...segments.map((s, i) => ({
                  title: i === segments.length - 1 ? BREADCRUMB_MAP[s] || s : s,
                })),
              ]}
              className="text-xs"
            />
            {sharedTranscript && (
              <div className="flex items-center gap-1.5 bg-blue-50 border border-blue-200 rounded-full px-2.5 py-0.5 animate-fade-in">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
                <span className="text-[11px] text-blue-700 font-medium truncate max-w-[160px]">
                  {sharedTranscript.fileName}
                </span>
                <span className="text-[10px] text-blue-400">
                  ({sharedTranscript.text.length} 字)
                </span>
                <button
                  onClick={clearSharedTranscript}
                  className="text-blue-400 hover:text-blue-600 text-xs leading-none ml-0.5"
                  title="清除共享笔录"
                >
                  ×
                </button>
              </div>
            )}
            {generationTask.status === 'running' && (
              <div className="flex items-center gap-1.5 bg-amber-50 border border-amber-200 rounded-full px-2.5 py-0.5 animate-fade-in">
                <LoadingOutlined className="text-[11px] text-amber-600" spin />
                <span className="text-[11px] text-amber-700 font-medium truncate max-w-[140px]">
                  正在生成{generationTask.docType}
                </span>
              </div>
            )}
          </div>

          <div className="flex items-center gap-3">
            {/* 模型选择 */}
            {models.length > 0 && (
              <Select
                size="small"
                value={currentId}
                onChange={handleSwitchModel}
                className="w-40"
                options={models.map((m) => ({
                  label: m.name,
                  value: m.id,
                }))}
                prefix={<RobotOutlined className="text-police-400 text-xs" />}
              />
            )}

            <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
              <Button type="text" size="small" icon={<UserOutlined />} className="flex items-center gap-1">
                <CaretDownOutlined className="text-[10px] text-slate-400" />
              </Button>
            </Dropdown>
          </div>
        </Header>

        {/* Page Content */}
        <Content className="flex-1 min-h-0 overflow-auto bg-[#f2f3f7]">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
