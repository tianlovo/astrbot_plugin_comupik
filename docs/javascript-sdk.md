# ComuPik JavaScript SDK

JavaScript SDK 用于在 JavaScript/TypeScript 项目中接入 ComuPik 图片服务。

## 安装

```bash
npm install comupik-sdk
# 或
yarn add comupik-sdk
```

## 快速开始

```javascript
import { ComuPikClient } from 'comupik-sdk';

const client = new ComuPikClient('http://127.0.0.1:8080');

// 获取统计信息
const stats = await client.getStats();
console.log(`总图片数: ${stats.totalImages}`);

// 轮询新图片
for await (const image of client.pollImages({ interval: 30 })) {
  console.log(`新图片: ${image.id} - ${image.filePath}`);
}
```

## 完整 SDK 代码

```typescript
/**
 * ComuPik JavaScript SDK
 * 
 * 提供便捷的 JavaScript/TypeScript 接口访问 ComuPik API 服务。
 */

export interface ImageInfo {
  id: number;
  messageId: string;
  chatId: string;
  senderId: string;
  senderName: string;
  timestamp: number;
  filePath: string;
  originalUrl: string;
  fileSize: number;
  width: number;
  height: number;
  createdAt: number;
  status: 'available' | 'downloading' | 'expired';
}

export interface StatsInfo {
  totalImages: number;
  totalSizeBytes: number;
  avgSizeBytes: number;
  chatCount: number;
  oldestTimestamp: number;
  newestTimestamp: number;
}

export interface ListImagesOptions {
  startTime: number;
  endTime: number;
  excludeIds?: number[];
  limit?: number;
  offset?: number;
}

export interface ListImagesResult {
  images: ImageInfo[];
  total: number;
  limit: number;
  offset: number;
}

export interface PollOptions {
  interval?: number;
  startFrom?: number;
}

export class ComuPikError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ComuPikError';
  }
}

export class APIError extends ComuPikError {
  statusCode?: number;
  
  constructor(message: string, statusCode?: number) {
    super(`API Error ${statusCode}: ${message}`);
    this.name = 'APIError';
    this.statusCode = statusCode;
  }
}

export class ImageNotFoundError extends ComuPikError {
  constructor(imageId: string | number) {
    super(`图片不存在: ${imageId}`);
    this.name = 'ImageNotFoundError';
  }
}

export class ImageExpiredError extends ComuPikError {
  constructor(filename: string) {
    super(`图片已过期: ${filename}`);
    this.name = 'ImageExpiredError';
  }
}

/**
 * ComuPik API 客户端
 * 
 * 提供便捷的接口访问 ComuPik 图片服务。
 * 
 * @example
 * ```typescript
 * const client = new ComuPikClient('http://127.0.0.1:8080');
 * 
 * // 获取统计信息
 * const stats = await client.getStats();
 * 
 * // 轮询新图片
 * for await (const image of client.pollImages({ interval: 30 })) {
 *   await processImage(image);
 * }
 * ```
 */
export class ComuPikClient {
  private baseUrl: string;
  private knownIds: Set<number> = new Set();
  private lastEndTime: number = Math.floor(Date.now() / 1000);

  /**
   * 创建客户端实例
   * @param baseUrl - API 基础 URL
   */
  constructor(baseUrl: string = 'http://127.0.0.1:8080') {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  /**
   * 发送 HTTP 请求
   */
  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    const data = await response.json();

    if (!response.ok) {
      throw new APIError(data.message || 'Unknown error', response.status);
    }

    return data;
  }

  /**
   * 健康检查
   * @returns 服务是否正常
   */
  async healthCheck(): Promise<boolean> {
    try {
      const data = await this.request<{ status: string }>('/api/health');
      return data.status === 'ok';
    } catch {
      return false;
    }
  }

  /**
   * 获取统计信息
   * @returns 统计信息
   */
  async getStats(): Promise<StatsInfo> {
    const data = await this.request<{ data: {
      total_images: number;
      total_size_bytes: number;
      avg_size_bytes: number;
      chat_count: number;
      oldest_timestamp: number;
      newest_timestamp: number;
    } }>('/api/stats');

    return {
      totalImages: data.data.total_images,
      totalSizeBytes: data.data.total_size_bytes,
      avgSizeBytes: data.data.avg_size_bytes,
      chatCount: data.data.chat_count,
      oldestTimestamp: data.data.oldest_timestamp,
      newestTimestamp: data.data.newest_timestamp,
    };
  }

  /**
   * 获取图片列表
   * @param options - 查询选项
   * @returns 图片列表和总数
   */
  async listImages(options: ListImagesOptions): Promise<ListImagesResult> {
    const params = new URLSearchParams({
      start_time: options.startTime.toString(),
      end_time: options.endTime.toString(),
      exclude_ids: JSON.stringify(options.excludeIds || []),
      limit: (options.limit || 100).toString(),
      offset: (options.offset || 0).toString(),
    });

    const data = await this.request<{
      data: {
        images: any[];
        total: number;
        limit: number;
        offset: number;
      };
    }>(`/api/images?${params}`);

    return {
      images: data.data.images.map(this.mapImageInfo),
      total: data.data.total,
      limit: data.data.limit,
      offset: data.data.offset,
    };
  }

  /**
   * 获取单个图片信息
   * @param imageId - 图片ID
   * @returns 图片信息
   */
  async getImage(imageId: number): Promise<ImageInfo> {
    try {
      const data = await this.request<{ data: any }>(`/api/images/${imageId}`);
      return this.mapImageInfo(data.data);
    } catch (error) {
      if (error instanceof APIError && error.statusCode === 404) {
        throw new ImageNotFoundError(imageId);
      }
      throw error;
    }
  }

  /**
   * 下载图片文件
   * @param filename - 文件名
   * @returns 图片 Blob 数据
   */
  async downloadImage(filename: string): Promise<Blob> {
    const url = `${this.baseUrl}/api/file/${filename}`;
    const response = await fetch(url);

    if (response.status === 200) {
      return response.blob();
    } else if (response.status === 202) {
      throw new ComuPikError('图片正在下载中，请稍后重试');
    } else if (response.status === 404) {
      throw new ImageNotFoundError(filename);
    } else if (response.status === 410) {
      throw new ImageExpiredError(filename);
    } else {
      throw new APIError('下载失败', response.status);
    }
  }

  /**
   * 下载并保存图片
   * @param filename - 文件名
   * @param saveName - 保存文件名
   */
  async downloadAndSave(filename: string, saveName?: string): Promise<void> {
    const blob = await this.downloadImage(filename);
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = saveName || filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    
    URL.revokeObjectURL(url);
  }

  /**
   * 轮询新图片（异步生成器）
   * @param options - 轮询选项
   */
  async *pollImages(options: PollOptions = {}): AsyncGenerator<ImageInfo> {
    const interval = options.interval || 30;
    
    if (options.startFrom) {
      this.lastEndTime = options.startFrom;
    }

    while (true) {
      const currentTime = Math.floor(Date.now() / 1000);

      try {
        const result = await this.listImages({
          startTime: this.lastEndTime,
          endTime: currentTime,
          excludeIds: Array.from(this.knownIds),
          limit: 100,
        });

        for (const image of result.images) {
          this.knownIds.add(image.id);
          yield image;
        }

        this.lastEndTime = currentTime;
      } catch (error) {
        console.error('轮询出错:', error);
      }

      await this.sleep(interval * 1000);
    }
  }

  /**
   * 重置轮询状态
   */
  resetPollState(): void {
    this.knownIds.clear();
    this.lastEndTime = Math.floor(Date.now() / 1000);
  }

  /**
   * 辅助方法：映射图片信息
   */
  private mapImageInfo(data: any): ImageInfo {
    return {
      id: data.id,
      messageId: data.message_id,
      chatId: data.chat_id,
      senderId: data.sender_id,
      senderName: data.sender_name,
      timestamp: data.timestamp,
      filePath: data.file_path,
      originalUrl: data.original_url,
      fileSize: data.file_size,
      width: data.width,
      height: data.height,
      createdAt: data.created_at,
      status: data.status,
    };
  }

  /**
   * 辅助方法：延迟
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// 默认导出
export default ComuPikClient;
```

## 使用示例

### 浏览器环境

```html
<!DOCTYPE html>
<html>
<head>
  <title>ComuPik 图片浏览器</title>
</head>
<body>
  <div id="gallery"></div>
  
  <script type="module">
    import { ComuPikClient } from 'comupik-sdk';
    
    const client = new ComuPikClient('http://127.0.0.1:8080');
    const gallery = document.getElementById('gallery');
    
    // 轮询新图片
    for await (const image of client.pollImages({ interval: 30 })) {
      if (image.status === 'available') {
        const img = document.createElement('img');
        img.src = `${client.baseUrl}/api/file/${image.filePath.split('/').pop()}`;
        img.style.maxWidth = '200px';
        gallery.appendChild(img);
      }
    }
  </script>
</body>
</html>
```

### Node.js 环境

```javascript
const { ComuPikClient } = require('comupik-sdk');
const fs = require('fs').promises;
const path = require('path');

async function main() {
  const client = new ComuPikClient('http://127.0.0.1:8080');
  const downloadDir = './downloads';
  
  // 确保下载目录存在
  await fs.mkdir(downloadDir, { recursive: true });
  
  // 轮询新图片
  for await (const image of client.pollImages({ interval: 30 })) {
    console.log(`收到新图片: ${image.id}`);
    
    if (image.status === 'available') {
      const filename = path.basename(image.filePath);
      
      try {
        const blob = await client.downloadImage(filename);
        const buffer = Buffer.from(await blob.arrayBuffer());
        
        await fs.writeFile(
          path.join(downloadDir, filename),
          buffer
        );
        
        console.log(`✓ 下载成功: ${filename}`);
      } catch (error) {
        console.error(`✗ 下载失败: ${filename}`, error.message);
      }
    }
  }
}

main().catch(console.error);
```

### React 组件示例

```jsx
import React, { useEffect, useState } from 'react';
import { ComuPikClient, ImageInfo } from 'comupik-sdk';

const ImageGallery = () => {
  const [images, setImages] = useState([]);
  const [stats, setStats] = useState(null);
  
  useEffect(() => {
    const client = new ComuPikClient('http://127.0.0.1:8080');
    
    // 加载初始统计
    client.getStats().then(setStats);
    
    // 轮询新图片
    const pollImages = async () => {
      for await (const image of client.pollImages({ interval: 30 })) {
        setImages(prev => [...prev, image]);
      }
    };
    
    pollImages();
    
    return () => {
      // 清理
    };
  }, []);
  
  return (
    <div>
      {stats && (
        <div className="stats">
          <h3>统计信息</h3>
          <p>总图片数: {stats.totalImages}</p>
          <p>总大小: {(stats.totalSizeBytes / 1024 / 1024).toFixed(2)} MB</p>
        </div>
      )}
      
      <div className="gallery">
        {images.map(image => (
          <div key={image.id} className="image-card">
            <img 
              src={`http://127.0.0.1:8080/api/file/${image.filePath.split('/').pop()}`}
              alt={`图片 ${image.id}`}
              style={{ maxWidth: '200px' }}
            />
            <p>发送者: {image.senderName}</p>
            <p>尺寸: {image.width}x{image.height}</p>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ImageGallery;
```

### Vue 3 组合式 API 示例

```vue
<template>
  <div>
    <div v-if="stats" class="stats">
      <h3>统计信息</h3>
      <p>总图片数: {{ stats.totalImages }}</p>
      <p>总大小: {{ formatSize(stats.totalSizeBytes) }}</p>
    </div>
    
    <div class="gallery">
      <div v-for="image in images" :key="image.id" class="image-card">
        <img 
          :src="getImageUrl(image)"
          :alt="`图片 ${image.id}`"
        />
        <p>发送者: {{ image.senderName }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { ComuPikClient } from 'comupik-sdk';

const images = ref([]);
const stats = ref(null);
let client = null;
let polling = true;

const formatSize = (bytes) => {
  const units = ['B', 'KB', 'MB', 'GB'];
  let size = bytes;
  for (const unit of units) {
    if (size < 1024) return `${size.toFixed(2)} ${unit}`;
    size /= 1024;
  }
  return `${size.toFixed(2)} TB`;
};

const getImageUrl = (image) => {
  const filename = image.filePath.split('/').pop();
  return `http://127.0.0.1:8080/api/file/${filename}`;
};

onMounted(async () => {
  client = new ComuPikClient('http://127.0.0.1:8080');
  
  // 获取统计
  stats.value = await client.getStats();
  
  // 轮询图片
  const poll = async () => {
    for await (const image of client.pollImages({ interval: 30 })) {
      if (!polling) break;
      images.value.push(image);
    }
  };
  
  poll();
});

onUnmounted(() => {
  polling = false;
});
</script>
```

## 错误处理

```javascript
import { 
  ComuPikClient, 
  ComuPikError, 
  APIError, 
  ImageNotFoundError,
  ImageExpiredError 
} from 'comupik-sdk';

const client = new ComuPikClient();

try {
  const image = await client.getImage(99999);
} catch (error) {
  if (error instanceof ImageNotFoundError) {
    console.log('图片不存在');
  } else if (error instanceof ImageExpiredError) {
    console.log('图片已过期');
  } else if (error instanceof APIError) {
    console.log(`API 错误: ${error.message} (状态码: ${error.statusCode})`);
  } else if (error instanceof ComuPikError) {
    console.log(`SDK 错误: ${error.message}`);
  } else {
    console.log(`未知错误: ${error.message}`);
  }
}
```

## TypeScript 类型支持

SDK 提供完整的 TypeScript 类型定义：

```typescript
import { 
  ComuPikClient, 
  ImageInfo, 
  StatsInfo, 
  ListImagesOptions,
  PollOptions 
} from 'comupik-sdk';

// 所有类型都有完整的定义
const client: ComuPikClient = new ComuPikClient();
const stats: StatsInfo = await client.getStats();
```
