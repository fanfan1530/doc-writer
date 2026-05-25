import ReactDOM from 'react-dom/client';
import { ConfigProvider, App as AntApp } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import App from './App';
import ErrorBoundary from './components/ErrorBoundary';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <ConfigProvider locale={zhCN} theme={{ token: { colorPrimary: '#1a3a5c', borderRadius: 8 } }}>
    <AntApp>
      <ErrorBoundary>
        <App />
      </ErrorBoundary>
    </AntApp>
  </ConfigProvider>,
);
