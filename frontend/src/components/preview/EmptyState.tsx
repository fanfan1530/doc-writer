/** 文书预览空状态组件。 */

import { Tag } from 'antd';
import { FileTextOutlined } from '@ant-design/icons';

export default function EmptyState() {
  return (
    <div className="text-center px-8 py-6">
      <div className="relative mx-auto mb-5 w-24 h-28">
        <div className="absolute inset-0 bg-white border border-slate-200 rounded-sm shadow-md rotate-[-3deg]" />
        <div className="absolute inset-0 bg-white border border-slate-200 rounded-sm shadow-md rotate-[2deg] scale-95" />
        <div className="absolute inset-0 bg-white border border-slate-200 rounded-sm shadow-sm flex items-center justify-center">
          <FileTextOutlined className="text-2xl text-police-300" />
        </div>
      </div>
      <div className="text-base text-slate-600 font-medium mb-1">AI 智能文书生成</div>
      <div className="text-xs text-slate-400 mb-4">支持多种公安法律文书，输入案情即可一键生成</div>
      <div className="flex flex-wrap justify-center gap-2">
        {['行政处罚决定书', '检查笔录', '辨认笔录', '现场勘查笔录'].map((t) => (
          <Tag key={t} className="text-xs text-slate-500 bg-slate-50 border-slate-200">{t}</Tag>
        ))}
      </div>
    </div>
  );
}
