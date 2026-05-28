/** 工作台首页 —— 统计概览 + 趋势图 + 快捷入口 + 最近活动 + 系统状态 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Statistic, Row, Col, Tag, Typography, Divider, Tooltip } from 'antd';
import {
  FileTextOutlined, RobotOutlined, SearchOutlined,
  SafetyCertificateOutlined, BookOutlined, ClockCircleOutlined,
  ThunderboltOutlined, RightOutlined, CheckCircleOutlined,
  ArrowUpOutlined, HistoryOutlined, ApiOutlined,
  CheckCircleFilled, CloseCircleFilled,
} from '@ant-design/icons';
import { useHistoryStats } from '../../hooks/useHistoryStats';
import { useAppContext } from '../../context/AppContext';
import client from '../../api/client';

const { Text } = Typography;

interface QuickAction {
  icon: React.ReactNode;
  title: string;
  desc: string;
  path: string;
  color: string;
}

const QUICK_ACTIONS: QuickAction[] = [
  { icon: <FileTextOutlined />, title: '生成文书', desc: 'AI 智能生成公安法律文书', path: '/documents', color: '#1a3a5c' },
  { icon: <RobotOutlined />, title: 'AI 助手', desc: '智能法律咨询与文书润色', path: '/copilot', color: '#1e4470' },
  { icon: <SearchOutlined />, title: '类案检索', desc: '检索相似案例与处理参考', path: '/cases', color: '#2c5f2d' },
  { icon: <SafetyCertificateOutlined />, title: '案件分析', desc: '案情要素提取与时间线', path: '/analysis', color: '#b85c1a' },
  { icon: <BookOutlined />, title: '知识库', desc: '法律法规体系化检索', path: '/knowledge', color: '#6b3a8b' },
];

const TYPE_COLORS: Record<string, string> = {
  '行政处罚决定书': '#1a3a5c',
  '立案报告': '#1e4470',
  '终止侦查报告': '#2c5f2d',
  '呈请报告书': '#b85c1a',
  '行政案件卷宗目录': '#6b3a8b',
  '涉案财物清单': '#0d9488',
};

export default function DashboardPage() {
  const navigate = useNavigate();
  const { stats, loading } = useHistoryStats();
  const { models, currentModelId } = useAppContext();
  const [apiStatus, setApiStatus] = useState<'ok' | 'error' | 'checking'>('checking');
  const [apiLatency, setApiLatency] = useState<number>(0);

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      const t0 = performance.now();
      try {
        await client.get('/health');
        if (!cancelled) {
          setApiStatus('ok');
          setApiLatency(Math.round(performance.now() - t0));
        }
      } catch {
        if (!cancelled) setApiStatus('error');
      }
    };
    check();
    return () => { cancelled = true; };
  }, []);

  const currentModel = models.find((m) => m.id === currentModelId);
  const maxTrend = Math.max(1, ...stats.dailyTrend);
  const sortedTypes = Object.entries(stats.typeBreakdown)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 6);

  return (
    <div className="p-5 page-enter max-w-[1400px] mx-auto">
      <h2 className="text-lg font-bold text-slate-800 mb-5 flex items-center gap-2">
        <ThunderboltOutlined className="text-gold-500" />
        工作台
      </h2>

      {/* 统计卡片 + 7日趋势 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={8}>
          <Card
            className="stat-card rounded-xl shadow-sm border-0 cursor-pointer hover:shadow-md transition-all"
            onClick={() => navigate('/history')}
            hoverable
            loading={loading}
          >
            <div className="flex items-start justify-between">
              <Statistic
                title={<span className="text-xs text-slate-500">历史文书总数</span>}
                value={stats.total}
                prefix={<FileTextOutlined className="text-police-500" />}
                valueStyle={{ fontSize: 28, fontWeight: 700, color: '#1a3a5c' }}
              />
              {stats.recent > 0 && (
                <Tag color="blue" className="text-[10px] flex items-center gap-0.5">
                  <ArrowUpOutlined /> 近7天 +{stats.recent}
                </Tag>
              )}
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card
            className="stat-card rounded-xl shadow-sm border-0 cursor-pointer hover:shadow-md transition-all"
            hoverable
            loading={loading}
          >
            <Statistic
              title={<span className="text-xs text-slate-500">近 7 天生成</span>}
              value={stats.recent}
              prefix={<ClockCircleOutlined className="text-blue-500" />}
              valueStyle={{ fontSize: 28, fontWeight: 700, color: '#1e4470' }}
            />
            {/* Sparkline 迷你趋势图 */}
            {stats.dailyTrend.length > 0 && (
              <div className="mt-2 flex items-end gap-0.5 h-8">
                {stats.dailyTrend.map((count, i) => (
                  <div
                    key={i}
                    className="flex-1 rounded-sm transition-all duration-500"
                    style={{
                      height: `${Math.max(4, (count / maxTrend) * 100)}%`,
                      background: count > 0
                        ? 'linear-gradient(180deg, #1a3a5c 0%, #3b82f6 100%)'
                        : '#e2e8f0',
                      opacity: count > 0 ? 0.85 : 0.4,
                    }}
                    title={`${6 - i} 天前: ${count} 份`}
                  />
                ))}
              </div>
            )}
            <div className="flex justify-between mt-1">
              <Text className="text-[9px] text-slate-300">7天前</Text>
              <Text className="text-[9px] text-slate-300">今天</Text>
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card
            className="stat-card rounded-xl shadow-sm border-0"
            hoverable
            loading={loading}
          >
            <Statistic
              title={<span className="text-xs text-slate-500">涵盖文书类型</span>}
              value={stats.types}
              prefix={<CheckCircleOutlined className="text-green-500" />}
              valueStyle={{ fontSize: 28, fontWeight: 700, color: '#2c5f2d' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 系统状态 */}
      <Row gutter={[16, 16]} className="mt-4">
        <Col xs={24} sm={8}>
          <Card size="small" className="rounded-xl shadow-sm border-0">
            <div className="flex items-center gap-2">
              <ApiOutlined className="text-police-500" />
              <Text className="text-xs font-medium text-slate-600">API 服务</Text>
              <Tooltip title={apiStatus === 'ok' ? `延迟 ${apiLatency}ms` : '不可用'}>
                {apiStatus === 'ok'
                  ? <CheckCircleFilled className="text-green-500 text-xs" />
                  : apiStatus === 'error'
                    ? <CloseCircleFilled className="text-red-500 text-xs" />
                    : <Text className="text-[10px] text-slate-400">检测中...</Text>
                }
              </Tooltip>
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card size="small" className="rounded-xl shadow-sm border-0">
            <div className="flex items-center gap-2">
              <RobotOutlined className="text-police-500" />
              <Text className="text-xs font-medium text-slate-600">当前模型</Text>
              <Tag color="blue" className="text-[10px] leading-tight">
                {currentModel?.name || '未配置'}
              </Tag>
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card size="small" className="rounded-xl shadow-sm border-0">
            <div className="flex items-center gap-2">
              <ThunderboltOutlined className="text-amber-500" />
              <Text className="text-xs font-medium text-slate-600">平均耗时</Text>
              <Text className="text-xs text-slate-500">
                {stats.recentItems.length > 0
                  ? `${Math.round(stats.recentItems.reduce((s, i) => s + (i.latency_ms || 0), 0) / stats.recentItems.length)}ms`
                  : '暂无数据'}
              </Text>
            </div>
          </Card>
        </Col>
      </Row>

      {/* 文书类型分布 + 最近活动 */}
      <Row gutter={[16, 16]} className="mt-4">
        <Col xs={24} lg={14}>
          <Card
            size="small"
            title={<span className="text-sm font-semibold text-slate-700">文书类型分布</span>}
            className="rounded-xl shadow-sm border-0"
            loading={loading}
          >
            {sortedTypes.length === 0 ? (
              <div className="text-center py-6 text-xs text-slate-400">暂无数据</div>
            ) : (
              <div className="space-y-2.5">
                {sortedTypes.map(([type, count]) => {
                  const pct = stats.total > 0 ? Math.round((count / stats.total) * 100) : 0;
                  return (
                    <div key={type} className="flex items-center gap-2">
                      <Text className="text-xs text-slate-600 w-[120px] flex-shrink-0 truncate" title={type}>
                        {type}
                      </Text>
                      <div className="flex-1 h-4 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-700"
                          style={{
                            width: `${Math.max(2, pct)}%`,
                            background: TYPE_COLORS[type] || '#64748b',
                          }}
                        />
                      </div>
                      <Text className="text-xs text-slate-400 w-8 text-right flex-shrink-0">
                        {count}
                      </Text>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card
            size="small"
            title={
              <span className="text-sm font-semibold text-slate-700 flex items-center gap-1.5">
                <HistoryOutlined className="text-police-500" />
                最近活动
              </span>
            }
            className="rounded-xl shadow-sm border-0"
            loading={loading}
          >
            {stats.recentItems.length === 0 ? (
              <div className="text-center py-6 text-xs text-slate-400">暂无记录</div>
            ) : (
              <div className="space-y-2">
                {stats.recentItems.map((item) => (
                  <div
                    key={item.id}
                    className="flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-slate-50 cursor-pointer transition-colors group"
                    onClick={() => navigate(`/history`)}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <div
                        className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                        style={{ background: TYPE_COLORS[item.doc_type] || '#94a3b8' }}
                      />
                      <Text className="text-xs text-slate-700 truncate">
                        {item.doc_type || '未分类'}
                      </Text>
                    </div>
                    <Text className="text-[10px] text-slate-400 flex-shrink-0 ml-2 group-hover:text-slate-600">
                      {formatRelativeTime(item.created_at)}
                    </Text>
                  </div>
                ))}
                <Divider className="my-1" />
                <div
                  className="text-center text-xs text-police-500 cursor-pointer hover:text-police-700 py-1"
                  onClick={() => navigate('/history')}
                >
                  查看全部 <RightOutlined className="text-[10px]" />
                </div>
              </div>
            )}
          </Card>
        </Col>
      </Row>

      {/* 快捷操作 */}
      <h3 className="text-sm font-semibold text-slate-600 mt-5 mb-3">快捷操作</h3>
      <Row gutter={[12, 12]}>
        {QUICK_ACTIONS.map((action) => (
          <Col xs={24} sm={12} md={8} lg={24 / 5} key={action.path}>
            <Card
              hoverable
              className="quick-action-btn rounded-xl shadow-sm border-slate-100"
              onClick={() => navigate(action.path)}
              styles={{ body: { padding: '18px 16px' } }}
            >
              <div className="flex items-center gap-3">
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ background: `${action.color}12`, color: action.color }}
                >
                  <span className="text-lg">{action.icon}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-slate-700">{action.title}</div>
                  <div className="text-xs text-slate-400 mt-0.5">{action.desc}</div>
                </div>
                <RightOutlined className="text-slate-300 text-xs" />
              </div>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
}

function formatRelativeTime(iso: string): string {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return '刚刚';
  if (mins < 60) return `${mins} 分钟前`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} 天前`;
  return `${Math.floor(days / 30)} 月前`;
}
