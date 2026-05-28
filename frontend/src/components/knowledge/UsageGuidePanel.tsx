/** 填写规范面板 —— 搜索模板的使用说明和填写规则 */
import { useState, useEffect, useCallback } from 'react';
import { Input, Card, Empty, Tag, Typography, Select, App } from 'antd';
import { SearchOutlined, FileTextOutlined, ReadOutlined } from '@ant-design/icons';
import client from '../../api/client';
import type { TemplateInfo } from '../../types';

const { Text, Paragraph } = Typography;

export default function UsageGuidePanel() {
  const { message } = App.useApp();
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [guides, setGuides] = useState<{ doc_type: string; name: string; category: string; guide: string }[]>([]);
  const [keyword, setKeyword] = useState('');
  const [loading, setLoading] = useState(true);

  // Load all templates with usage guides
  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await client.get('/knowledge/templates', { params: { page_size: 200 } });
      const allTpl = (data.templates || []) as TemplateInfo[];
      setTemplates(allTpl);

      // Fetch detail for templates that have usage guides
      const withGuides: typeof guides = [];
      for (const tpl of allTpl) {
        try {
          const { data: detail } = await client.get(`/knowledge/templates/${encodeURIComponent(tpl.doc_type)}`);
          if (detail.usage_guide?.trim()) {
            withGuides.push({
              doc_type: tpl.doc_type,
              name: tpl.name || tpl.doc_type,
              category: tpl.category || '',
              guide: detail.usage_guide,
            });
          }
        } catch { /* skip */ }
      }
      setGuides(withGuides);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  const filtered = keyword
    ? guides.filter(g =>
        g.name.includes(keyword) ||
        g.guide.includes(keyword) ||
        g.category.includes(keyword)
      )
    : guides;

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center gap-3 mb-3 flex-shrink-0">
        <Input
          prefix={<SearchOutlined className="text-slate-400" />}
          placeholder="搜索填写规范、使用说明..."
          value={keyword}
          onChange={e => setKeyword(e.target.value)}
          allowClear
          className="max-w-md"
        />
        <Text className="text-xs text-slate-400 flex-shrink-0">
          {filtered.length} / {guides.length} 份规范
        </Text>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} loading size="small" className="rounded-xl" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <Empty description={guides.length === 0 ? '暂无填写规范数据，请先导入官方模板' : '未找到匹配的规范'} />
      ) : (
        <div className="flex-1 overflow-auto">
          <div className="grid grid-cols-1 gap-3">
            {filtered.map(g => (
              <Card
                key={g.doc_type}
                size="small"
                className="rounded-xl shadow-sm border-slate-100"
              >
                <div className="flex items-center gap-2 mb-2">
                  <ReadOutlined className="text-police-400" />
                  <Text strong className="text-sm">{g.name}</Text>
                  <Tag color="blue" className="text-xs">{g.category}</Tag>
                </div>
                <Paragraph
                  className="text-xs text-slate-600 leading-relaxed whitespace-pre-wrap mb-0"
                  ellipsis={{ rows: 4, expandable: true, symbol: '展开全部' }}
                >
                  {g.guide}
                </Paragraph>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
