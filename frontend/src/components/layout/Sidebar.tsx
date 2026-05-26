/** 警务侧栏 —— 可折叠，导航切换，高对比度设计。 */
import { useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Avatar, Dropdown } from 'antd';
import {
  SafetyCertificateOutlined,
  UserOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons';
import { NAV_ITEMS, toMenuItems } from '../../constants/navigation';
import { useState } from 'react';
import { clearTokens } from '../../api/client';
import type { MenuProps } from 'antd';

const { Sider } = Layout;

export default function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  const selectedKey = '/' + (location.pathname.split('/')[1] || 'dashboard');

  const handleLogout = () => {
    clearTokens();
    window.dispatchEvent(new Event('auth:logout'));
    navigate('/login');
  };

  const userMenuItems: MenuProps['items'] = [
    { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', onClick: handleLogout },
  ];

  return (
    <Sider
      collapsible
      collapsed={collapsed}
      onCollapse={setCollapsed}
      width={228}
      collapsedWidth={60}
      trigger={null}
      style={{
        background: 'linear-gradient(180deg, #101f38 0%, #152544 40%, #12203a 100%)',
        borderRight: '1px solid rgba(255,255,255,0.06)',
      }}
    >
      {/* Logo */}
      <div
        className={`flex items-center gap-3 h-14 border-b border-white/5 ${
          collapsed ? 'justify-center px-2' : 'px-5'
        }`}
      >
        <div className="w-9 h-9 rounded-lg bg-police-500 flex items-center justify-center flex-shrink-0"
          style={{ boxShadow: '0 2px 8px rgba(26,58,92,0.5)' }}>
          <SafetyCertificateOutlined className="text-white text-lg" />
        </div>
        {!collapsed && (
          <div className="leading-tight min-w-0">
            <div className="text-white text-sm font-bold tracking-wider">智慧警务</div>
            <div className="text-blue-200/70 text-[11px]">智能工作台</div>
          </div>
        )}
      </div>

      {/* Navigation Menu */}
      <div className="flex-1 overflow-auto py-2">
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={toMenuItems(NAV_ITEMS)}
          onClick={({ key }) => navigate(key)}
          inlineCollapsed={collapsed}
          style={{
            background: 'transparent',
            borderInlineEnd: 'none',
            fontSize: 14,
          }}
        />
      </div>

      {/* Collapse toggle */}
      <div
        className="flex items-center justify-center h-9 border-t border-white/5 cursor-pointer hover:bg-white/5 transition-colors"
        onClick={() => setCollapsed(!collapsed)}
      >
        {collapsed ? (
          <MenuUnfoldOutlined className="text-white/50 text-sm" />
        ) : (
          <MenuFoldOutlined className="text-white/50 text-sm" />
        )}
      </div>

      {/* User info */}
      <div className={`border-t border-white/5 ${collapsed ? 'px-2 py-3' : 'px-4 py-3'}`}>
        <Dropdown menu={{ items: userMenuItems }} placement="topRight" trigger={['click']}>
          <div className={`flex items-center cursor-pointer rounded-lg hover:bg-white/5 transition-colors ${collapsed ? 'justify-center py-1' : 'gap-2.5 py-1.5 px-2'}`}>
            <Avatar size={collapsed ? 28 : 30} icon={<UserOutlined />}
              style={{ background: '#3b5998', flexShrink: 0 }} />
            {!collapsed && (
              <div className="flex-1 min-w-0 leading-tight">
                <div className="text-white/90 text-xs font-medium truncate">admin</div>
                <div className="text-white/35 text-[10px]">系统管理员</div>
              </div>
            )}
          </div>
        </Dropdown>
      </div>
    </Sider>
  );
}
