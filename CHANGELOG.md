# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/lang/zh-CN/spec/v2.0.0.html).

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
