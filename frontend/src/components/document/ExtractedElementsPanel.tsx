import { Button, Card, Empty, Input, Tag } from 'antd';
import {
  CheckCircleOutlined,
  FileSearchOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';

interface Props {
  elements: Record<string, string>;
  fieldLabels: Record<string, string>;
  caseNature: string;
  extracting: boolean;
  generating: boolean;
  canExtract: boolean;
  onExtract: () => void;
  onElementChange: (key: string, value: string) => void;
  onElementFocus?: (key: string, label: string, value: string) => void;
  onGenerateFromElements: () => void;
}

export default function ExtractedElementsPanel({
  elements,
  fieldLabels,
  caseNature,
  extracting,
  generating,
  canExtract,
  onExtract,
  onElementChange,
  onElementFocus,
  onGenerateFromElements,
}: Props) {
  const entries = Object.entries(elements).filter(([, value]) => String(value ?? '').trim());
  const hasElements = entries.length > 0;

  return (
    <Card
      className="shadow-sm border-0 rounded-xl h-full flex flex-col min-h-0"
      styles={{ body: { padding: 16, height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 } }}
    >
      <div className="flex items-start justify-between gap-3 mb-3 flex-shrink-0">
        <div>
          <div className="text-base font-semibold text-slate-800 flex items-center gap-2">
            <FileSearchOutlined className="text-police-500" />
            要素确认
          </div>
          <div className="text-xs text-slate-400 mt-1">
            先核对字段，再用确认后的内容生成
          </div>
        </div>
        <Button
          size="small"
          icon={hasElements ? <ReloadOutlined /> : <ThunderboltOutlined />}
          loading={extracting}
          disabled={!canExtract || generating}
          onClick={onExtract}
        >
          {hasElements ? '重新提取' : '提取要素'}
        </Button>
      </div>

      {caseNature && (
        <div className="mb-3 flex-shrink-0">
          <Tag color="blue" className="m-0">{caseNature}</Tag>
        </div>
      )}

      <div className="flex-1 min-h-0 overflow-auto pr-1">
        {!hasElements ? (
          <div className="h-full min-h-[220px] flex items-center justify-center">
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                <span className="text-xs text-slate-400">
                  输入案情后点击“提取要素”
                </span>
              }
            />
          </div>
        ) : (
          <div className="space-y-2">
            {entries.map(([key, value], index) => (
              <div key={key} className="rounded-lg border border-slate-100 bg-slate-50 p-2.5">
                <div className="text-xs font-medium text-slate-500 mb-1">
                  {formatElementLabel(key, fieldLabels, index)}
                </div>
                <Input.TextArea
                  autoSize={{ minRows: 1, maxRows: 4 }}
                  value={String(value)}
                  onChange={(event) => onElementChange(key, event.target.value)}
                  onFocus={() => onElementFocus?.(
                    key,
                    formatElementLabel(key, fieldLabels, index),
                    String(value),
                  )}
                  onClick={() => onElementFocus?.(
                    key,
                    formatElementLabel(key, fieldLabels, index),
                    String(value),
                  )}
                  className="text-sm bg-white"
                />
              </div>
            ))}
          </div>
        )}
      </div>

      <Button
        type="primary"
        block
        size="large"
        className="mt-3 h-10 font-semibold flex-shrink-0"
        icon={<CheckCircleOutlined />}
        disabled={!hasElements || extracting}
        loading={generating}
        onClick={onGenerateFromElements}
        style={hasElements && !extracting ? { background: '#1a3a5c' } : undefined}
      >
        用确认要素生成
      </Button>
    </Card>
  );
}

function formatElementLabel(key: string, fieldLabels: Record<string, string>, index: number): string {
  if (fieldLabels[key]) return fieldLabels[key];

  const labels: Record<string, string> = {
    document_number: '文书编号',
    police_org_name: '公安机关名称',
    org_dept: '机关简称',
    year: '年份',
    number: '编号',
    offender_name: '违法行为人姓名',
    person_name: '姓名',
    name: '姓名',
    gender: '性别',
    age: '年龄',
    birth_date: '出生日期',
    id_type: '身份证件种类',
    id_number: '身份证件号码',
    registered_place: '户籍所在地',
    current_address: '现住址',
    work_unit: '工作单位',
    offense_history: '违法经历',
    offense_fact: '违法事实',
    evidence: '证据',
    punishment: '处罚种类及幅度',
    execution_method: '执行方式及期限',
    appeal_org: '行政复议机关',
    appeal_court: '行政诉讼法院',
    decision_date: '决定日期',
    sign_date: '签收日期',
    case_time: '案发时间',
    case_date: '案发日期',
    case_location: '案发地点',
    case_nature: '案件性质',
    case_brief: '案情摘要',
    case_fact: '案件事实',
    fact_description: '事实描述',
    illegal_fact: '违法事实',
    evidence_list: '证据材料',
    penalty_content: '处罚内容',
    legal_basis: '法律依据',
    police_unit: '办案单位',
    suspect_name: '当事人',
  };
  if (labels[key]) return labels[key];

  const lowerKey = key.toLowerCase();
  if (lowerKey.includes('date') || lowerKey.includes('time')) return '时间信息';
  if (lowerKey.includes('location') || lowerKey.includes('address') || lowerKey.includes('place')) return '地点信息';
  if (lowerKey.includes('fact') || lowerKey.includes('brief') || lowerKey.includes('summary')) return '事实经过';
  if (lowerKey.includes('evidence')) return '证据材料';
  if (lowerKey.includes('law') || lowerKey.includes('legal')) return '法律依据';
  if (lowerKey.includes('penalty') || lowerKey.includes('punish')) return '处罚内容';
  if (lowerKey.includes('offender') || lowerKey.includes('suspect') || lowerKey.includes('person')) return '人员信息';
  if (lowerKey.includes('unit') || lowerKey.includes('org') || lowerKey.includes('police')) return '单位信息';

  return `其他要素 ${index + 1}`;
}
