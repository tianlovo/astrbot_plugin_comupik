# ComuPik 文档中心

欢迎来到 ComuPik 文档中心！这里提供了完整的插件使用指南和其他插件接入文档。

## 文档目录

### 📖 API 文档

- [API 参考文档](./api-reference.md) - 完整的 RESTful API 接口文档
  - 健康检查
  - 统计信息
  - 图片列表查询
  - 单个图片信息
  - 图片文件下载
  - 轮询策略

### 🚀 SDK 文档

- [Python SDK](./python-sdk.md) - Python 异步 SDK
  - 完整 SDK 源码
  - 使用示例
  - 异常处理
  - 轮询实现

- [JavaScript SDK](./javascript-sdk.md) - JavaScript/TypeScript SDK
  - 完整 SDK 源码
  - 浏览器/Node.js 示例
  - React/Vue 组件示例
  - TypeScript 类型支持

## 快速开始

### 使用 Python SDK

```python
import asyncio
from comupik import ComuPikClient

async def main():
    client = ComuPikClient("http://127.0.0.1:8080")
    
    # 轮询新图片
    async for image in client.poll_images(interval=30):
        print(f"新图片: {image.id}")

asyncio.run(main())
```

### 使用 JavaScript SDK

```javascript
import { ComuPikClient } from 'comupik-sdk';

const client = new ComuPikClient('http://127.0.0.1:8080');

// 轮询新图片
for await (const image of client.pollImages({ interval: 30 })) {
  console.log(`新图片: ${image.id}`);
}
```

### 直接使用 HTTP API

```bash
# 获取统计信息
curl http://127.0.0.1:8080/api/stats

# 获取图片列表
curl "http://127.0.0.1:8080/api/images?start_time=0&end_time=1700000000&exclude_ids=[]"

# 下载图片
curl http://127.0.0.1:8080/api/file/image.jpg -o image.jpg
```

## 集成场景

### 场景 1：图片归档系统

使用 Python SDK 定期归档图片到云存储：

```python
async for image in client.poll_images(interval=60):
    if image.status == 'available':
        data = await client.download_image(image.file_path)
        await upload_to_cloud(data, image.id)
```

### 场景 2：实时图片展示

使用 JavaScript SDK 在网页实时展示新图片：

```javascript
for await (const image of client.pollImages({ interval: 10 })) {
  const img = document.createElement('img');
  img.src = `${client.baseUrl}/api/file/${image.filePath}`;
  gallery.appendChild(img);
}
```

### 场景 3：图片分析处理

使用 Python SDK 进行 AI 分析：

```python
async for image in client.poll_images():
    data = await client.download_image(image.file_path)
    result = await ai_analyze(data)
    await save_analysis_result(image.id, result)
```

## 配置说明

### API 服务器配置

在 AstrBot 管理页面的插件配置中：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `api_server.enabled` | bool | true | 是否启用API服务 |
| `api_server.host` | string | "127.0.0.1" | 监听地址 |
| `api_server.port` | int | 8080 | 监听端口 |

### 安全建议

1. **绑定本地地址**：建议将 `host` 设置为 `127.0.0.1`
2. **反向代理**：通过 Nginx/Apache 对外提供服务
3. **HTTPS**：生产环境启用 HTTPS
4. **访问控制**：配置防火墙限制访问来源

## 常见问题

### Q: 如何获取 API 地址？

A: 默认地址是 `http://127.0.0.1:8080`，可以在 AstrBot 管理页面的插件配置中修改端口。

### Q: 如何处理大量图片？

A: 使用分页查询和轮询机制，避免一次性加载过多数据：

```python
# 分页查询
images, total = await client.list_images(
    start_time=start,
    end_time=end,
    limit=100,  # 每页100条
    offset=0
)

# 轮询新图片
async for image in client.poll_images(interval=30):
    process_image(image)
```

### Q: 图片状态有哪些？

A: 
- `available` - 图片可用，可以下载
- `downloading` - 图片正在下载中
- `expired` - 图片已过期被清理

### Q: 如何处理下载中的图片？

A: SDK 会自动处理，遇到 `downloading` 状态会等待后重试。

## 技术支持

- GitHub Issues: [https://github.com/tianlovo/astrbot_plugin_comupik/issues](https://github.com/tianlovo/astrbot_plugin_comupik/issues)
- 文档更新：欢迎提交 PR 改进文档

## 许可证

MIT License
