/** 模型厂商预设配置。 */

export interface ProviderPreset {
  base_url: string;
  model_name: string;
  model_name_large: string;
  api_type?: string;
}

export const PROVIDER_PRESETS: Record<string, ProviderPreset> = {
  'DeepSeek': {
    base_url: 'https://api.deepseek.com/v1',
    model_name: 'deepseek-v4-pro',
    model_name_large: 'deepseek-v4-pro',
    api_type: 'openai',
  },
  'MiniMax': {
    base_url: 'https://api.minimax.chat/v1',
    model_name: 'MiniMax-M2.7',
    model_name_large: 'MiniMax-M2.7',
    api_type: 'openai',
  },
  'Dify': {
    base_url: 'http://127.0.0.1:8080/v1',
    model_name: 'dify-workflow',
    model_name_large: 'dify-workflow',
    api_type: 'dify',
  },
};
