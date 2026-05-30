import { Alert, Badge, Card, Empty, List, Tag } from 'antd';
import {
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  SafetyCertificateOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import type { GenerationResult } from '../../types';

interface RiskItem {
  level: 'high' | 'medium' | 'low';
  title: string;
  description: string;
}

interface Props {
  result: GenerationResult | null;
  elements: Record<string, string>;
}

export default function RiskCheckPanel({ result, elements }: Props) {
  const risks = buildRisks(result, elements);
  const highCount = risks.filter((risk) => risk.level === 'high').length;
  const mediumCount = risks.filter((risk) => risk.level === 'medium').length;

  return (
    <Card
      className="shadow-sm border-0 rounded-xl"
      styles={{ body: { padding: 14 } }}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-semibold text-slate-700 flex items-center gap-2">
          <SafetyCertificateOutlined className="text-police-500" />
          风险检查
        </div>
        <div className="flex items-center gap-2">
          {highCount > 0 && <Badge count={highCount} size="small" />}
          {mediumCount > 0 && <Tag color="warning" className="m-0">{mediumCount} 项提醒</Tag>}
          {risks.length === 0 && result?.content && <Tag color="success" className="m-0">未发现明显风险</Tag>}
        </div>
      </div>

      {!result ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={<span className="text-xs text-slate-400">生成文书后自动检查</span>}
        />
      ) : risks.length === 0 ? (
        <Alert
          type="success"
          showIcon
          icon={<CheckCircleOutlined />}
          message={<span className="text-xs">基础格式、要素完整性和常见日期逻辑未发现明显问题。</span>}
        />
      ) : (
        <List
          size="small"
          dataSource={risks}
          renderItem={(risk) => (
            <List.Item className="!px-0">
              <div className="flex gap-2 w-full">
                {risk.level === 'high'
                  ? <ExclamationCircleOutlined className="text-red-500 mt-0.5" />
                  : <WarningOutlined className="text-amber-500 mt-0.5" />}
                <div className="min-w-0">
                  <div className="text-xs font-medium text-slate-700">{risk.title}</div>
                  <div className="text-xs text-slate-500 mt-0.5 leading-relaxed">{risk.description}</div>
                </div>
              </div>
            </List.Item>
          )}
        />
      )}
    </Card>
  );
}

function buildRisks(result: GenerationResult | null, elements: Record<string, string>): RiskItem[] {
  if (!result) return [];
  const risks: RiskItem[] = [];
  const merged = { ...(result.elements || {}), ...elements };
  const content = result.content || '';

  if (!content.trim()) {
    risks.push({
      level: 'high',
      title: '文书内容为空',
      description: '当前没有生成有效正文，请补充案情或重新生成。',
    });
    return risks;
  }

  const placeholders = content.match(/{{\s*[\w.-]+\s*}}/g) || [];
  if (placeholders.length > 0) {
    risks.push({
      level: 'high',
      title: '存在未填充字段',
      description: `文书中还有 ${placeholders.length} 个模板字段未被填充，请补充要素后重新生成。`,
    });
  }

  const required = getRequiredHints(result.doc_type);
  for (const item of required) {
    if (!hasAny(merged, item.keys) && !item.keywords.some((keyword) => content.includes(keyword))) {
      risks.push({
        level: item.level,
        title: `${item.label}可能缺失`,
        description: `建议核对文书中是否已包含“${item.label}”，避免生成后仍需大量人工补录。`,
      });
    }
  }

  if (content.length < 120) {
    risks.push({
      level: 'medium',
      title: '正文偏短',
      description: '文书正文较短，可能缺少事实经过、证据或法律依据。',
    });
  }

  if (!/[《].+[》]/.test(content) && !(result.suggested_laws || []).length) {
    risks.push({
      level: 'medium',
      title: '法条依据不明显',
      description: '未识别到明确法条引用，建议补充处罚或处理依据。',
    });
  }

  const noticeDate = pickDate(merged, ['notice_date', '告知日期', 'notification_date']);
  const decisionDate = pickDate(merged, ['penalty_decision_date', '决定日期', '处罚决定日期']);
  if (noticeDate && decisionDate && noticeDate.getTime() > decisionDate.getTime()) {
    risks.push({
      level: 'high',
      title: '日期顺序异常',
      description: '告知日期晚于处罚决定日期，请核对程序时间。',
    });
  }

  return risks;
}

function getRequiredHints(docType: string) {
  const common = [
    { label: '时间', keys: ['case_time', 'case_date', '案发时间', '案发日期'], keywords: ['时间', '日期'], level: 'medium' as const },
    { label: '地点', keys: ['case_location', '案发地点', '地点'], keywords: ['地点'], level: 'medium' as const },
    { label: '当事人信息', keys: ['suspect_name', 'person_name', 'name', '姓名', '当事人'], keywords: ['姓名', '当事人'], level: 'medium' as const },
  ];
  if (docType.includes('行政处罚')) {
    return [
      ...common,
      { label: '违法事实', keys: ['illegal_fact', '违法事实'], keywords: ['违法事实'], level: 'high' as const },
      { label: '处罚内容', keys: ['penalty_content', '处罚内容'], keywords: ['处罚'], level: 'high' as const },
      { label: '权利告知', keys: ['rights_statement', '权利告知'], keywords: ['申请行政复议', '提起行政诉讼', '权利'], level: 'medium' as const },
    ];
  }
  return common;
}

function hasAny(source: Record<string, string>, keys: string[]): boolean {
  return keys.some((key) => {
    const direct = source[key];
    if (direct && String(direct).trim()) return true;
    const fuzzyKey = Object.keys(source).find((sourceKey) => sourceKey.includes(key));
    return !!(fuzzyKey && String(source[fuzzyKey]).trim());
  });
}

function pickDate(source: Record<string, string>, keys: string[]): Date | null {
  for (const key of keys) {
    const value = source[key] || source[Object.keys(source).find((sourceKey) => sourceKey.includes(key)) || ''];
    const parsed = parseDate(String(value || ''));
    if (parsed) return parsed;
  }
  return null;
}

function parseDate(value: string): Date | null {
  const match = value.match(/(\d{4})年(\d{1,2})月(\d{1,2})日|(\d{4})-(\d{1,2})-(\d{1,2})/);
  if (!match) return null;
  const year = Number(match[1] || match[4]);
  const month = Number(match[2] || match[5]);
  const day = Number(match[3] || match[6]);
  const date = new Date(year, month - 1, day);
  return Number.isNaN(date.getTime()) ? null : date;
}
