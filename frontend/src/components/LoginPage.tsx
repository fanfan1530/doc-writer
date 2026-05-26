/** 登录页面 —— 使用默认 admin 账户或自定义登录。 */

import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Input, Button, Typography, App } from 'antd';
import { UserOutlined, LockOutlined, LoginOutlined } from '@ant-design/icons';
import { setTokens } from '../api/client';

const { Text, Title } = Typography;

interface Props {
  onLogin?: () => void;
}

export default function LoginPage({ onLogin }: Props) {
  const { message } = App.useApp();
  // useNavigate may throw if not inside a Router (App_v2 fallback)
  let navigate: ReturnType<typeof useNavigate> | undefined;
  try {
    navigate = useNavigate();
  } catch {
    navigate = undefined;
  }
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin123');
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    if (!username.trim() || !password.trim()) {
      message.warning('请输入用户名和密码');
      return;
    }
    setLoading(true);
    try {
      const resp = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password }),
      });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || '登录失败');
      }
      const data = await resp.json();
      setTokens(data.access_token, data.refresh_token);
      message.success(`欢迎，${data.username}`);
      if (navigate) {
        navigate('/dashboard', { replace: true });
      }
      onLogin?.();
    } catch (err) {
      message.error(err instanceof Error ? err.message : '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-screen flex items-center justify-center bg-gradient-to-br from-police-900 via-police-700 to-police-600">
      <div className="w-full max-w-[400px] px-4">
        <div className="text-center mb-8">
          <span className="text-5xl">🛡️</span>
          <Title level={2} className="!text-white !mb-1">智慧警务智能工作台</Title>
          <Text className="text-police-200">AI 驱动的公安执法辅助平台</Text>
        </div>

        <Card className="shadow-xl border-0 rounded-2xl" styles={{ body: { padding: '32px' } }}>
          <div className="space-y-4">
            <div>
              <Text className="text-xs text-slate-500 mb-1 block">用户名</Text>
              <Input
                size="large"
                prefix={<UserOutlined className="text-slate-400" />}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
                placeholder="admin"
              />
            </div>
            <div>
              <Text className="text-xs text-slate-500 mb-1 block">密码</Text>
              <Input.Password
                size="large"
                prefix={<LockOutlined className="text-slate-400" />}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
                placeholder="admin123"
              />
            </div>
            <Button
              type="primary"
              size="large"
              block
              loading={loading}
              onClick={handleLogin}
              icon={<LoginOutlined />}
              className="h-11 text-base font-semibold"
              style={{
                background: 'linear-gradient(135deg, #1a3a5c 0%, #1e4470 100%)',
              }}
            >
              登录
            </Button>
            <Text className="text-xs text-slate-400 text-center block">
              默认账户: admin / admin123
            </Text>
          </div>
        </Card>
      </div>
    </div>
  );
}
