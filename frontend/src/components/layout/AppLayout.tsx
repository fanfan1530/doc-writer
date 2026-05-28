/** 应用布局外壳 —— 侧栏 + 顶栏 + 内容区 + 认证守卫 + 通知中心。 */
import { useEffect, useState, useCallback } from 'react';
import { Outlet, useNavigate, useLocation, Navigate } from 'react-router-dom';
import { Layout, Breadcrumb, Select, Button, Dropdown, Badge, Popover, App } from 'antd';
import {
  UserOutlined, LogoutOutlined, RobotOutlined, CaretDownOutlined,
  LoadingOutlined, FileTextOutlined, BellOutlined,
} from '@ant-design/icons';
import { getAccessToken, clearTokens } from '../../api/client';
import client from '../../api/client';
import { useAppContext } from '../../context/AppContext';
import { useIdleTimer } from '../../hooks/useIdleTimer';
import { useWebSocket } from '../../hooks/useWebSocket';
import NotificationCenter from '../notifications/NotificationCenter';
import Sidebar from './Sidebar';
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
  const antApp = App.useApp();
  const [loggedIn, setLoggedIn] = useState(!!getAccessToken());
  const {
    sharedTranscript, clearSharedTranscript, generationTask,
    models, currentModelId, refreshModels,
  } = useAppContext();

  // 通知
  const [unreadCount, setUnreadCount] = useState(0);
  const handleNotification = useCallback(() => {
    // WebSocket 推送新通知时刷新未读数
    fetch('/api/notifications/unread-count', {
      headers: { Authorization: `Bearer ${getAccessToken()}` },
    }).then(r => r.json()).then(d => setUnreadCount(d.count || 0)).catch(() => {});
  }, []);

  // 初始化未读数 + 实时通知
  useEffect(() => {
    if (!loggedIn) return;
    fetch('/api/notifications/unread-count', {
      headers: { Authorization: `Bearer ${getAccessToken()}` },
    }).then(r => r.json()).then(d => setUnreadCount(d.count || 0)).catch(() => {});
  }, [loggedIn]);

  useWebSocket({
    url: `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/notifications`,
    onMessage: (data) => {
      if (data?.type) {
        setUnreadCount((c) => c + 1);
      }
    },
    enabled: loggedIn,
  });

  // 登录状态监听
  useEffect(() => {
    const handler = () => setLoggedIn(false);
    window.addEventListener('auth:logout', handler);
    return () => window.removeEventListener('auth:logout', handler);
  }, []);

  // 空闲超时保护（30 分钟无操作自动登出，提前 60 秒警告）
  useIdleTimer({
    timeout: 30 * 60 * 1000,
    promptBefore: 60 * 1000,
    enabled: loggedIn,
    onPrompt: () => {
      antApp.message.warning('即将因长时间未操作退出登录，请尽快操作');
    },
    onLogout: () => {
      clearTokens();
      setLoggedIn(false);
    },
  });

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
      refreshModels();
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
          role="banner"
          aria-label="顶部导航栏"
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
              aria-label="面包屑导航"
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
                value={currentModelId}
                onChange={handleSwitchModel}
                className="w-40"
                options={models.map((m) => ({
                  label: m.name,
                  value: m.id,
                }))}
                prefix={<RobotOutlined className="text-police-400 text-xs" />}
              />
            )}

            {/* 通知中心 */}
            <Popover
              content={<NotificationCenter onUnreadCountChange={setUnreadCount} />}
              trigger="click"
              placement="bottomRight"
            >
              <Badge count={unreadCount} size="small" offset={[-2, 2]}>
                <Button type="text" size="small" icon={<BellOutlined />} />
              </Badge>
            </Popover>

            <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
              <Button type="text" size="small" icon={<UserOutlined />} className="flex items-center gap-1">
                <CaretDownOutlined className="text-[10px] text-slate-400" />
              </Button>
            </Dropdown>
          </div>
        </Header>

        {/* Page Content */}
        <Content className="flex-1 min-h-0 overflow-auto bg-[#f2f3f7]" role="main" aria-label="页面内容区">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
