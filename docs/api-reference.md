# ComuPik API 参考文档

## 基础信息

- **Base URL**: `http://{host}:{port}/api`
- **默认地址**: `http://127.0.0.1:8080/api`
- **响应格式**: JSON

## 接口列表

### 1. 健康检查

检查 API 服务是否正常运行。

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

**状态码说明：**

| 状态码 | 说明 |
|--------|------|
| 200 | 服务正常运行 |

---

### 2. 获取统计信息

获取数据库中图片的统计信息。

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
| oldest_timestamp | int | 最早图片时间戳（Unix） |
| newest_timestamp | int | 最新图片时间戳（Unix） |

---

### 3. 获取图片列表

获取指定时间范围内的图片列表，支持分页和排除指定ID。

```
GET /api/images?start_time={start_time}&end_time={end_time}&exclude_ids={exclude_ids}&limit={limit}&offset={offset}
```

**查询参数：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| start_time | int | **是** | - | 开始时间戳（Unix） |
| end_time | int | **是** | - | 结束时间戳（Unix） |
| exclude_ids | string | 否 | "[]" | 要排除的图片ID列表，JSON格式数组 |
| limit | int | 否 | 100 | 返回数量限制（最大1000） |
| offset | int | 否 | 0 | 偏移量 |

**关于 `exclude_ids` 参数：**

`exclude_ids` 用于在轮询新图片时排除已处理的图片ID，避免重复获取相同数据。

**为什么需要 `exclude_ids`？**

在轮询场景中，客户端需要定期获取新图片。由于时间范围查询是基于 `timestamp` 字段，而多张图片可能具有相同的时间戳（同一秒内），这会导致以下问题：

1. **时间戳精度限制**：时间戳是秒级的，同一秒内发送的多张图片会有相同的 `timestamp`
2. **分页边界问题**：当使用 `limit` 和 `offset` 分页时，新图片的插入可能导致偏移量计算错误
3. **重复数据**：如果不排除已处理的图片ID，轮询时可能会重复获取相同的图片

**使用场景：**

```
第一次请求：
GET /api/images?start_time=0&end_time=1700000000&exclude_ids=[]
返回：[图片1(id=1), 图片2(id=2), 图片3(id=3)]

第二次请求（排除已获取的图片）：
GET /api/images?start_time=1700000000&end_time=1700000100&exclude_ids=[1,2,3]
返回：[图片4(id=4), 图片5(id=5)]  # 不会重复返回图片1-3
```

**最佳实践：**
- 客户端应维护一个已处理图片ID的集合
- 每次轮询时将已知的ID列表传入 `exclude_ids`
- 收到响应后，将新图片的ID加入已处理集合

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
        "original_url": "https://api.telegram.org/file/...",
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

**图片状态说明：**

| 状态 | 说明 |
|------|------|
| `available` | 图片已下载，可以访问 |
| `downloading` | 图片正在下载中 |
| `expired` | 图片已过期被清理 |

**错误响应：**

```json
{
  "status": "error",
  "message": "缺少必填参数: start_time 和 end_time 为必填项"
}
```

---

### 4. 获取单个图片信息

获取指定ID的图片详细信息。

```
GET /api/images/{id}
```

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| id | int | 图片记录ID |

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
    "original_url": "https://api.telegram.org/file/...",
    "file_size": 102400,
    "width": 1920,
    "height": 1080,
    "created_at": 1700000000,
    "status": "available"
  }
}
```

**错误响应：**

```json
{
  "status": "error",
  "message": "图片不存在"
}
```

---

### 5. 获取图片文件

获取图片文件内容。

```
GET /api/file/{filename}
```

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| filename | string | 文件名（从 file_path 中提取） |

**状态码说明：**

| 状态码 | 状态 | 说明 |
|--------|------|------|
| 200 | `available` | 图片可用，返回文件内容（Content-Type: image/jpeg 等） |
| 202 | `downloading` | 图片正在下载中 |
| 404 | `not_found` | 图片不存在 |
| 410 | `expired` | 图片已过期被清理 |

**202 响应示例：**

```json
{
  "status": "downloading",
  "message": "文件正在下载中",
  "filename": "1700000000_12345_abc123.jpg"
}
```

**410 响应示例：**

```json
{
  "status": "expired",
  "message": "文件已过期",
  "filename": "1700000000_12345_abc123.jpg"
}
```

---

## 轮询策略

### 基本轮询流程

其他插件可以通过轮询接口获取新图片：

1. **首次请求**：`start_time=0&end_time=当前时间&exclude_ids=[]`
2. **记录返回的所有图片ID**
3. **下次请求**：`start_time=上次end_time&end_time=当前时间&exclude_ids=[已记录的图片ID]`
4. **重复步骤 2-3**

### 轮询示例

```python
import time
import json

class ComuPikPoller:
    def __init__(self, base_url="http://127.0.0.1:8080"):
        self.base_url = base_url
        self.known_ids = set()
        self.last_end_time = int(time.time()) - 3600  # 从1小时前开始
    
    def get_new_images(self):
        current_time = int(time.time())
        
        params = {
            "start_time": self.last_end_time,
            "end_time": current_time,
            "exclude_ids": json.dumps(list(self.known_ids)),
            "limit": 100
        }
        
        # 发送请求...
        # 记录新的图片ID
        # 更新 last_end_time
```

---

## 错误处理

### 通用错误格式

```json
{
  "status": "error",
  "message": "错误描述信息"
}
```

### 常见错误码

| HTTP 状态码 | 说明 |
|-------------|------|
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 410 | 资源已过期 |
| 500 | 服务器内部错误 |

---

## 配置说明

### API 服务器配置

在 AstrBot 管理页面的插件配置中：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `api_server.enabled` | bool | true | 是否启用API服务 |
| `api_server.host` | string | "127.0.0.1" | 监听地址 |
| `api_server.port` | int | 8080 | 监听端口 |

### 安全建议

1. **绑定本地地址**：建议将 `host` 设置为 `127.0.0.1`，通过反向代理对外提供服务
2. **防火墙配置**：如需外部访问，请配置防火墙规则限制访问来源
3. **HTTPS**：生产环境建议通过反向代理启用 HTTPS
