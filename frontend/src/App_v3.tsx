/** 智慧警务智能工作台 v2.0 —— Router + 多模块工作台 */
import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, App as AntApp, Spin } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { AppProvider } from './context/AppContext';
import ErrorBoundary from './components/ErrorBoundary';

const LoginPage = lazy(() => import('./components/LoginPage'));
const AppLayout = lazy(() => import('./components/layout/AppLayout'));
const DashboardPage = lazy(() => import('./components/dashboard/DashboardPage'));
const DocumentGenPage = lazy(() => import('./components/document/DocumentGenPage'));
const CopilotPage = lazy(() => import('./components/copilot/CopilotPage'));
const CaseSearchPage = lazy(() => import('./components/cases/CaseSearchPage'));
const CaseListPage = lazy(() => import('./components/cases/CaseListPage'));
const CaseDetailPage = lazy(() => import('./components/cases/CaseDetailPage'));
const CaseAnalysisPage = lazy(() => import('./components/analysis/CaseAnalysisPage'));
const KnowledgeBasePage = lazy(() => import('./components/knowledge/KnowledgeBasePage'));
const SettingsPage = lazy(() => import('./components/settings/SettingsPage'));
const HistoryPage = lazy(() => import('./components/history/HistoryPage'));
const UserManagementPage = lazy(() => import('./components/admin/UserManagementPage'));
const AuditLogPage = lazy(() => import('./components/admin/AuditLogPage'));
const AnalyticsDashboard = lazy(() => import('./components/analytics/AnalyticsDashboard'));
const TemplateManagementPage = lazy(() => import('./components/admin/TemplateManagementPage'));

function PageLoader() {
  return (
    <div className="flex items-center justify-center h-full min-h-[200px]">
      <Spin size="large" />
    </div>
  );
}

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
        <ErrorBoundary
          resetKeys={[window.location.pathname]}
          onError={(error, info) => {
            console.error('[ErrorBoundary]', error.message, info.componentStack);
          }}
        >
          <AppProvider>
            <BrowserRouter>
              <Suspense fallback={<PageLoader />}>
                <Routes>
                  <Route path="/login" element={<LoginPage />} />
                  <Route element={<AppLayout />}>
                    <Route path="/" element={<Navigate to="/dashboard" replace />} />
                    <Route path="/dashboard" element={<DashboardPage />} />
                    <Route path="/analytics" element={<AnalyticsDashboard />} />
                    <Route path="/documents" element={<DocumentGenPage />} />
                    <Route path="/copilot" element={<CopilotPage />} />
                    <Route path="/cases" element={<CaseSearchPage />} />
                    <Route path="/cases/manage" element={<CaseListPage />} />
                    <Route path="/cases/manage/:id" element={<CaseDetailPage />} />
                    <Route path="/analysis" element={<CaseAnalysisPage />} />
                    <Route path="/knowledge" element={<KnowledgeBasePage />} />
                    <Route path="/history" element={<HistoryPage />} />
                    <Route path="/settings" element={<SettingsPage />} />
                    <Route path="/admin/users" element={<UserManagementPage />} />
                    <Route path="/admin/audit" element={<AuditLogPage />} />
                    <Route path="/admin/templates" element={<TemplateManagementPage />} />
                  </Route>
                  <Route path="*" element={<Navigate to="/dashboard" replace />} />
                </Routes>
              </Suspense>
            </BrowserRouter>
          </AppProvider>
        </ErrorBoundary>
      </AntApp>
    </ConfigProvider>
  );
}
