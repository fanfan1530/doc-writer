/** 空闲超时检测 Hook —— 用户无操作一段时间后自动登出 */
import { useEffect, useRef, useCallback } from 'react';
import { clearTokens } from '../api/client';

interface UseIdleTimerOptions {
  /** 空闲超时时间（毫秒），默认 30 分钟 */
  timeout?: number;
  /** 提前警告时间（毫秒），默认 60 秒 */
  promptBefore?: number;
  /** 是否启用（默认 true） */
  enabled?: boolean;
  /** 登出回调 */
  onLogout?: () => void;
  /** 警告回调（还剩 promptBefore 毫秒时触发） */
  onPrompt?: () => void;
}

export function useIdleTimer({
  timeout = 30 * 60 * 1000,
  promptBefore = 60 * 1000,
  enabled = true,
  onLogout,
  onPrompt,
}: UseIdleTimerOptions = {}) {
  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const promptTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const promptedRef = useRef(false);

  const clearTimers = useCallback(() => {
    if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
    if (promptTimerRef.current) clearTimeout(promptTimerRef.current);
  }, []);

  const resetTimers = useCallback(() => {
    if (!enabled) return;
    clearTimers();
    promptedRef.current = false;

    if (promptBefore > 0 && onPrompt) {
      promptTimerRef.current = setTimeout(() => {
        promptedRef.current = true;
        onPrompt();
      }, timeout - promptBefore);
    }

    idleTimerRef.current = setTimeout(() => {
      clearTokens();
      onLogout?.();
      window.dispatchEvent(new CustomEvent('auth:logout'));
    }, timeout);
  }, [enabled, timeout, promptBefore, onPrompt, onLogout, clearTimers]);

  // 返回手动重置函数（用于"继续保持登录"按钮）
  const stayActive = useCallback(() => {
    resetTimers();
  }, [resetTimers]);

  useEffect(() => {
    if (!enabled) {
      clearTimers();
      return;
    }

    resetTimers();

    const events = ['mousedown', 'keydown', 'scroll', 'mousemove', 'touchstart'];
    const handler = () => resetTimers();

    events.forEach((e) => window.addEventListener(e, handler, { passive: true }));
    return () => {
      clearTimers();
      events.forEach((e) => window.removeEventListener(e, handler));
    };
  }, [enabled, resetTimers, clearTimers]);

  return { stayActive, isPrompted: promptedRef.current };
}
