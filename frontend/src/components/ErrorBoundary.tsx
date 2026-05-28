import { Component, type ReactNode, type ReactElement } from 'react';
import { Button, Card } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';

interface FallbackProps {
  error: Error | null;
  /** 触发 error boundary 重置 */
  onRetry: () => void;
}

interface Props {
  children: ReactNode;
  /** 错误回调 —— 接入外部监控（如 Sentry） */
  onError?: (error: Error, info: { componentStack: string | null }) => void;
  /** 自定义降级 UI */
  FallbackComponent?: (props: FallbackProps) => ReactElement;
  /** 重置键 —— 变化时自动恢复，通常传 window.location.pathname */
  resetKeys?: unknown[];
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: { componentStack: string | null }) {
    this.props.onError?.(error, {
      componentStack: info.componentStack ?? null,
    });
  }

  componentDidUpdate(prevProps: Props) {
    if (
      this.state.hasError &&
      this.props.resetKeys &&
      prevProps.resetKeys?.some((k, i) => k !== this.props.resetKeys?.[i])
    ) {
      this.setState({ hasError: false, error: null });
    }
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.FallbackComponent) {
        return this.props.FallbackComponent({
          error: this.state.error,
          onRetry: this.handleRetry,
        });
      }

      return (
        <div
          style={{
            minHeight: '100vh',
            background: '#f0f2f5',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 40,
          }}
        >
          <Card style={{ maxWidth: 480, textAlign: 'center' }}>
            <h2 style={{ color: '#1a3a5c', marginBottom: 12 }}>
              页面发生错误
            </h2>
            <p
              style={{
                color: '#64748b',
                marginBottom: 8,
                fontSize: 14,
                wordBreak: 'break-all',
              }}
            >
              {this.state.error?.message || '未知错误'}
            </p>
            {import.meta.env.DEV && this.state.error?.stack && (
              <pre
                style={{
                  textAlign: 'left',
                  fontSize: 11,
                  color: '#94a3b8',
                  background: '#f8fafc',
                  padding: 10,
                  borderRadius: 8,
                  maxHeight: 200,
                  overflow: 'auto',
                  marginBottom: 16,
                }}
              >
                {this.state.error.stack}
              </pre>
            )}
            <Button
              type="primary"
              icon={<ReloadOutlined />}
              onClick={this.handleRetry}
            >
              重试
            </Button>
          </Card>
        </div>
      );
    }
    return this.props.children;
  }
}
