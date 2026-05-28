/** 模板浏览器 —— 分类树 + 卡片列表 + 详情抽屉 */
import { useState, useEffect, useCallback } from 'react';
import { Input, Card, Empty, Drawer, Tag, Typography, Descriptions, App } from 'antd';
import {
  SearchOutlined, FileTextOutlined, EyeOutlined, CopyOutlined,
  FolderOutlined, TagsOutlined, DownloadOutlined,
} from '@ant-design/icons';
import client from '../../api/client';
import type { TemplateInfo, TemplateDetail, TemplateCategory } from '../../types';

const { Text, Paragraph } = Typography;

export default function TemplateBrowser() {
  const { message } = App.useApp();
  const [tree, setTree] = useState<TemplateCategory[]>([]);
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCat, setSelectedCat] = useState('');
  const [selectedSubcat, setSelectedSubcat] = useState('');
  const [keyword, setKeyword] = useState('');
  const [selectedTpl, setSelectedTpl] = useState<TemplateDetail | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const loadTree = useCallback(async () => {
    try {
      const { data } = await client.get('/knowledge/template-categories');
      setTree(data.categories || []);
    } catch { /* ignore */ }
  }, []);

  const loadTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = {};
      if (selectedCat) params.category = selectedCat;
      if (selectedSubcat) params.subcategory = selectedSubcat;
      if (keyword) params.keyword = keyword;
      params.page_size = 100;

      const { data } = await client.get('/knowledge/templates', { params });
      setTemplates(data.templates || []);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  }, [selectedCat, selectedSubcat, keyword]);

  useEffect(() => { loadTree(); }, [loadTree]);
  useEffect(() => { loadTemplates(); }, [loadTemplates]);

  const openDetail = async (tpl: TemplateInfo) => {
    try {
      const { data } = await client.get(`/knowledge/templates/${encodeURIComponent(tpl.doc_type)}`);
      setSelectedTpl(data);
      setDrawerOpen(true);
    } catch {
      message.error('获取模板详情失败');
    }
  };

  const handleDownload = async (tpl: TemplateInfo | TemplateDetail) => {
    try {
      const catParam = tpl.category ? `&category=${encodeURIComponent(tpl.category)}` : '';
      const response = await client.get(
        `/knowledge/templates/${encodeURIComponent(tpl.doc_type)}/download?${catParam}`,
        { responseType: 'blob' },
      );
      const blob = new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${tpl.doc_type}.docx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      message.success(`已下载「${tpl.doc_type}」`);
    } catch {
      message.error('下载失败');
    }
  };

  const subCategories = selectedCat
    ? tree.find(c => c.name === selectedCat)?.children || []
    : [];

  return (
    <div className="flex gap-4 h-full min-h-0">
      {/* 左侧分类树 */}
      <div className="w-56 flex-shrink-0 bg-white rounded-xl shadow-sm border border-slate-100 p-3 overflow-auto">
        <div className="text-xs font-bold text-slate-500 mb-2 flex items-center gap-1">
          <FolderOutlined /> 分类筛选
        </div>

        {/* 全部分类 */}
        <div
          className={`px-2 py-1.5 rounded-lg cursor-pointer text-sm mb-1 transition-colors ${
            !selectedCat ? 'bg-police-50 text-police-700 font-bold' : 'text-slate-600 hover:bg-slate-50'
          }`}
          onClick={() => { setSelectedCat(''); setSelectedSubcat(''); }}
        >
          全部模板 ({tree.reduce((s, c) => s + c.count, 0)})
        </div>

        {tree.map(cat => (
          <div key={cat.name} className="mb-1">
            <div
              className={`px-2 py-1.5 rounded-lg cursor-pointer text-sm transition-colors flex items-center justify-between ${
                selectedCat === cat.name ? 'bg-police-50 text-police-700 font-bold' : 'text-slate-600 hover:bg-slate-50'
              }`}
              onClick={() => {
                setSelectedCat(selectedCat === cat.name ? '' : cat.name);
                setSelectedSubcat('');
              }}
            >
              <span>{cat.name}</span>
              <Tag className="text-xs scale-75">{cat.count}</Tag>
            </div>

            {selectedCat === cat.name && (cat.children || []).map(sub => (
              <div
                key={sub.name}
                className={`pl-6 pr-2 py-1 rounded-lg cursor-pointer text-xs transition-colors ${
                  selectedSubcat === sub.name ? 'text-police-600 font-bold bg-police-50/50' : 'text-slate-500 hover:bg-slate-50'
                }`}
                onClick={(e) => { e.stopPropagation(); setSelectedSubcat(sub.name); }}
              >
                {sub.name} ({sub.count})
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* 右侧模板列表 */}
      <div className="flex-1 flex flex-col min-h-0 min-w-0">
        <Input
          prefix={<SearchOutlined className="text-slate-400" />}
          placeholder="搜索模板名称..."
          value={keyword}
          onChange={e => setKeyword(e.target.value)}
          allowClear
          className="mb-3 flex-shrink-0"
        />

        <div className="flex-1 overflow-auto">
          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <Card key={i} loading size="small" className="rounded-xl" />
              ))}
            </div>
          ) : templates.length === 0 ? (
            <Empty description="暂无匹配的模板" />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {templates.map(tpl => (
                <Card
                  key={tpl.doc_type}
                  size="small"
                  className="rounded-xl shadow-sm border-slate-100 hover:border-police-200 hover:shadow-md transition-all cursor-pointer"
                  onClick={() => openDetail(tpl)}
                >
                  <div className="flex items-start gap-2">
                    <FileTextOutlined className="text-police-400 mt-0.5 flex-shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-bold text-slate-700 truncate" title={tpl.name}>
                        {tpl.name || tpl.doc_type}
                      </div>
                      <div className="flex items-center gap-1 mt-1">
                        {tpl.category && <Tag color="blue" className="text-xs">{tpl.category}</Tag>}
                        {tpl.is_official && <Tag color="green" className="text-xs">官方</Tag>}
                      </div>
                      {tpl.description && (
                        <Text className="text-xs text-slate-400 line-clamp-2 mt-1 block">
                          {tpl.description}
                        </Text>
                      )}
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDownload(tpl); }}
                        className="text-slate-300 hover:text-police-500 transition-colors"
                        title="下载模板"
                      >
                        <DownloadOutlined />
                      </button>
                      <EyeOutlined className="text-slate-300" />
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 详情抽屉 */}
      <Drawer
        title={selectedTpl?.name || selectedTpl?.doc_type}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={640}
        extra={
          selectedTpl && (
            <div className="flex items-center gap-3">
              <button
                onClick={() => handleDownload(selectedTpl)}
                className="text-police-500 hover:text-police-700 transition-colors"
              >
                <DownloadOutlined /> 下载 .docx
              </button>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(selectedTpl.template_text || '').then(() => message.success('模板文本已复制'));
                }}
                className="text-slate-400 hover:text-slate-600 transition-colors"
              >
                <CopyOutlined /> 复制
              </button>
            </div>
          )
        }
      >
        {selectedTpl && (
          <div className="space-y-4">
            <Descriptions size="small" column={2} bordered>
              <Descriptions.Item label="文书类型">{selectedTpl.doc_type}</Descriptions.Item>
              <Descriptions.Item label="分类">
                <Tag>{selectedTpl.category}</Tag>
                {selectedTpl.subcategory && <Tag color="blue">{selectedTpl.subcategory}</Tag>}
              </Descriptions.Item>
              <Descriptions.Item label="官方模板">
                {selectedTpl.is_official ? <Tag color="green">是</Tag> : <Tag>否</Tag>}
              </Descriptions.Item>
              <Descriptions.Item label="版本">v{selectedTpl.version}</Descriptions.Item>
              {selectedTpl.description && (
                <Descriptions.Item label="用途" span={2}>{selectedTpl.description}</Descriptions.Item>
              )}
            </Descriptions>

            {selectedTpl.schema_fields && selectedTpl.schema_fields.length > 0 && (
              <div>
                <Text strong className="text-sm flex items-center gap-1 mb-2">
                  <TagsOutlined /> 字段定义 ({selectedTpl.schema_fields.length})
                </Text>
                <div className="flex flex-wrap gap-1">
                  {selectedTpl.schema_fields.map((f, i) => (
                    <Tag key={i} className="text-xs" color={f.required ? 'blue' : 'default'}>
                      {f.label}{f.required ? ' *' : ''}
                    </Tag>
                  ))}
                </div>
              </div>
            )}

            {selectedTpl.template_text && (
              <div>
                <Text strong className="text-sm">模板文本</Text>
                <div className="mt-1 p-3 bg-slate-50 rounded-lg border border-slate-100 text-xs font-mono whitespace-pre-wrap max-h-96 overflow-auto leading-relaxed">
                  {selectedTpl.template_text}
                </div>
              </div>
            )}

            {selectedTpl.usage_guide && (
              <div>
                <Text strong className="text-sm">填写说明</Text>
                <Paragraph className="mt-1 text-xs text-slate-600 leading-relaxed whitespace-pre-wrap">
                  {selectedTpl.usage_guide}
                </Paragraph>
              </div>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
}
