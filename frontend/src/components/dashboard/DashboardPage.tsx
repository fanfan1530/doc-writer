/** 工作台首页 —— 统计概览 + 快捷入口 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Statistic, Row, Col, Skeleton, Tag, Alert } from 'antd';
import {
  FileTextOutlined, RobotOutlined, SearchOutlined,
  SafetyCertificateOutlined, BookOutlined, ClockCircleOutlined,
  ThunderboltOutlined, RightOutlined, CheckCircleOutlined,
} from '@ant-design/icons';
import client from '../../api/client';

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

export default function DashboardPage() {
  const navigate = useNavigate();
  const [stats, setStats] = useState({ total: 0, recent: 0, types: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await client.get('/generation/history?limit=50');
        const items = data.history || [];
        const types = new Set(items.map((h: { doc_type: string }) => h.doc_type));
        setStats({
          total: items.length,
          recent: items.filter((h: { created_at: string }) => {
            const d = new Date(h.created_at);
            return (Date.now() - d.getTime()) < 7 * 24 * 3600 * 1000;
          }).length,
          types: types.size,
        });
      } catch { /* use defaults */ } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="p-5 page-enter max-w-[1400px] mx-auto">
      <h2 className="text-lg font-bold text-slate-800 mb-5 flex items-center gap-2">
        <ThunderboltOutlined className="text-gold-500" />
        工作台
      </h2>

      {/* 统计卡片 */}
      {loading ? (
        <Row gutter={[16, 16]}>
          {[1, 2, 3].map((i) => (
            <Col xs={24} sm={8} key={i}><Card><Skeleton active paragraph={{ rows: 1 }} /></Card></Col>
          ))}
        </Row>
      ) : (
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={8}>
            <Card
              className="stat-card rounded-xl shadow-sm border-0 cursor-pointer hover:shadow-md transition-all"
              onClick={() => navigate('/history')}
              hoverable
            >
              <Statistic
                title={<span className="text-xs text-slate-500">历史文书总数 <RightOutlined className="text-[10px] text-slate-300 ml-0.5" /></span>}
                value={stats.total}
                prefix={<FileTextOutlined className="text-police-500" />}
                valueStyle={{ fontSize: 28, fontWeight: 700, color: '#1a3a5c' }}
              />
            </Card>
          </Col>
          <Col xs={24} sm={8}>
            <Card
              className="stat-card rounded-xl shadow-sm border-0 cursor-pointer hover:shadow-md transition-all"
              onClick={() => navigate('/history?filter=recent')}
              hoverable
            >
              <Statistic
                title={<span className="text-xs text-slate-500">近 7 天生成 <RightOutlined className="text-[10px] text-slate-300 ml-0.5" /></span>}
                value={stats.recent}
                prefix={<ClockCircleOutlined className="text-blue-500" />}
                valueStyle={{ fontSize: 28, fontWeight: 700, color: '#1e4470' }}
              />
            </Card>
          </Col>
          <Col xs={24} sm={8}>
            <Card
              className="stat-card rounded-xl shadow-sm border-0 cursor-pointer hover:shadow-md transition-all"
              onClick={() => navigate('/history')}
              hoverable
            >
              <Statistic
                title={<span className="text-xs text-slate-500">涵盖文书类型 <RightOutlined className="text-[10px] text-slate-300 ml-0.5" /></span>}
                value={stats.types}
                prefix={<CheckCircleOutlined className="text-green-500" />}
                valueStyle={{ fontSize: 28, fontWeight: 700, color: '#2c5f2d' }}
              />
            </Card>
          </Col>
        </Row>
      )}

      {/* 快捷操作 */}
      <h3 className="text-sm font-semibold text-slate-600 mt-6 mb-3">快捷操作</h3>
      <Row gutter={[12, 12]}>
        {QUICK_ACTIONS.map((action) => (
          <Col xs={24} sm={12} md={8} lg={24 / 5} key={action.path}>
            <Card
              hoverable
              className="quick-action-btn rounded-xl shadow-sm border-slate-100"
              onClick={() => navigate(action.path)}
              bodyStyle={{ padding: '18px 16px' }}
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

      {/* 系统提示 */}
      <Alert
        type="info"
        showIcon
        icon={<ThunderboltOutlined />}
        message="智慧警务智能工作台 v2.0"
        description="本系统提供 AI 驱动的文书生成、类案检索、案件分析等功能，所有数据均存储于本地，确保信息安全。如有功能建议或问题反馈，请联系系统管理员。"
        className="mt-5 rounded-xl border-police-100"
        style={{ background: 'linear-gradient(135deg, rgba(26,58,92,0.02) 0%, rgba(30,68,112,0.04) 100%)' }}
      />
    </div>
  );
}
