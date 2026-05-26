import ReactDOM from 'react-dom/client';
import { ConfigProvider, App as AntApp } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import AppV2 from './App_v2';
import ErrorBoundary from './components/ErrorBoundary';
import './index.css';

// 重构版入口 — 使用 AppV2（含 AppProvider 全局状态）
// 如需切回旧版，将 AppV2 改为 App, './App_v2' 改为 './App'
ReactDOM.createRoot(document.getElementById('root')!).render(
  <ConfigProvider locale={zhCN} theme={{ token: { colorPrimary: '#1a3a5c', borderRadius: 8 } }}>
    <AntApp>
      <ErrorBoundary>
        <AppV2 />
      </ErrorBoundary>
    </AntApp>
  </ConfigProvider>,
);
