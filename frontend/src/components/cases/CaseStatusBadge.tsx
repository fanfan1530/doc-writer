/** 案件状态标签 —— 7 种状态对应不同颜色。 */
import { Tag } from 'antd';
import type { CaseStatus } from '../../types';

const STATUS_CONFIG: Record<CaseStatus, { color: string; label: string }> = {
  FILING: { color: 'processing', label: '立案中' },
  INVESTIGATING: { color: 'blue', label: '侦查中' },
  REVIEWING: { color: 'orange', label: '审核中' },
  APPROVED: { color: 'green', label: '已批准' },
  CLOSED: { color: 'default', label: '已结案' },
  ARCHIVED: { color: 'default', label: '已归档' },
};

export default function CaseStatusBadge({ status }: { status: CaseStatus | string }) {
  const config = STATUS_CONFIG[status as CaseStatus] || { color: 'default', label: status };
  return <Tag color={config.color}>{config.label}</Tag>;
}
