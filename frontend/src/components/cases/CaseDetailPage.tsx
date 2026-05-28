/** 案件详情页 —— 基本信息 + 状态时间线 + 关联文书 + 证据 + 审查历史。 */
import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Descriptions, Timeline, Table, Tag, Button, Select, App, Typography, Space, Popconfirm, Spin } from 'antd';
import { ArrowLeftOutlined, ReloadOutlined } from '@ant-design/icons';
import client from '../../api/client';
import CaseStatusBadge from './CaseStatusBadge';
import type { CaseDetail, DBCase } from '../../types';

const { Title, Text, Paragraph } = Typography;

const TRANSITIONS: Record<string, string[]> = {
  FILING: ['INVESTIGATING'],
  INVESTIGATING: ['REVIEWING', 'FILING'],
  REVIEWING: ['APPROVED', 'INVESTIGATING'],
  APPROVED: ['CLOSED', 'REVIEWING'],
  CLOSED: ['ARCHIVED', 'INVESTIGATING'],
  ARCHIVED: [],
};

const STATUS_TRANSITION_LABELS: Record<string, string> = {
  INVESTIGATING: '转入侦查',
  REVIEWING: '提交审核',
  APPROVED: '批准',
  CLOSED: '结案',
  ARCHIVED: '归档',
  FILING: '退回补充侦查',
};

export default function CaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [caseData, setCaseData] = useState<CaseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [transitioning, setTransitioning] = useState(false);

  const fetchDetail = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await client.get(`/cases/db/${id}`);
      setCaseData(data);
    } catch {
      message.error('获取案件详情失败');
    } finally {
      setLoading(false);
    }
  }, [id, message]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  const handleTransition = async (targetStatus: string) => {
    setTransitioning(true);
    try {
      await client.post(`/cases/db/${id}/transition`, { target_status: targetStatus, comment: '' });
      message.success('状态流转成功');
      fetchDetail();
    } catch {
      message.error('状态流转失败');
    } finally {
      setTransitioning(false);
    }
  };

  if (loading) return <div className="flex items-center justify-center h-full"><Spin size="large" /></div>;
  if (!caseData) return <div className="p-6 text-center text-slate-400">案件不存在</div>;

  const availableTransitions = TRANSITIONS[caseData.status] || [];

  const docColumns = [
    { title: '文书标题', dataIndex: 'title', key: 'title', width: 200 },
    { title: '类型', dataIndex: 'doc_type', key: 'doc_type', width: 100, render: (t: string) => <Tag>{t}</Tag> },
    { title: '状态', dataIndex: 'status', key: 'status', width: 100,
      render: (s: string) => {
        const map: Record<string, { color: string; label: string }> = {
          DRAFT: { color: 'default', label: '草稿' },
          SUBMITTED: { color: 'processing', label: '已提交' },
          APPROVED: { color: 'green', label: '已批准' },
          REJECTED: { color: 'red', label: '已驳回' },
        };
        const info = map[s] || { color: 'default', label: s };
        return <Tag color={info.color}>{info.label}</Tag>;
      },
    },
  ];

  return (
    <div className="p-6 h-full overflow-auto">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-4">
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/cases')}>返回</Button>
            <Title level={4} className="!mb-0">{caseData.title}</Title>
            <CaseStatusBadge status={caseData.status} />
          </Space>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={fetchDetail}>刷新</Button>
            {availableTransitions.length > 0 && (
              <Space>
                <Select
                  size="small"
                  placeholder="状态流转..."
                  value={undefined}
                  onChange={handleTransition}
                  loading={transitioning}
                  className="w-36"
                  options={availableTransitions.map((t) => ({
                    label: STATUS_TRANSITION_LABELS[t] || t,
                    value: t,
                  }))}
                />
              </Space>
            )}
          </Space>
        </div>

        {/* 基本信息 */}
        <Card className="border-0 shadow-sm mb-4" title="基本信息">
          <Descriptions size="small" column={3}>
            <Descriptions.Item label="案件编号">{caseData.case_number}</Descriptions.Item>
            <Descriptions.Item label="案件类型"><Tag>{caseData.case_type}</Tag></Descriptions.Item>
            <Descriptions.Item label="状态"><CaseStatusBadge status={caseData.status} /></Descriptions.Item>
            <Descriptions.Item label="办案单位">{caseData.unit || '-'}</Descriptions.Item>
            <Descriptions.Item label="案发日期">{caseData.incident_date || '-'}</Descriptions.Item>
            <Descriptions.Item label="案发地点">{caseData.location || '-'}</Descriptions.Item>
            <Descriptions.Item label="创建时间">{caseData.created_at ? new Date(caseData.created_at).toLocaleString('zh-CN') : '-'}</Descriptions.Item>
            <Descriptions.Item label="更新时间">{caseData.updated_at ? new Date(caseData.updated_at).toLocaleString('zh-CN') : '-'}</Descriptions.Item>
          </Descriptions>
          {caseData.description && (
            <div className="mt-3">
              <Text className="text-xs text-slate-500">案情描述</Text>
              <Paragraph className="mt-1 text-sm">{caseData.description}</Paragraph>
            </div>
          )}
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* 时间线 */}
          <Card className="border-0 shadow-sm" title="案件时间线">
            {caseData.timeline.length > 0 ? (
              <Timeline
                items={caseData.timeline.map((t) => ({
                  children: (
                    <div>
                      <div className="font-medium text-sm">{t.event}</div>
                      <div className="text-xs text-slate-500">{t.description}</div>
                      <div className="text-xs text-slate-400 mt-0.5">
                        {t.occurred_at ? new Date(t.occurred_at).toLocaleString('zh-CN') : ''}
                      </div>
                    </div>
                  ),
                }))}
              />
            ) : (
              <Text className="text-slate-400 text-sm">暂无事件记录</Text>
            )}
          </Card>

          {/* 审查记录 */}
          <Card className="border-0 shadow-sm" title="审查记录">
            {caseData.reviews.length > 0 ? (
              <Table
                dataSource={caseData.reviews}
                rowKey="id"
                size="small"
                pagination={false}
                columns={[
                  {
                    title: '操作', dataIndex: 'action', key: 'action', width: 80,
                    render: (a: string) => {
                      const map: Record<string, { color: string; label: string }> = {
                        APPROVE: { color: 'green', label: '通过' },
                        REJECT: { color: 'red', label: '驳回' },
                        RETURN: { color: 'orange', label: '退回' },
                      };
                      const info = map[a] || { color: 'default', label: a };
                      return <Tag color={info.color}>{info.label}</Tag>;
                    },
                  },
                  { title: '意见', dataIndex: 'comment', key: 'comment', width: 200 },
                  {
                    title: '时间', dataIndex: 'created_at', key: 'created_at', width: 140,
                    render: (t: string) => t ? new Date(t).toLocaleString('zh-CN') : '-',
                  },
                ]}
              />
            ) : (
              <Text className="text-slate-400 text-sm">暂无审查记录</Text>
            )}
          </Card>
        </div>

        {/* 关联文书 */}
        <Card className="border-0 shadow-sm mt-4" title="关联文书">
          <Table
            dataSource={caseData.documents}
            rowKey="id"
            size="small"
            pagination={false}
            columns={docColumns}
          />
        </Card>
      </div>
    </div>
  );
}
