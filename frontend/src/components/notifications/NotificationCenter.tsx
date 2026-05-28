/** 通知中心下拉面板 —— 通知列表 + 标记已读 + 跳转案件。 */
import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { List, Badge, Button, Typography, App, Empty, Spin } from 'antd';
import { BellOutlined, CheckOutlined } from '@ant-design/icons';
import client from '../../api/client';
import type { NotificationItem } from '../../types';

const { Text } = Typography;

const TYPE_LABELS: Record<string, string> = {
  CASE_ASSIGNED: '案件分配',
  DOCUMENT_SUBMITTED: '文书提交',
  DOCUMENT_APPROVED: '审批通过',
  DOCUMENT_REJECTED: '文书退回',
  DEADLINE_WARNING: '期限预警',
  SYSTEM_ANNOUNCEMENT: '系统公告',
};

interface Props {
  onUnreadCountChange?: (count: number) => void;
}

export default function NotificationCenter({ onUnreadCountChange }: Props) {
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchNotifications = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await client.get('/notifications', { params: { limit: 10 } });
      setNotifications(data.notifications || []);
      const unread = (data.notifications || []).filter((n: NotificationItem) => !n.is_read).length;
      onUnreadCountChange?.(unread);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [onUnreadCountChange]);

  useEffect(() => {
    fetchNotifications();
  }, [fetchNotifications]);

  const handleMarkRead = async (id: number) => {
    try {
      await client.put(`/notifications/${id}/read`);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)),
      );
      onUnreadCountChange?.(notifications.filter((n) => !n.is_read && n.id !== id).length);
    } catch {
      message.error('操作失败');
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await client.post('/notifications/mark-all-read');
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      onUnreadCountChange?.(0);
    } catch {
      message.error('操作失败');
    }
  };

  const handleClick = (item: NotificationItem) => {
    if (!item.is_read) handleMarkRead(item.id);
    if (item.related_case_id) {
      navigate(`/cases/${item.related_case_id}`);
    }
  };

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  return (
    <div className="w-80 max-h-96 flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
        <Text strong className="text-sm">通知</Text>
        {unreadCount > 0 && (
          <Button size="small" type="link" icon={<CheckOutlined />} onClick={handleMarkAllRead}>
            全部已读
          </Button>
        )}
      </div>
      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="flex items-center justify-center py-8"><Spin /></div>
        ) : notifications.length === 0 ? (
          <Empty description="暂无通知" className="py-4" />
        ) : (
          <List
            dataSource={notifications}
            renderItem={(item) => (
              <div
                className={`flex items-start gap-3 px-4 py-3 cursor-pointer hover:bg-slate-50 transition-colors border-b border-slate-50 ${
                  !item.is_read ? 'bg-blue-50/50' : ''
                }`}
                onClick={() => handleClick(item)}
              >
                {/* 未读小点 */}
                <div className="mt-1.5 flex-shrink-0">
                  {!item.is_read ? (
                    <Badge status="processing" />
                  ) : (
                    <div className="w-2 h-2 rounded-full bg-slate-200" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <Text className="text-xs font-medium text-slate-800 truncate">{item.title}</Text>
                    <Text className="text-[10px] text-slate-300 flex-shrink-0">
                      {TYPE_LABELS[item.type] || item.type}
                    </Text>
                  </div>
                  {item.content && (
                    <div className="text-xs text-slate-500 mt-0.5 line-clamp-2">{item.content}</div>
                  )}
                  <div className="text-[10px] text-slate-400 mt-1">
                    {item.created_at ? new Date(item.created_at).toLocaleString('zh-CN') : ''}
                  </div>
                </div>
              </div>
            )}
          />
        )}
      </div>
    </div>
  );
}
