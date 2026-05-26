/** AI 助手独立页面 —— 全宽对话 */
import ChatPanel from '../ChatPanel';

export default function CopilotPage() {
  return (
    <div className="h-full p-3 page-enter min-h-0">
      <div className="h-full max-w-[1200px] mx-auto">
        <ChatPanel />
      </div>
    </div>
  );
}
