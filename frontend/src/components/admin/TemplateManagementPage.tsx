/** 模板管理页面 —— 管理员浏览、启用/禁用模板。 */

import { useState, useEffect, useCallback } from 'react';
import {
  Card, Table, Input, Select, Tag, Switch, Space, Tooltip,
  Typography, App, Popconfirm, Button,
} from 'antd';
import {
  SearchOutlined, ReloadOutlined, FileTextOutlined,
  DownloadOutlined,
} from '@ant-design/icons';
import client from '../../api/client';
import type { TemplateInfo, TemplateCategory } from '../../types';

const { Text } = Typography;

const PAGE_SIZE = 20;

export default function TemplateManagementPage() {
  const { message } = App.useApp();
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState('');
  const [category, setCategory] = useState('');
  const [subcategory, setSubcategory] = useState('');
  const [categories, setCategories] = useState<TemplateCategory[]>([]);

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('page_size', String(PAGE_SIZE));
      if (keyword) params.set('keyword', keyword);
      if (category) params.set('category', category);
      if (subcategory) params.set('subcategory', subcategory);

      const { data } = await client.get(`/knowledge/templates?${params}`);
      setTemplates(data.templates || []);
      setTotal(data.total || 0);
    } catch {
      message.error('加载模板列表失败');
    } finally {
      setLoading(false);
    }
  }, [page, keyword, category, subcategory, message]);

  const fetchCategories = useCallback(async () => {
    try {
      const { data } = await client.get('/knowledge/template-categories');
      setCategories(data.categories || []);
    } catch {
      // silent
    }
  }, []);

  useEffect(() => { fetchCategories(); }, [fetchCategories]);
  useEffect(() => { fetchTemplates(); }, [fetchTemplates]);

  const handleToggle = async (docType: string, cat: string) => {
    try {
      await client.put(`/knowledge/templates/${encodeURIComponent(docType)}/toggle?category=${encodeURIComponent(cat)}`);
      message.success(`已切换「${docType}」状态`);
      fetchTemplates();
    } catch {
      message.error('操作失败');
    }
  };

  const handleDownload = async (docType: string, cat: string) => {
    try {
      const catParam = cat ? `category=${encodeURIComponent(cat)}` : '';
      const response = await client.get(
        `/knowledge/templates/${encodeURIComponent(docType)}/download?${catParam}`,
        { responseType: 'blob' },
      );
      const blob = new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${docType}.docx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      message.success(`已下载「${docType}」`);
    } catch {
      message.error('下载失败');
    }
  };

  const columns = [
    {
      title: '文书名称', dataIndex: 'doc_type', key: 'doc_type',
      render: (text: string, record: TemplateInfo) => (
        <Space>
          <FileTextOutlined className="text-slate-400" />
          <Text strong>{text}</Text>
          {record.is_official && <Tag color="green" className="text-[10px]">官方</Tag>}
        </Space>
      ),
    },
    {
      title: '类别', key: 'category', width: 100,
      render: (_: unknown, r: TemplateInfo) => (
        <Tag color={r.category === '刑事' ? 'red' : 'blue'}>{r.category}</Tag>
      ),
    },
    {
      title: '子分类', dataIndex: 'subcategory', key: 'subcategory', width: 100,
      render: (v: string) => v ? <Tag>{v}</Tag> : <span className="text-slate-300">-</span>,
    },
    {
      title: '版本', dataIndex: 'version', key: 'version', width: 60,
    },
    {
      title: '状态', key: 'status', width: 80,
      render: (_: unknown, r: TemplateInfo & { is_active?: boolean }) => (
        <Popconfirm
          title={`确认${r.is_active !== false ? '禁用' : '启用'}「${r.doc_type}」？`}
          onConfirm={() => handleToggle(r.doc_type, r.category)}
        >
          <Switch
            size="small"
            checked={r.is_active !== false}
            loading={false}
          />
        </Popconfirm>
      ),
    },
    {
      title: '下载', key: 'download', width: 60,
      render: (_: unknown, r: TemplateInfo) => (
        <Button
          type="text"
          size="small"
          icon={<DownloadOutlined />}
          onClick={() => handleDownload(r.doc_type, r.category)}
        />
      ),
    },
  ];

  const subcategories = category
    ? categories.find((c) => c.name === category)?.children?.map((s) => s.name) || []
    : [];

  return (
    <div className="h-full flex flex-col p-4 page-enter min-h-0">
      <div className="flex items-center justify-between mb-3 flex-shrink-0">
        <div>
          <Text strong className="text-lg">模板管理</Text>
          <Text type="secondary" className="ml-2 text-sm">
            共 {total} 个模板
          </Text>
        </div>
        <Button icon={<ReloadOutlined />} onClick={fetchTemplates} size="small">
          刷新
        </Button>
      </div>

      <Card size="small" className="mb-3 flex-shrink-0">
        <Space wrap>
          <Input
            prefix={<SearchOutlined />}
            placeholder="搜索模板名称..."
            value={keyword}
            onChange={(e) => { setKeyword(e.target.value); setPage(1); }}
            style={{ width: 240 }}
            allowClear
            size="small"
          />
          <Select
            placeholder="类别"
            value={category || undefined}
            onChange={(v) => { setCategory(v || ''); setSubcategory(''); setPage(1); }}
            style={{ width: 100 }}
            allowClear
            size="small"
            options={categories.map((c) => ({ label: `${c.name} (${c.count})`, value: c.name }))}
          />
          {subcategories.length > 0 && (
            <Select
              placeholder="子分类"
              value={subcategory || undefined}
              onChange={(v) => { setSubcategory(v || ''); setPage(1); }}
              style={{ width: 120 }}
              allowClear
              size="small"
              options={subcategories.map((s) => ({ label: s, value: s }))}
            />
          )}
        </Space>
      </Card>

      <Card size="small" className="flex-1 min-h-0 overflow-auto">
        <Table
          columns={columns}
          dataSource={templates}
          rowKey={(r) => `${r.category}:${r.doc_type}`}
          loading={loading}
          size="small"
          pagination={{
            current: page,
            pageSize: PAGE_SIZE,
            total,
            showTotal: (t) => `共 ${t} 个`,
            onChange: (p) => setPage(p),
            showSizeChanger: false,
          }}
          scroll={{ y: 'calc(100vh - 320px)' }}
        />
      </Card>
    </div>
  );
}
