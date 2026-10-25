# 信息门户 CAS 登录扩展

本文档描述当前 fork 中基于华南农业大学信息门户 CAS 的登录扩展。当前状态是最小可用版本，只实现登录和本地会话状态查询，不包含课表、成绩、通知或其他业务数据接口。

## 范围与边界

- 登录目标：`https://portal.scau.edu.cn` 的统一认证入口。
- 登录方式：真实 Chrome 浏览器自动化，通过 CDP 操作官方登录页，不逆向密码加密逻辑。
- 对外能力：MCP 工具 `portal_status` 和 `portal_login`。
- 当前不包含：课表、成绩、通知、文件下载、表单提交和选课等写操作。
- 当前不修改 WebUI、TUI 或智能体核心循环。

## 架构

```text
nanobot agent
  -> enabled Agent Plugin: school-portal
      -> bundled Skill: skills/school-portal/SKILL.md
      -> MCP stdio server: nanobot-school-portal-mcp
          -> SchoolPortalService
              -> cas_driver: 临时 headless Chrome + CDP
                  -> 官方 CAS 登录页
                  -> CASTGC / customsid / Authorization Cookie
              -> PortalSessionStore
                  -> PLUGIN_DATA/session.json
```

浏览器只负责认证，后续业务读取应复用保存的 HTTP 会话，不需要为每个请求启动浏览器。

## 代码位置

| 内容 | 路径 |
|---|---|
| Agent Plugin 包 | [`extensions/agent-plugins/school-portal`](../agent-plugins/school-portal) |
| Plugin manifest | [`plugin.json`](../agent-plugins/school-portal/plugin.json) |
| Plugin MCP 声明 | [`mcp.json`](../agent-plugins/school-portal/mcp.json) |
| MCP 入口 | [`server.py`](../nanobot_ext/src/nanobot_ext/school_portal/server.py) |
| 登录驱动 | [`cas_driver.py`](../nanobot_ext/src/nanobot_ext/school_portal/cas_driver.py) |
| 凭证、会话和登录编排 | [`service.py`](../nanobot_ext/src/nanobot_ext/school_portal/service.py) |
| Skill | [`SKILL.md`](../agent-plugins/school-portal/skills/school-portal/SKILL.md) |
| 示例凭证 | [`credentials.example.json`](../agent-plugins/school-portal/examples/credentials.example.json) |
| 测试 | [`test_school_portal.py`](../nanobot_ext/tests/test_school_portal.py) |

## 登录流程

1. MCP server 从本地凭证文件或环境变量读取学号和密码。
2. 启动临时 headless Chrome，使用独立临时 profile 和随机 CDP 端口。
3. 打开官方 CAS 登录页，注入隐藏 `navigator.webdriver` 的脚本。
4. 填入学号和密码，点击登录，由官方页面自己的 JavaScript 完成密码变换和提交。
5. 轮询页面地址，进入 `portal.scau.edu.cn` 后判定登录成功。
6. 从浏览器收割学校域名的 Cookie 和 localStorage，关闭 Chrome 并删除临时 profile。
7. 将安全字段写入本地会话文件，只向调用方返回用户名和登录结果。

## 凭证配置

启用 Agent Plugin 后，MCP server 会获得独立的 `PLUGIN_DATA` 目录。默认凭证文件位于：

```text
PLUGIN_DATA/credentials.json
```

如果缺失，`portal_status` 的错误信息会给出当前实例的准确路径。可以从插件的示例文件复制：

```bash
mkdir -p "$PLUGIN_DATA"
cp extensions/agent-plugins/school-portal/examples/credentials.example.json \
  "$PLUGIN_DATA/credentials.json"
```

文件格式：

```json
{
  "username": "your-student-id",
  "password": "your-password"
}
```

建议权限：

```bash
chmod 700 "$PLUGIN_DATA"
chmod 600 "$PLUGIN_DATA/credentials.json"
```

也可以用环境变量代替文件：

```text
NANOBOT_SCHOOL_PORTAL_USERNAME
NANOBOT_SCHOOL_PORTAL_PASSWORD
```

密码不会通过 MCP 工具参数传入，也不会写入会话文件或日志。

## 会话存储

启用插件后，会话文件位于：

```text
PLUGIN_DATA/session.json
```

文件权限应为 `600`。内容包含用户名、登录时间、学校域名 Cookie 和 localStorage；不包含密码。会话文件属于敏感数据，不能提交到 Git，也不要通过聊天工具发送。

当前 `portal_status` 只检查本地会话文件是否存在，不代表服务端会话一定仍有效。后续应增加只读 HTTP 校验接口。

## Agent Plugin 安装

先安装 Python 扩展，使 `nanobot-school-portal-mcp` 命令可用：

```bash
uv sync --all-extras --dev
uv run --no-sync python -m scripts.install_channel_dependencies --all-channels
```

把插件目录复制到 workspace：

```bash
mkdir -p ~/.nanobot/workspace/plugins
cp -R extensions/agent-plugins/school-portal \
  ~/.nanobot/workspace/plugins/school-portal
```

打开 WebUI 的 **Apps** 页面，审核并启用 `school-portal`。只复制目录不会激活插件。

插件启用后重启网关：

```bash
cd /Users/dcj/ai/nanobot
uv run --no-sync nanobot gateway restart
```

插件的 `mcp.json` 会自动声明 MCP server，`skills/school-portal/SKILL.md` 会随插件加载，不需要手动编辑 `tools.mcpServers` 或创建 workspace Skill 链接。

在 nanobot 中，MCP 工具通常显示为：

```text
mcp_school-portal_portal_status
mcp_school-portal_portal_login
```

## Skill

Skill 随 Agent Plugin 打包，源码位于：

```text
extensions/agent-plugins/school-portal/skills/school-portal/SKILL.md
```

Skill 的规则包括：先查询状态、只在未登录时登录、不要把密码粘贴到聊天、不要输出 Cookie/JWT、遇到验证码或二次验证时停止自动流程。

## CAS SSO 换票

当前已保存的 `CASTGC` 可以用于其他接入 CAS 的应用，流程如下：

1. 从本地会话中读取 `CASTGC`。
2. 向 CAS REST 接口换 Service Ticket：

```http
POST https://cas.scau.edu.cn/lyuapServer/v1/tickets/{CASTGC}
Content-Type: application/x-www-form-urlencoded

service=<目标系统 service URL>
```

3. 接口返回 HTTP 200，响应体为 `ST-...`。
4. 请求 `<service>?ticket=ST-...`，跟随目标系统的重定向。
5. 目标系统会种下自己的会话 Cookie，例如 `JSESSIONID`、`.loginAuth` 或 `ASP.NET_SessionId`。

对于带入口中间页的系统，要按页面生成的完整 `sid`、`screen` 参数继续访问，不能只访问裸路径。

目前 SSO 换票是已验证的 HTTP 操作模式，还没有封装成正式的 MCP 工具；`portal_login` 和 `portal_status` 仍是当前唯一正式暴露的能力。

## 已验证系统

| 系统 | 入口 | 结果 |
|---|---|---|
| 本科毕业论文系统 | `https://bkbylw.scau.edu.cn/tyrzdl.aspx` | 完整进入，主菜单和主内容 iframe 均为 HTTP 200，标题为“华南农业大学毕业设计（论文）智能管理系统” |
| 新教务系统 | `https://jwzf.scau.edu.cn/sso/lyiotlogin` | CAS 登录成功，主页面 HTTP 200，标题为“教学管理信息服务平台” |

新教务系统的主页面 iframe 指向 `http://127.0.0.1/...`，该地址在当前机器无法连接。这是页面地址配置异常，不影响 CAS 认证成功；主页面已经进入。

验证过程中没有重新提交密码，也没有输出 ST、Cookie 值、`sid` 或其他会话秘密。

## 已知限制

- `portal_status` 仅依据本地会话文件，不进行服务端有效性校验。
- 不保存密码，因此会话过期后不能自动重登，只能重新调用 `portal_login`。
- headless Chrome 依赖本机 Chrome；如果学校改版登录页或加强 WAF，选择器和流程可能需要调整。
- 会话文件是 `600` 权限的普通 JSON，不是加密存储；长期可以迁移到 macOS Keychain。
- SSO 换票尚未封装为 MCP 工具。
- 当前没有实现课表、成绩、通知等业务读取。

## 排障

| 现象 | 处理 |
|---|---|
| `未配置学校门户凭证` | 填写 `credentials.json` 或设置两个环境变量 |
| `chrome_not_found` | 确认 Chrome 已安装，或设置 `NANOBOT_SCHOOL_PORTAL_CHROME` |
| `form_not_found` | 检查登录页是否改版，查看 `PLUGIN_DATA/last-login-timeout.png` |
| `CAPTCHA_REQUIRED` / 滑块 | 先到官网正常登录一次解除风控，不要反复自动重试 |
| `PASSERROR` | 检查密码；连续失败可能触发账号风控 |
| `TWOVERIFY` | 当前范围不支持二次验证 |
| `portal_status` 报告已登录但接口返回 401 | 本地会话已过期，重新调用 `portal_login` |

查看网关日志：

```bash
cd /Users/dcj/ai/nanobot
uv run --no-sync nanobot gateway logs
```

## 安全要求

- 不提交 `credentials.json`、`session.json`、诊断截图或任何 Cookie/JWT。
- 不在聊天、日志、Issue 或 PR 中粘贴密码、CASTGC、ST、sid 或 Authorization。
- MCP 登录工具不接受密码参数，凭证只从本地文件或受控环境变量读取。
- 当前功能只允许 GET 和登录所需的 CAS 请求，不实现业务写操作。
- 任何新增的门户读取功能都应先明确鉴权方式、权限边界和脱敏策略。

## 验证命令

```bash
uv run --no-sync pytest extensions/nanobot_ext/tests -q
uv run --no-sync ruff check extensions/nanobot_ext
```

2026-10-25 已完成真实登录测试、MCP 握手测试和两个应用的 SSO 访问验证。
