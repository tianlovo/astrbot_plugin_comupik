# ComuPik 图片收集插件

Telegram群组/频道图片自动收集、存储管理及API服务插件

## 功能特性

- **图片自动收集**: 监控指定的Telegram群组/频道，自动收集图片消息
- **感知哈希去重**: 使用pHash算法计算图片感知哈希，防止重复存储相似图片
- **数据库存储**: 保存图片元数据（消息ID、发送者、时间、文件路径等）
- **定时清理**: 自动清理过期的临时文件，支持文件访问锁定防止并发冲突
- **RESTful API**: 提供HTTP API接口，支持图片列表查询和文件访问
- **可视化配置**: 通过AstrBot管理页面进行配置，无需修改代码
- **重试机制**: 对耗时易中断操作（图片下载、数据库操作）提供指数退避重试
- **错误通知**: 自动向超级管理员发送错误通知，包含错误详情和堆栈信息

## 安装要求

- AstrBot >= 4.9.2
- Telegram平台适配器已配置

## 配置说明

在AstrBot管理页面的插件配置中，可以设置以下选项：

### 基础配置

| 配置项 | 类型 | 说明 | 默认值 |
|--------|------|------|--------|
| `super_admin` | string | 超级管理员TG ID，接收错误通知 | "" |
| `monitor_targets` | list | 监控的群组/频道ID列表 | [] |

> **注意**: 插件使用AstrBot Telegram平台适配器提供的接口，无需单独配置Bot Token。请确保在AstrBot主配置中正确配置了Telegram平台适配器。

**获取超级管理员TG ID：**
1. 私聊Bot发送 `/myid` 指令
2. 获取用户ID并配置到 `super_admin` 中
3. 插件运行中的错误将自动通知该用户

### API服务器配置

| 配置项 | 类型 | 说明 | 默认值 |
|--------|------|------|--------|
| `api_server.enabled` | bool | 是否启用API服务 | true |
| `api_server.host` | string | API服务器监听地址 | "127.0.0.1" |
| `api_server.port` | int | API服务器监听端口 | 8080 |

### 定时清理配置

| 配置项 | 类型 | 说明 | 默认值 |
|--------|------|------|--------|
| `cleanup.enabled` | bool | 是否启用定时清理 | true |
| `cleanup.interval_hours` | int | 清理任务执行间隔（小时） | 24 |
| `cleanup.max_age_hours` | int | 文件最大保留时间（小时） | 72 |

### 去重配置

| 配置项 | 类型 | 说明 | 默认值 |
|--------|------|------|--------|
| `deduplication.enabled` | bool | 是否启用感知哈希去重 | true |
| `deduplication.threshold` | int | 相似度阈值（越小越严格） | 8 |

### 存储配置

| 配置项 | 类型 | 说明 | 默认值 |
|--------|------|------|--------|
| `storage.tmp_subdir` | string | 临时文件子目录名 | "tmp" |
| `storage.file_naming` | string | 文件命名模式 | "{timestamp}_{msg_id}_{random}" |

## 使用指南

### 1. 配置AstrBot Telegram平台适配器

在使用本插件前，请确保已在AstrBot主配置中配置好Telegram平台适配器：

1. 在AstrBot管理页面，进入「平台适配器」配置
2. 添加Telegram平台适配器
3. 填写从@BotFather获取的Bot Token
4. 保存配置并重启AstrBot

### 2. 获取群组/频道ID

**使用指令查询（推荐）**

将机器人添加到群组或频道后，发送指令：
```
/chatid
```

机器人会立即回复当前聊天的ID信息，格式如下：
```
📋 群组信息
━━━━━━━━━━━━━━━━━━
群组名称: 测试群组
群组ID: -1001234567890
━━━━━━━━━━━━━━━━━━
💡 将此ID添加到监控目标列表即可收集本群图片
```

**频道ID获取方法：**
1. 将机器人添加为频道管理员
2. 在频道中发送 `/chatid` 指令
3. 获取频道ID

**获取用户TG ID（用于配置超级管理员）：**

1. 私聊Bot发送指令：
```
/myid
```

2. Bot会回复你的用户ID：
```
👤 用户信息
━━━━━━━━━━━━━━━━━━
用户名: 你的昵称
用户ID: 123456789
━━━━━━━━━━━━━━━━━━
💡 将此ID配置为超级管理员可接收错误通知
```

3. 将用户ID配置到插件的 `super_admin` 配置项中

### 3. 配置插件

1. 打开AstrBot管理页面
2. 进入插件管理，找到ComuPik插件
3. 点击配置按钮，填写监控目标列表和超级管理员TG ID
4. 根据需要调整其他配置项
5. 保存配置并重载插件

## API接口文档

### 基础信息

- **Base URL**: `http://{host}:{port}/api`
- **响应格式**: JSON

### 接口列表

#### 1. 健康检查

```
GET /api/health
```

**响应示例：**
```json
{
  "status": "ok",
  "service": "comupik-api",
  "version": "1.0.0"
}
```

#### 2. 获取统计信息

```
GET /api/stats
```

**响应示例：**
```json
{
  "status": "ok",
  "data": {
    "total_images": 150,
    "total_size_bytes": 15728640,
    "avg_size_bytes": 104857,
    "chat_count": 5,
    "oldest_timestamp": 1700000000,
    "newest_timestamp": 1700086400
  }
}
```

**字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| total_images | int | 总图片数量 |
| total_size_bytes | int | 总文件大小（字节） |
| avg_size_bytes | int | 平均文件大小（字节） |
| chat_count | int | 监控的聊天群数量 |
| oldest_timestamp | int | 最早图片时间戳 |
| newest_timestamp | int | 最新图片时间戳 |

### Bot 指令

#### 1. 查询当前聊天ID

```
/chatid
```

获取当前群组或频道的ID，用于配置监控目标。

#### 2. 查询用户ID

```
/myid
```

获取当前用户的TG ID，用于配置超级管理员。

#### 3. 查看图片统计

```
/comupik_stats
```

显示数据库中的图片统计信息，包括总数、总大小、聊天群数量等。

**输出示例：**
```
📊 ComuPik 图片统计
━━━━━━━━━━━━━━━━━━
📁 总图片数: 150 张
💾 总大小: 15.50 MB
📊 平均大小: 158.72 KB
💬 聊天群数: 5 个
━━━━━━━━━━━━━━━━━━
📅 最早图片: 2026-03-15 20:00:00
📅 最新图片: 2026-03-15 21:00:00
━━━━━━━━━━━━━━━━━━
```

#### 3. 获取图片列表（轮询接口）

```
GET /api/images?start_time={start_time}&end_time={end_time}&exclude_ids={exclude_ids}&limit={limit}&offset={offset}
```

**参数说明：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| start_time | int | **是** | 开始时间戳（Unix时间戳） |
| end_time | int | **是** | 结束时间戳（Unix时间戳） |
| exclude_ids | string | **是** | 要排除的图片ID列表，JSON格式数组（可为空`[]`） |
| limit | int | 否 | 返回数量限制（默认100，最大1000） |
| offset | int | 否 | 偏移量（默认0） |

**图片状态说明：**

| 状态 | 说明 |
|------|------|
| `available` | 图片已下载，可以访问 |
| `downloading` | 图片正在下载中 |
| `expired` | 图片已过期被清理 |

**响应示例：**
```json
{
  "status": "ok",
  "data": {
    "total": 150,
    "limit": 100,
    "offset": 0,
    "start_time": 1700000000,
    "end_time": 1700086400,
    "images": [
      {
        "id": 1,
        "message_id": "12345",
        "chat_id": "-1001234567890",
        "sender_id": "987654321",
        "sender_name": "用户名",
        "timestamp": 1700000000,
        "file_path": "/path/to/image.jpg",
        "original_url": "https://t.me/c/1234567890/12345",
        "file_size": 102400,
        "width": 1920,
        "height": 1080,
        "created_at": 1700000000,
        "status": "available"
      }
    ]
  }
}
```

**轮询使用示例：**

其他插件通过定时调用此接口实现新图片轮询：

1. 首次请求：`start_time=0&end_time=当前时间&exclude_ids=[]`
2. 记录返回的所有图片ID
3. 下次请求：`start_time=上次end_time&end_time=当前时间&exclude_ids=[已记录的图片ID]`
4. 重复步骤2-3

#### 4. 获取单个图片信息

```
GET /api/images/{id}
```

**响应示例：**
```json
{
  "status": "ok",
  "data": {
    "id": 1,
    "message_id": "12345",
    "chat_id": "-1001234567890",
    "sender_id": "987654321",
    "sender_name": "用户名",
    "timestamp": 1700000000,
    "file_path": "/path/to/image.jpg",
    "original_url": "https://t.me/c/1234567890/12345",
    "file_size": 102400,
    "width": 1920,
    "height": 1080,
    "created_at": 1700000000,
    "status": "available"
  }
}
```

#### 5. 获取图片文件

```
GET /api/file/{filename}
```

**状态码说明：**

| 状态码 | 状态 | 说明 |
|--------|------|------|
| 200 | `available` | 图片可用，返回文件内容 |
| 202 | `downloading` | 图片正在下载中 |
| 410 | `expired` | 图片已过期被清理 |
| 404 | `not_found` | 图片不存在 |

**响应示例（图片可用）：**
直接返回图片文件内容

**响应示例（正在下载）：**
```json
{
  "status": "downloading",
  "message": "文件正在下载中",
  "filename": "1700000000_12345_abc123.jpg"
}
```

**响应示例（已过期）：**
```json
{
  "status": "expired",
  "message": "文件已过期",
  "filename": "1700000000_12345_abc123.jpg"
}
```

## 其他插件接入指南

### Python轮询示例

```python
import aiohttp
import json
import time

class ComuPikClient:
    def __init__(self, api_host="127.0.0.1", api_port=8080):
        self.base_url = f"http://{api_host}:{api_port}"
        self.known_ids = set()  # 已知的图片ID集合
        self.last_end_time = 0
    
    async def poll_new_images(self):
        """轮询获取新图片"""
        async with aiohttp.ClientSession() as session:
            current_time = int(time.time())
            
            # 构建请求参数
            params = {
                "start_time": self.last_end_time,
                "end_time": current_time,
                "exclude_ids": json.dumps(list(self.known_ids)),
                "limit": 100
            }
            
            async with session.get(
                f"{self.base_url}/api/images", params=params
            ) as resp:
                data = await resp.json()
                images = data.get("data", {}).get("images", [])
                
                # 记录新的图片ID
                for img in images:
                    self.known_ids.add(img["id"])
                
                # 更新时间范围
                self.last_end_time = current_time
                
                return images
    
    async def download_image(self, filename):
        """下载图片文件"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/api/file/{filename}"
            ) as resp:
                if resp.status == 200:
                    return await resp.read()
                elif resp.status == 202:
                    print("图片正在下载中，请稍后重试")
                    return None
                elif resp.status == 410:
                    print("图片已过期")
                    return None
                else:
                    print(f"获取图片失败: {resp.status}")
                    return None

# 使用示例
async def main():
    client = ComuPikClient()
    
    # 定时轮询（每30秒）
    while True:
        images = await client.poll_new_images()
        print(f"获取到 {len(images)} 张新图片")
        
        for img in images:
            if img["status"] == "available":
                # 获取文件名
                filename = img["file_path"].split("/")[-1]
                data = await client.download_image(filename)
                if data:
                    print(f"下载成功: {filename}, 大小: {len(data)} bytes")
        
        await asyncio.sleep(30)
```

### JavaScript示例

```javascript
// 获取图片列表
async function getImages(host = '127.0.0.1', port = 8080) {
  const response = await fetch(`http://${host}:${port}/api/images?limit=10`);
  const data = await response.json();
  return data.data.images;
}

// 获取图片文件
async function getImageFile(filename, host = '127.0.0.1', port = 8080) {
  const response = await fetch(`http://${host}:${port}/api/file/${filename}`);
  if (response.ok) {
    return await response.blob();
  }
  return null;
}
```

## 数据存储说明

### 数据库结构

图片元数据存储在SQLite数据库中，包含以下字段：

- `id`: 记录ID（主键）
- `message_id`: Telegram消息ID
- `chat_id`: 群组/频道ID
- `sender_id`: 发送者ID
- `sender_name`: 发送者名称
- `timestamp`: 消息时间戳
- `file_path`: 本地文件路径
- `original_url`: 原始消息链接
- `perceptual_hash`: 感知哈希值
- `file_size`: 文件大小（字节）
- `width`: 图片宽度
- `height`: 图片高度
- `created_at`: 记录创建时间

### 文件存储

- 数据目录：`data/plugin_data/astrbot_plugin_comupik/`
- 临时文件：`data/plugin_data/astrbot_plugin_comupik/tmp/`
- 数据库文件：`data/plugin_data/astrbot_plugin_comupik/comupik_data.db`

## 注意事项

1. **Bot权限**: 确保Bot在监控的群组/频道中有读取消息的权限
2. **隐私合规**: 收集图片前请确保符合相关隐私法规
3. **存储空间**: 定期清理配置可避免存储空间不足
4. **API安全**: 建议将API服务器绑定到127.0.0.1，通过反向代理对外提供服务

## 重试机制说明

本插件对耗时易中断的操作提供了重试机制，使用指数退避策略：

| 操作类型 | 重试次数 | 退避策略 |
|----------|----------|----------|
| 图片下载 | 3次 | 1秒 → 2秒 → 4秒 |
| 数据库操作 | 3次 | 0.5秒 → 1秒 → 2秒 |
| 文件操作 | 3次 | 0.5秒 → 1秒 → 2秒 |

重试机制确保在网络波动或临时故障时，操作能够自动恢复，提高系统可用性。

## 错误通知说明

当插件运行中发生错误时，会自动向配置的超级管理员发送TG消息通知：

**通知内容包含：**
- 错误类型
- 发生时间
- 错误信息（前500字符）
- 堆栈跟踪（前1000字符）

**去重机制：**
- 相同错误5分钟内只通知一次
- 避免重复通知造成骚扰

**配置方法：**
1. 私聊Bot发送 `/myid` 获取用户ID
2. 将ID填入插件配置的 `super_admin` 字段
3. 保存配置后，插件会自动发送测试通知

## 技术实现说明

### Telegram平台适配器集成

本插件使用AstrBot封装的Telegram平台适配器进行图片下载，而非直接访问Telegram API：

```python
# 使用AstrBot Telegram适配器提供的接口
from astrbot.core.utils.io import download_file

# 从消息事件中获取PhotoSize对象
photo = event.message_obj.raw_message.photo[-1]

# 使用适配器的get_file方法获取文件对象
file_obj = await photo.get_file()

# 使用AstrBot提供的download_file工具函数下载文件
temp_path = await download_file(file_obj.file_path)
```

**优势：**
- 无需单独配置Bot Token，复用AstrBot主配置的Token
- 自动处理文件下载的缓存和错误处理
- 与AstrBot其他功能保持一致性
- 支持自定义Telegram API服务器（如使用代理）

### 直接API访问说明

本插件**不直接访问**Telegram API。所有与Telegram的交互都通过AstrBot平台适配器完成。如果未来需要实现重新下载已过期文件的功能，可能需要：

1. 存储file_id到数据库（但file_id会过期）
2. 或者使用原始消息链接（需要Bot在消息发送时就在群组中）

## 故障排查

### 插件无法加载

1. 检查AstrBot版本是否 >= 4.9.2
2. 检查requirements.txt中的依赖是否已安装
3. 查看AstrBot日志获取详细错误信息

### 图片无法收集

1. 确认AstrBot主配置中Telegram平台适配器已正确配置
2. 确认Bot已被添加到监控的群组/频道
3. 检查群组/频道ID格式是否正确（应为数字，频道ID通常以-100开头）
4. 查看日志中的错误信息

### API无法访问

1. 检查API服务器是否已启用
2. 检查端口是否被占用
3. 检查防火墙设置

## 更新日志

### v1.0.0
- 初始版本发布
- 实现图片自动收集功能
- 实现感知哈希去重
- 实现定时清理机制
- 提供RESTful API服务

## 开源协议

MIT License
