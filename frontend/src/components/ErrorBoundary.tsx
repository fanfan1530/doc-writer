import { Component, type ReactNode } from 'react';
import { Button, Card } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';

interface Props {
  children: ReactNode;
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

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ minHeight: '100vh', background: '#f0f2f5', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 40 }}>
          <Card style={{ maxWidth: 480, textAlign: 'center' }}>
            <h2 style={{ color: '#1a3a5c', marginBottom: 12 }}>页面发生错误</h2>
            <p style={{ color: '#64748b', marginBottom: 8, fontSize: 14 }}>
              {this.state.error?.message || '未知错误'}
            </p>
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
