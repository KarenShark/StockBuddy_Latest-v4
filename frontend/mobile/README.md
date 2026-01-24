# StockBuddy Mobile App

React Native + Expo 移动端应用，用于访问 StockBuddy AI 交易分析系统。

## 快速开始

### 1. 启动后端 API 服务器

```bash
cd ../../api
pip install -r requirements.txt
python main.py
```

服务器启动后会显示你的局域网 IP 地址，例如：
```
Mobile access (same WiFi): http://192.168.1.100:8000
```

### 2. 配置 API 地址

编辑 `src/config/api.ts`，将 `API_BASE_URL` 改为你的电脑 IP：

```typescript
export const API_BASE_URL = 'http://192.168.1.100:8000';
```

### 3. 启动 Expo 开发服务器

```bash
npm start
```

### 4. 在手机上运行

1. **下载 Expo Go App**
   - iOS: App Store 搜索 "Expo Go"
   - Android: Google Play 搜索 "Expo Go"

2. **扫描二维码**
   - 确保手机和电脑在同一 WiFi 下
   - 使用 Expo Go 扫描终端中显示的二维码

3. **开始使用**
   - 输入股票代码（如 AAPL, NVDA）
   - 选择要使用的分析师
   - 点击"开始分析"

## 功能特性

- ✅ 实时分析状态更新
- ✅ 多代理分析结果展示
- ✅ 美观的移动端界面
- ✅ 支持 iOS 和 Android
- ✅ 下拉刷新状态

## 技术栈

- React Native
- Expo
- TypeScript
- React Navigation
- React Native Paper
- Axios

## 注意事项

1. 确保电脑的防火墙允许 8000 端口访问
2. 确保手机和电脑在同一 WiFi 网络下
3. 如果连接失败，检查 API_BASE_URL 配置是否正确
