/** 智慧警务智能工作台 v2.0 —— Router + 多模块工作台 */
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, App as AntApp } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { AppProvider } from './context/AppContext';
import ErrorBoundary from './components/ErrorBoundary';
import LoginPage from './components/LoginPage';
import AppLayout from './components/layout/AppLayout';
import DashboardPage from './components/dashboard/DashboardPage';
import DocumentGenPage from './components/document/DocumentGenPage';
import CopilotPage from './components/copilot/CopilotPage';
import CaseSearchPage from './components/cases/CaseSearchPage';
import CaseAnalysisPage from './components/analysis/CaseAnalysisPage';
import KnowledgeBasePage from './components/knowledge/KnowledgeBasePage';
import SettingsPage from './components/settings/SettingsPage';
import HistoryPage from './components/history/HistoryPage';

export default function AppV3() {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: { colorPrimary: '#1a3a5c', borderRadius: 8 },
        components: {
          Menu: {
            darkItemBg: 'transparent',
            darkItemSelectedBg: 'rgba(212,168,83,0.18)',
            darkItemSelectedColor: '#f0d78c',
            darkItemColor: 'rgba(255,255,255,0.82)',
            darkItemHoverBg: 'rgba(255,255,255,0.08)',
            darkItemHoverColor: '#ffffff',
            darkSubMenuItemBg: 'transparent',
            itemBorderRadius: 8,
          },
          Layout: {
            siderBg: '#101f38',
          },
        },
      }}
    >
      <AntApp>
        <ErrorBoundary>
          <AppProvider>
            <BrowserRouter>
              <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route element={<AppLayout />}>
                  <Route path="/" element={<Navigate to="/dashboard" replace />} />
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/documents" element={<DocumentGenPage />} />
                  <Route path="/copilot" element={<CopilotPage />} />
                  <Route path="/cases" element={<CaseSearchPage />} />
                  <Route path="/analysis" element={<CaseAnalysisPage />} />
                  <Route path="/knowledge" element={<KnowledgeBasePage />} />
                  <Route path="/history" element={<HistoryPage />} />
                  <Route path="/settings" element={<SettingsPage />} />
                </Route>
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Routes>
            </BrowserRouter>
          </AppProvider>
        </ErrorBoundary>
      </AntApp>
    </ConfigProvider>
  );
}
