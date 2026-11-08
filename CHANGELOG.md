# Changelog

## 0.3.0（睡眠修复与小时窗口同步）

### 新增

- 增量同步支持时间窗口：MCP `sync_data`、REST `POST /api/sync`、CLI `sync` 与 `SyncService` 新增 `hours_back` / `start_time` / `end_time`（epoch 秒）。心率、压力、血氧、异常心跳、运动可只拉最近 N 小时，单趟心率请求从约 1440 条降到约 60–120 条（取决于窗口内采样密度）。
- `POST /api/sync` 与同步服务接受 ISO 8601 时间（如 `2026-11-06T09:00:00`）；查询端点仍按日期查询，传入 ISO 时间会截断为日期。

### 改进

- 睡眠评分改为从日汇总接口（`daily_report` / `sleep`）补齐：主睡眠记录可取得 0–100 的评分；没有对应日汇总的记录（部分 `hlth.gen` 记录与小睡）仍可能为空。
- 睡眠分段状态码按实测重新映射：`1`/`2` = 深睡、`3` = 浅睡、`4` = REM、`5` = 清醒、`6` = 未分期（手机单段跟踪，按浅睡计入）。旧版本把 `2` 当浅睡、`4` 当清醒、`5` 当 REM，导致深睡数据缺失。
- 日聚合数据（步数、睡眠、体重）在窗口模式下仍按整天抓取，保证汇总值与评分完整。

### 修复

- 修复仅传 epoch 窗口时不带日期参数就无法请求的问题：`_fetch_key`、`_fetch_sport_records_by_time` 现在可直接按窗口拉取。
- 修复窗口模式缺少 `timezone` 导入导致的同步启动异常。
- 修复查询端点接受 ISO 8601 时间后按字符串比较、漏掉开始日的问题（现在统一截断为日期）。
- 修复同步窗口起止格式混用（一端日期、一端 ISO 时间）时结束时间被忽略或报错的问题。

### 升级注意

- **睡眠分段映射变化**：旧映射 `4` = 清醒、`5` = REM；新映射 `4` = REM、`5` = 清醒。重新同步历史数据后，已有记录的 REM 与清醒时长会按新映射更新，睡眠分期统计与旧版本不再可比。
- 无需数据库迁移。已有睡眠记录会在下次同步时按主键 UPSERT 更新，深睡分段与睡眠评分自动补齐；建议升级后先对最近 7 天做一次睡眠同步。
- 无破坏性 API 变更；`hours_back` / `start_time` / `end_time` 均为可选参数。

## 0.2.2（零第三方请求）

- 移除 Web 仪表盘与测试页的 Google Fonts 外链：打开页面不再向 Google 发送任何请求（此前浏览器会上传 IP/UA），改用系统字体栈，国内加载也更快、离线可渲染
- 发往小米的请求覆盖默认 `python-httpx/*` User-Agent 为浏览器 UA，去除脚本指纹（与 Cookie 登录来源一致）
- `docs/PRIVACY.md` 补充浏览器端零外链与最小化出站请求头说明

## 0.2.1（隐私加固）

- 数据安全审计文档 `docs/PRIVACY.md`：全部对外请求清单（仅小米域名）、本机数据存放表、威胁模型与自验方法
- CORS 收紧：默认仅允许本机来源（原来为 `*`，恶意网页可跨站读取本地健康数据）；可用 `MI_FITNESS_CORS_ORIGINS` 覆盖
- Host 头白名单中间件（FastAPI + Flask 双侧）：阻断 DNS 重绑定攻击；非回环绑定时 CLI 自动放行绑定地址，可用 `MI_FITNESS_ALLOWED_HOSTS` 覆盖
- API Key 的 passToken 迁出 SQLite 明文，改存系统 keyring（启动时自动迁移历史数据）；吊销时同步清理
- `api` 命令默认关闭 uvicorn 访问日志（查询参数不再落入终端）
- 新增 `GET /api/export`：本地数据导出为 JSON/CSV（含 Excel BOM），纯离线操作

## 0.2.0

- 内置 Web 仪表盘（`mi-fitness-mcp web`，Flask）：可视化测试全部 API 端点、Key 管理、扫码登录，内置反向代理（自动附加 X-API-Key/X-Admin-Key，上游耗时透传）
- REST API 服务（`mi-fitness-mcp api`，FastAPI）：全部数据端点 + 同步（前台/后台）+ 覆盖统计，交互式文档 `/docs`
- API Key 体系：`POST /api/auth/keys` 用小米凭据换取 `mif_sk_*` Key（类大模型平台风格），支持多账号上下文、last_used 统计、按前缀吊销；静态 Key 经 `MI_FITNESS_API_KEY`、管理端点经 `MI_FITNESS_ADMIN_KEY`
- 扫码登录：逆向小米通用扫码流程（`sid=xiaomiio`），`/api/auth/qr/start|poll` 生成二维码并轮询换取凭据后自动发放 Key，无需浏览器 F12
- Rust 测试页 `testpage/`（可选，内置 Web 仪表盘的 Rust 替代实现）
- 修复：`mcp` 依赖加上界 `<2`（MCP SDK 2.x 移除 `Server.list_tools` 导致启动崩溃）
- 文档：隐私与数据安全审计 `docs/PRIVACY.md`

## 0.1.0

- initial standalone `mi-fitness-mcp` repository
- Xiaomi auth via `userId + passToken`
- Mi Fitness cloud sync for steps, heart rate, calories, body measurements
- MCP tools for sync, summaries, heart rate, body measurements, coverage
