/** 数据分析仪表盘 —— 统计卡片 + 趋势图 + 类型分布 + 警员绩效排名 + 文书统计。 */
import { useEffect, useState, useCallback } from 'react';
import { Card, Col, Row, Statistic, Table, Typography, App, Spin, Tag, Empty } from 'antd';
import {
  FileTextOutlined, UserOutlined, CheckCircleOutlined, ThunderboltOutlined,
} from '@ant-design/icons';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, PieChart, Pie, Cell, Legend,
} from 'recharts';
import client from '../../api/client';

const { Title, Text } = Typography;

const COLORS = ['#1a3a5c', '#d4a853', '#4caf50', '#f44336', '#2196f3', '#ff9800', '#9c27b0'];

interface OverviewData {
  total_cases: number;
  total_documents: number;
  total_users: number;
  closed_rate: number;
  month_new_cases: number;
  month_new_docs: number;
}

interface TrendData {
  by_month: { month: string; count: number }[];
  by_type: { type: string; count: number }[];
  by_status: { status: string; label: string; count: number }[];
}

interface OfficerStats {
  officer_id: number;
  username: string;
  display_name: string;
  unit: string;
  case_count: number;
}

interface DocTypeStats {
  doc_type: string;
  count: number;
  avg_latency_ms: number;
  total_tokens: number;
}

interface DocStats {
  by_type: DocTypeStats[];
  total_tokens: number;
}

export default function AnalyticsDashboard() {
  const { message } = App.useApp();
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [trends, setTrends] = useState<TrendData | null>(null);
  const [officers, setOfficers] = useState<OfficerStats[]>([]);
  const [docStats, setDocStats] = useState<DocStats | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [ovRes, trRes, ofRes, docRes] = await Promise.all([
        client.get('/analytics/overview'),
        client.get('/analytics/case-trends', { params: { months: 12 } }),
        client.get('/analytics/officer-stats', { params: { limit: 10 } }),
        client.get('/analytics/document-stats'),
      ]);
      setOverview(ovRes.data);
      setTrends(trRes.data);
      setOfficers(ofRes.data.officers || []);
      setDocStats(docRes.data);
    } catch {
      message.error('获取分析数据失败');
    } finally {
      setLoading(false);
    }
  }, [message]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  if (loading) return <div className="flex items-center justify-center h-full"><Spin size="large" /></div>;

  return (
    <div className="p-6 h-full overflow-auto">
      <div className="max-w-7xl mx-auto">
        <Title level={4} className="!mb-4">数据分析仪表盘</Title>

        {/* 统计卡片 */}
        <Row gutter={[16, 16]} className="mb-6">
          <Col xs={12} sm={6}>
            <Card className="border-0 shadow-sm">
              <Statistic title="案件总数" value={overview?.total_cases || 0} prefix={<FileTextOutlined />} />
              <Text className="text-xs text-slate-400">本月新增 {overview?.month_new_cases || 0}</Text>
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card className="border-0 shadow-sm">
              <Statistic title="文书总数" value={overview?.total_documents || 0} prefix={<ThunderboltOutlined />} />
              <Text className="text-xs text-slate-400">本月生成 {overview?.month_new_docs || 0}</Text>
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card className="border-0 shadow-sm">
              <Statistic title="活跃用户" value={overview?.total_users || 0} prefix={<UserOutlined />} />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card className="border-0 shadow-sm">
              <Statistic
                title="结案率"
                value={overview?.closed_rate || 0}
                suffix="%"
                prefix={<CheckCircleOutlined />}
                valueStyle={{ color: (overview?.closed_rate || 0) > 50 ? '#3f8600' : '#cf1322' }}
              />
            </Card>
          </Col>
        </Row>

        {/* 趋势图 + 类型分布 */}
        <Row gutter={[16, 16]} className="mb-6">
          <Col xs={24} lg={16}>
            <Card className="border-0 shadow-sm" title="月度案件趋势">
              {trends?.by_month?.length ? (
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={trends.by_month}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" fontSize={12} />
                    <YAxis fontSize={12} allowDecimals={false} />
                    <Tooltip />
                    <Line type="monotone" dataKey="count" stroke="#1a3a5c" strokeWidth={2} name="案件数" />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <Empty description="暂无数据" />
              )}
            </Card>
          </Col>
          <Col xs={24} lg={8}>
            <Card className="border-0 shadow-sm" title="案件类型分布">
              {trends?.by_type?.length ? (
                <ResponsiveContainer width="100%" height={280}>
                  <PieChart>
                    <Pie
                      data={trends.by_type}
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      dataKey="count"
                      nameKey="type"
                      label={({ name, value }) => `${name} ${value}`}
                    >
                      {trends.by_type.map((_, i) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <Empty description="暂无数据" />
              )}
            </Card>
          </Col>
        </Row>

        {/* 案件状态分布 + 警员绩效 */}
        <Row gutter={[16, 16]} className="mb-6">
          <Col xs={24} lg={8}>
            <Card className="border-0 shadow-sm" title="案件状态分布">
              {trends?.by_status?.length ? (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={trends.by_status} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" fontSize={12} allowDecimals={false} />
                    <YAxis type="category" dataKey="label" width={70} fontSize={12} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#1a3a5c" name="案件数" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <Empty description="暂无数据" />
              )}
            </Card>
          </Col>
          <Col xs={24} lg={16}>
            <Card className="border-0 shadow-sm" title="警员办案绩效">
              <Table
                dataSource={officers}
                rowKey="officer_id"
                size="small"
                pagination={false}
                columns={[
                  { title: '警员', dataIndex: 'display_name', key: 'name', width: 120 },
                  { title: '单位', dataIndex: 'unit', key: 'unit', width: 140, render: (t: string) => t || '-' },
                  {
                    title: '办案数', dataIndex: 'case_count', key: 'count', width: 100,
                    render: (v: number, _: OfficerStats, i: number) => (
                      <Tag color={i < 3 ? 'gold' : 'default'}>{v} 件</Tag>
                    ),
                  },
                ]}
              />
            </Card>
          </Col>
        </Row>

        {/* 文书统计 */}
        <Row gutter={[16, 16]}>
          <Col span={24}>
            <Card className="border-0 shadow-sm" title="文书生成统计">
              {docStats?.by_type?.length ? (
                <Table
                  dataSource={docStats.by_type}
                  rowKey="doc_type"
                  size="small"
                  pagination={false}
                  columns={[
                    { title: '文书类型', dataIndex: 'doc_type', key: 'type', width: 160, render: (t: string) => <Tag>{t}</Tag> },
                    { title: '生成次数', dataIndex: 'count', key: 'count', width: 100 },
                    {
                      title: '平均耗时', dataIndex: 'avg_latency_ms', key: 'latency', width: 120,
                      render: (v: number) => `${(v / 1000).toFixed(1)}s`,
                    },
                    {
                      title: 'Token 用量', dataIndex: 'total_tokens', key: 'tokens', width: 120,
                      render: (v: number) => v > 1000 ? `${(v / 1000).toFixed(1)}k` : v,
                    },
                  ]}
                  summary={() => (
                    <Table.Summary.Row>
                      <Table.Summary.Cell index={0}><Text strong>合计</Text></Table.Summary.Cell>
                      <Table.Summary.Cell index={1}>
                        <Text strong>{docStats.by_type.reduce((s, d) => s + d.count, 0)}</Text>
                      </Table.Summary.Cell>
                      <Table.Summary.Cell index={2} />
                      <Table.Summary.Cell index={3}>
                        <Text strong>
                          {docStats.total_tokens > 1000
                            ? `${(docStats.total_tokens / 1000).toFixed(1)}k`
                            : docStats.total_tokens}
                        </Text>
                      </Table.Summary.Cell>
                    </Table.Summary.Row>
                  )}
                />
              ) : (
                <Empty description="暂无数据" />
              )}
            </Card>
          </Col>
        </Row>
      </div>
    </div>
  );
}
