# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/lang/zh-CN/spec/v2.0.0.html).

## [1.1.1] - 2026-03-16

### Fixed

- 修复 save_image 方法名错误
  - ImageMessageHandler 中错误调用了 save_image()
  - FileManager 实际方法名为 save_file()
  - 修复后图片可以正常保存
  - 影响文件: `handlers/image_handler.py`

## [1.1.0] - 2026-03-16

### Changed

- 重构消息处理逻辑，采用接口+适配器设计模式
  - 新增 `handlers/` 模块目录结构
  - 定义 `MessageHandler` 抽象接口，统一处理器标准
  - 实现 `ImageMessageHandler` 适配器 - 处理直接发送的图片（Image组件）
  - 实现 `FileImageMessageHandler` 适配器 - 处理以文件形式发送的图片（File组件且为图片格式）
  - 实现 `MessageHandlerFactory` 工厂类 - 根据消息类型创建对应处理器（一对一映射）
  - 重构 `ImageHandler` 类 - 使用新的处理器架构，直接调用单一处理器
  - 保持与现有系统的兼容性，不破坏原有功能
  - 影响文件: `image_handler.py`, `handlers/` 目录

## [1.0.8] - 2026-03-16

### Added

- 支持识别以文件形式发送的图片
  - 新增 `_check_has_image` 方法，同时检查 `Image` 和 `File` 组件
  - 对于 `File` 组件，通过文件扩展名判断是否为图片文件
  - 支持常见图片格式：jpg, jpeg, png, gif, webp, bmp, tiff
  - 扩展名不区分大小写（.JPG 和 .jpg 都支持）
  - 影响文件: `image_handler.py`

## [1.0.7] - 2026-03-16

### Fixed

- 修复 download_file 调用缺少 path 参数的错误
  - `download_file` 函数需要提供 `path` 参数指定下载目标
  - 使用 `FileManager.tmp_dir` 作为临时下载目录，符合 AstrBot 存储规范
  - 下载完成后自动清理临时文件
  - 影响文件: `image_handler.py`

## [1.0.6] - 2026-03-16

### Fixed

- 修复 raw_message 访问 photo 属性的错误
  - `raw_message` 是 `telegram.Update` 对象
  - `photo` 属性在 `Update.message` 中，而不是直接在 `Update` 中
  - 修复图片无法被正确处理的问题
  - 影响文件: `image_handler.py`

## [1.0.5] - 2026-03-16

### Fixed

- 修复初始化成功通知重复发送的问题
  - 添加 `_init_notification_sent` 标志位
  - 确保初始化成功通知只发送一次
  - 影响文件: `main.py`

## [1.0.4] - 2026-03-16

### Fixed

- 修复初始化成功通知显示为错误通知的问题
  - 新增 `_send_notification` 方法用于发送普通通知
  - 初始化成功通知使用 ✅ 图标和友好的标题
  - 错误通知继续使用 🚨 图标
  - 影响文件: `main.py`

## [1.0.3] - 2026-03-16

### Fixed

- 修复 ImageHandler 注册错误
  - 移除 ImageHandler 类中的 `@filter` 装饰器
  - 将 `on_telegram_message` 方法重命名为 `process_telegram_message`
  - 在 ComuPikPlugin 主类中统一处理 Telegram 消息事件
  - 解决 `star_map` KeyError: 'data.plugins.astrbot_plugin_comupik.image_handler'
  - 影响文件: `image_handler.py`, `main.py`

## [1.0.2] - 2026-03-16

### Fixed

- 修复 PlatformManager 属性名错误
  - 将错误的属性名 `platform_adapters` 更正为 `platform_insts`
  - 修复错误通知功能无法正常发送的问题
  - 影响文件: `main.py`

## [1.0.1] - 2026-03-16

### Fixed

- 修复 TelegramPlatformEvent 导入路径错误
  - 将 `astrbot.core.platform.sources.telegram.telegram_message_event.TelegramMessageEvent`
  - 更正为 `astrbot.core.platform.sources.telegram.tg_event.TelegramPlatformEvent`
  - 影响文件: `main.py`, `image_handler.py`

## [1.0.0] - 2026-03-16

### Added

- 实现 Telegram 群组/频道图片自动监听与收集
- 基于感知哈希(pHash)的图片去重机制
- SQLite 数据库异步存储图片元数据
- RESTful API 服务，支持图片状态管理
- 文件管理模块，支持自动清理和并发锁
- 指数退避重试机制，提升网络操作稳定性
- 错误通知系统，支持向 super_admin 发送告警
- 新增配置模块 `config.py`
- 新增数据库模块 `database.py`
- 新增图片处理模块 `image_handler.py`
- 新增文件管理模块 `file_manager.py`
- 新增 API 服务模块 `api_server.py`
- 新增重试工具模块 `retry_utils.py`
- 新增指令 `/chatid`: 查询当前群组/频道 ID
- 新增指令 `/myid`: 查询当前用户 TG ID
- 支持监控目标配置(monitor_targets)
- 支持去重配置(deduplication_config)
- 支持 API 服务配置(api_enabled, api_host, api_port)
- 支持超级管理员配置(super_admin)
- 支持清理任务配置(cleanup_config)
