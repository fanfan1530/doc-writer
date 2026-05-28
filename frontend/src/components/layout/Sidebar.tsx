/** 警务侧栏 —— 可折叠，导航切换，权限过滤，高对比度设计。 */
import { useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Avatar, Dropdown } from 'antd';
import {
  SafetyCertificateOutlined,
  UserOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  SettingOutlined,
  AuditOutlined,
  TeamOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import { NAV_ITEMS, toMenuItems, type NavItem } from '../../constants/navigation';
import { useState, useMemo } from 'react';
import { clearTokens } from '../../api/client';
import { useAppContext } from '../../context/AppContext';
import type { MenuProps } from 'antd';

const { Sider } = Layout;

// 管理员专属导航项
const ADMIN_NAV_ITEMS: NavItem[] = [
  { key: '/admin/users', label: '用户管理', icon: <TeamOutlined />, path: '/admin/users', permission: 'users:read' },
  { key: '/admin/audit', label: '审计日志', icon: <AuditOutlined />, path: '/admin/audit', permission: 'audit:read' },
  { key: '/admin/templates', label: '模板管理', icon: <FileTextOutlined />, path: '/admin/templates', permission: 'documents:read' },
  { key: '/admin/settings', label: '系统设置', icon: <SettingOutlined />, path: '/settings', permission: 'models:read' },
];

export default function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const { userInfo, hasPermission } = useAppContext();

  const selectedKey = '/' + (location.pathname.split('/')[1] || 'dashboard');

  // 根据权限过滤导航项
  const filteredNavItems = useMemo(() => {
    const allItems = [...NAV_ITEMS];
    // 管理员导航
    if (hasPermission('users:read') || hasPermission('audit:read')) {
      for (const item of ADMIN_NAV_ITEMS) {
        if (!item.permission || hasPermission(item.permission)) {
          allItems.push(item);
        }
      }
    }
    return allItems;
  }, [hasPermission]);

  const handleLogout = () => {
    clearTokens();
    localStorage.removeItem('user_info');
    window.dispatchEvent(new Event('auth:logout'));
    navigate('/login');
  };

  const userMenuItems: MenuProps['items'] = [
    { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', onClick: handleLogout },
  ];

  const displayName = userInfo?.display_name || userInfo?.username || '用户';
  const roleLabel = userInfo?.role_label || '未知角色';

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
          items={toMenuItems(filteredNavItems)}
          onClick={({ key }) => navigate(key)}
          inlineCollapsed={collapsed}
          className="sidebar-menu"
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
                <div className="text-white/90 text-xs font-medium truncate">{displayName}</div>
                <div className="text-white/35 text-[10px]">{roleLabel}</div>
              </div>
            )}
          </div>
        </Dropdown>
      </div>
    </Sider>
  );
}
