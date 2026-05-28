import { useState, useEffect, useCallback } from 'react';
import client from '../api/client';

interface HistoryStats {
  total: number;
  recent: number;
  types: number;
  /** 最近 7 天每日生成计数（从旧到新） */
  dailyTrend: number[];
  /** 文书类型分布：{ 类型名: 数量 } */
  typeBreakdown: Record<string, number>;
  /** 最近活动 */
  recentItems: Array<{ id: number; doc_type: string; created_at: string; latency_ms: number }>;
}

interface RawHistoryItem {
  id: number;
  doc_type: string;
  created_at: string;
  latency_ms: number;
}

export function useHistoryStats() {
  const [stats, setStats] = useState<HistoryStats>({
    total: 0, recent: 0, types: 0,
    dailyTrend: [], typeBreakdown: {}, recentItems: [],
  });
  const [loading, setLoading] = useState(true);

  const fetchStats = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await client.get('/generation/history', { params: { limit: 200 } });
      const all: RawHistoryItem[] = data.history || [];
      const total = data.total || all.length;

      // 文书类型分布
      const typeBreakdown: Record<string, number> = {};
      for (const h of all) {
        typeBreakdown[h.doc_type] = (typeBreakdown[h.doc_type] || 0) + 1;
      }

      // 近 7 天每日趋势
      const dailyTrend = new Array(7).fill(0);
      const now = Date.now();
      const msPerDay = 24 * 3600 * 1000;
      for (const h of all) {
        const daysAgo = Math.floor((now - new Date(h.created_at).getTime()) / msPerDay);
        if (daysAgo >= 0 && daysAgo < 7) {
          dailyTrend[6 - daysAgo]++;
        }
      }

      // 近 7 天总数
      const recent = dailyTrend.reduce((a, b) => a + b, 0);

      setStats({
        total,
        recent,
        types: new Set(all.map((h) => h.doc_type)).size,
        dailyTrend,
        typeBreakdown,
        recentItems: all.slice(0, 5).map((h) => ({
          id: h.id, doc_type: h.doc_type, created_at: h.created_at, latency_ms: h.latency_ms || 0,
        })),
      });
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchStats(); }, [fetchStats]);

  return { stats, loading, refresh: fetchStats };
}
