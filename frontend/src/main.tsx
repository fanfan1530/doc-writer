import ReactDOM from 'react-dom/client';
import AppV3 from './App_v3';
import './index.css';

// v2.0 智慧警务智能工作台
// 如需回滚到 v1.0: 将 AppV3 改为 AppV2, './App_v3' 改为 './App_v2'
ReactDOM.createRoot(document.getElementById('root')!).render(<AppV3 />);
