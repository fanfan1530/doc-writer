/** 可复用的 AI 处理中 Loading 动画组件。 */

import { Spin } from 'antd';
import { LoadingOutlined } from '@ant-design/icons';

interface Props {
  text: string;
  color?: 'police' | 'blue';
}

const colors = {
  police: {
    bg: 'from-police-50 via-white to-police-50',
    border: 'border-police-200',
    dot: 'bg-police-400',
    text: 'text-police-700',
    spinner: 'bg-police-600',
  },
  blue: {
    bg: 'from-blue-50 to-sky-50',
    border: 'border-blue-200',
    dot: 'bg-blue-400',
    text: 'text-blue-700',
    spinner: 'bg-blue-500',
  },
};

export default function LoadingIndicator({ text, color = 'police' }: Props) {
  const c = colors[color];
  return (
    <div className={`mb-2 p-3 bg-gradient-to-r ${c.bg} border ${c.border} rounded-lg animate-fade-in overflow-hidden relative`}>
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/40 to-transparent animate-shimmer" />
      <div className="flex items-center gap-2 relative">
        <div className={`flex-shrink-0 w-7 h-7 rounded-full ${c.spinner} flex items-center justify-center`}>
          <Spin indicator={<LoadingOutlined style={{ fontSize: 14, color: '#fff' }} spin />} />
        </div>
        <span className={`text-xs font-medium ${c.text}`}>{text}</span>
        <span className="inline-flex gap-0.5">
          <span className={`w-1 h-1 rounded-full ${c.dot} animate-dot-bounce [animation-delay:0ms]`} />
          <span className={`w-1 h-1 rounded-full ${c.dot} animate-dot-bounce [animation-delay:150ms]`} />
          <span className={`w-1 h-1 rounded-full ${c.dot} animate-dot-bounce [animation-delay:300ms]`} />
        </span>
      </div>
    </div>
  );
}
