/** WebSocket 连接 hook —— 自动重连 + JWT 认证 + 心跳。 */
import { useEffect, useRef, useCallback, useState } from 'react';
import { getAccessToken } from '../api/client';

interface UseWebSocketOptions {
  url: string;
  onMessage: (data: any) => void;
  enabled?: boolean;
  reconnectInterval?: number;
  heartbeatInterval?: number;
}

export function useWebSocket({
  url,
  onMessage,
  enabled = true,
  reconnectInterval = 5000,
  heartbeatInterval = 30000,
}: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [connected, setConnected] = useState(false);

  const connect = useCallback(() => {
    const token = getAccessToken();
    if (!token) return;

    try {
      const wsUrl = `${url}?token=${token}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        heartbeatTimerRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          }
        }, heartbeatInterval);
      };

      ws.onmessage = (event) => {
        if (event.data === 'pong') return;
        try {
          const data = JSON.parse(event.data);
          onMessage(data);
        } catch {
          // ignore non-JSON messages
        }
      };

      ws.onclose = () => {
        setConnected(false);
        if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
        if (enabled) {
          reconnectTimerRef.current = setTimeout(connect, reconnectInterval);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      // retry
      if (enabled) {
        reconnectTimerRef.current = setTimeout(connect, reconnectInterval);
      }
    }
  }, [url, onMessage, enabled, reconnectInterval, heartbeatInterval]);

  useEffect(() => {
    if (!enabled) {
      if (wsRef.current) wsRef.current.close();
      return;
    }
    connect();
    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [enabled, connect]);

  return { connected };
}
