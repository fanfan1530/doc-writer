/** 侧栏导航菜单配置 */
import {
  DashboardOutlined,
  FileTextOutlined,
  RobotOutlined,
  SearchOutlined,
  SafetyCertificateOutlined,
  BookOutlined,
  SettingOutlined,
  ClockCircleOutlined,
  BarChartOutlined,
} from '@ant-design/icons';
import type { ItemType } from 'antd/es/menu/interface';

export interface NavItem {
  key: string;
  label: string;
  icon: React.ReactNode;
  path: string;
  permission?: string;
}

export const NAV_ITEMS: NavItem[] = [
  { key: '/dashboard', label: '工作台', icon: <DashboardOutlined />, path: '/dashboard' },
  { key: '/documents', label: '文书生成', icon: <FileTextOutlined />, path: '/documents' },
  { key: '/copilot', label: 'AI 助手', icon: <RobotOutlined />, path: '/copilot' },
  { key: '/cases', label: '类案检索', icon: <SearchOutlined />, path: '/cases' },
  { key: '/cases/manage', label: '案件管理', icon: <SafetyCertificateOutlined />, path: '/cases/manage' },
  { key: '/analysis', label: '案件分析', icon: <SafetyCertificateOutlined />, path: '/analysis' },
  { key: '/knowledge', label: '知识库', icon: <BookOutlined />, path: '/knowledge' },
  { key: '/history', label: '历史文书', icon: <ClockCircleOutlined />, path: '/history' },
  { key: '/analytics', label: '数据分析', icon: <BarChartOutlined />, path: '/analytics' },
  { key: '/settings', label: '设置', icon: <SettingOutlined />, path: '/settings' },
];

export function toMenuItems(items: NavItem[]): ItemType[] {
  return items.map((item) => ({
    key: item.key,
    icon: item.icon,
    label: item.label,
  }));
}
