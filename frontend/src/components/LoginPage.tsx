/** 登录页面 —— remember me + autocomplete + idle timer */
import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Input, Button, Checkbox, Typography, App } from 'antd';
import { UserOutlined, LockOutlined, LoginOutlined } from '@ant-design/icons';
import { setTokens } from '../api/client';

const { Text, Title } = Typography;

export default function LoginPage({ onLogin }: { onLogin?: () => void }) {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin123');
  const [rememberMe, setRememberMe] = useState(false);
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
      setTokens(data.access_token, data.refresh_token, rememberMe);
      // 存储用户信息用于权限控制
      const userInfo = {
        username: data.username,
        role: data.role,
        role_label: data.role_label,
        permissions: data.permissions || [],
        display_name: data.display_name || data.username,
        unit: data.unit || '',
      };
      localStorage.setItem('user_info', JSON.stringify(userInfo));
      message.success(`欢迎，${data.display_name || data.username}`);
      onLogin?.();
      navigate('/dashboard', { replace: true });
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
                autoComplete="username"
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
                autoComplete="current-password"
              />
            </div>
            <div className="flex items-center justify-between">
              <Checkbox
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                className="text-xs text-slate-500"
              >
                记住登录
              </Checkbox>
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
