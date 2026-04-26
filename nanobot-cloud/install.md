# Nanobot Cloud — Mac mini 部署指南 (Docker)

## 目录

- [架构说明](#架构说明)
- [前置要求](#前置要求)
- [获取代码](#获取代码)
- [部署步骤](#部署步骤)
- [验证部署](#验证部署)
- [API 使用示例](#api-使用示例)
- [日常操作](#日常操作)
- [环境变量说明](#环境变量说明)
- [修改配置](#修改配置)
- [故障排查](#故障排查)
- [完整功能部署（Linux / KVM）](#完整功能部署linux--kvm)

---

## 架构说明

Mac 上的 Docker Desktop **不支持 `/dev/kvm`**，因此 Firecracker 微虚拟机无法运行。  
但以下功能**完全可用**：

| 功能 | Mac Docker | Linux KVM |
|------|-----------|-----------|
| 用户注册 / 登录 | ✅ | ✅ |
| Agent 配置管理 | ✅ | ✅ |
| System Prompt 管理 | ✅ | ✅ |
| Skills 管理 | ✅ | ✅ |
| MCP 服务器管理 | ✅ | ✅ |
| PostgreSQL 持久化 | ✅ | ✅ |
| MinIO 对象存储 | ✅ | ✅ |
| Firecracker VM 沙箱 | ❌ | ✅ |
| /chat 发送消息 | ❌ | ✅ |

服务组成：

```
┌─────────────────────────────────────────────┐
│  Mac mini (Docker Desktop)                  │
│                                             │
│  ┌──────────────┐   ┌───────────────────┐  │
│  │ control-plane│   │    PostgreSQL 16   │  │
│  │  FastAPI :8000│◄─►│    :5432          │  │
│  └──────┬───────┘   └───────────────────┘  │
│         │                                   │
│         │           ┌───────────────────┐  │
│         └──────────►│    MinIO          │  │
│                     │    API  :9000     │  │
│                     │    Console :9001  │  │
│                     └───────────────────┘  │
└─────────────────────────────────────────────┘
```

---

## 前置要求

### 1. 安装 Docker Desktop for Mac

前往 [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/) 下载并安装。

安装后启动 Docker Desktop，确认状态栏图标变为运行状态。

验证安装：

```bash
docker version
docker compose version
```

Docker Engine 版本需 >= 24.0，Compose 版本需 >= 2.20。

### 2. 确认可用磁盘空间

Docker 镜像 + 数据卷约需 **2 GB** 空间：

```bash
df -h ~
```

### 3. 安装 Git（如未安装）

```bash
# 通过 Homebrew 安装
brew install git

# 或者安装 Xcode Command Line Tools
xcode-select --install
```

---

## 获取代码

```bash
# 克隆仓库
git clone <仓库地址>
cd note/nanobot-cloud
```

目录结构：

```
nanobot-cloud/
├── control-plane/        # FastAPI 后端
├── deploy/
│   ├── Dockerfile.control-plane
│   ├── docker-compose.mac.yaml   # Mac 专用 compose
│   └── docker-compose.yaml       # 完整版（需要 KVM）
├── migrations/           # Alembic 数据库迁移
├── scripts/
│   └── start-mac.sh     # 一键启动脚本
└── install.md            # 本文档
```

---

## 部署步骤

### 步骤一：确认 Docker Desktop 已启动

```bash
docker info
```

输出中应包含 `Server Version`，无报错。

### 步骤二：进入项目目录

```bash
cd nanobot-cloud
```

### 步骤三：启动所有服务

```bash
./scripts/start-mac.sh
```

该脚本会自动完成：
1. 构建 `control-plane` Docker 镜像（首次约 2-3 分钟）
2. 拉取 `postgres:16-alpine` 和 `minio/minio` 镜像
3. 按依赖顺序启动服务（postgres → minio → control-plane）
4. 等待 `/health` 接口返回 200

正常输出示例：

```
[nanobot-cloud] building and starting services...
[+] Building 45.3s (10/10) FINISHED
[+] Running 3/3
 ✔ Container nanobot-cloud-postgres-1      Healthy
 ✔ Container nanobot-cloud-minio-1         Healthy
 ✔ Container nanobot-cloud-control-plane-1 Started
[nanobot-cloud] waiting for control-plane to be ready...
[nanobot-cloud] ✓ nanobot-cloud is ready!

  API:           http://localhost:8000
  Health check:  http://localhost:8000/health
  API docs:      http://localhost:8000/docs
  MinIO console: http://localhost:9001  (minioadmin / minioadmin123)
```

### 步骤四：验证服务健康状态

```bash
# 检查所有容器状态
./scripts/start-mac.sh ps

# 应输出类似：
# NAME                              STATUS          PORTS
# nanobot-cloud-control-plane-1    Up              0.0.0.0:8000->8000/tcp
# nanobot-cloud-minio-1             Up (healthy)    0.0.0.0:9000->9000/tcp
# nanobot-cloud-postgres-1          Up (healthy)    0.0.0.0:5432->5432/tcp
```

---

## 验证部署

### 健康检查

```bash
curl http://localhost:8000/health
# 返回: {"status":"ok"}
```

### 注册用户

```bash
curl -s -X POST http://localhost:8000/users/register \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "MyPassword123"}' | python3 -m json.tool
```

返回：

```json
{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "alice"
}
```

### 登录获取 Token

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/users/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "MyPassword123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "Token: $TOKEN"
```

### 查看当前用户

```bash
curl -s http://localhost:8000/users/me \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

---

## API 使用示例

以下示例均假设已将 Token 存入 `$TOKEN` 变量（见上方登录步骤）。

### Agent 配置

```bash
# 设置 Agent 配置（providers / models 等）
curl -s -X PUT http://localhost:8000/config/agent \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "providers": {
        "openrouter": {"apiKey": "sk-or-xxxxx"}
      },
      "agents": {
        "defaults": {"model": "anthropic/claude-sonnet-4-6"}
      }
    }
  }'

# 读取 Agent 配置
curl -s http://localhost:8000/config/agent \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

### System Prompt

```bash
# 设置 System Prompt
curl -s -X PUT http://localhost:8000/config/prompt \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "你是一个专注于代码审查的 AI 助手，回复简洁精准。"}'

# 读取当前 Prompt
curl -s http://localhost:8000/config/prompt \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

### Skills 管理

```bash
# 创建 Skill
curl -s -X POST http://localhost:8000/config/skills \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "write_file",
    "content": "# Write File\nUse the write_file tool to create or overwrite files.",
    "skill_type": "markdown"
  }'

# 列出所有 Skills
curl -s http://localhost:8000/config/skills \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 删除 Skill（替换 <skill_id> 为实际 ID）
curl -s -X DELETE http://localhost:8000/config/skills/<skill_id> \
  -H "Authorization: Bearer $TOKEN"
```

### MCP 服务器管理

```bash
# 添加 MCP 服务器（stdio 类型）
curl -s -X POST http://localhost:8000/config/mcp \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "github",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-github"],
    "env": {"GITHUB_TOKEN": "ghp_your_token_here"}
  }'

# 添加 MCP 服务器（HTTP 类型）
curl -s -X POST http://localhost:8000/config/mcp \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "remote_tool",
    "url": "https://mcp.example.com/v1"
  }'

# 列出 MCP 服务器（env 字段加密存储，不会返回明文）
curl -s http://localhost:8000/config/mcp \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

### 查看 VM 状态

```bash
# 查看当前用户的 VM 状态（Mac 上始终返回 stopped）
curl -s http://localhost:8000/chat/status \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 管理员查看所有 VM（无需认证）
curl -s http://localhost:8000/admin/vms | python3 -m json.tool
```

### 交互式 API 文档

打开浏览器访问 [http://localhost:8000/docs](http://localhost:8000/docs)，可在页面上直接测试所有接口。

---

## 日常操作

### 启动服务

```bash
./scripts/start-mac.sh
```

### 停止服务（保留数据）

```bash
./scripts/start-mac.sh stop
# 或者直接：
docker compose -f deploy/docker-compose.mac.yaml down
```

### 停止服务并清除所有数据

```bash
docker compose -f deploy/docker-compose.mac.yaml down -v
```

> **注意**：`-v` 会删除 PostgreSQL 和 MinIO 的数据卷，所有数据将丢失。

### 查看实时日志

```bash
# 所有服务的日志
./scripts/start-mac.sh logs

# 只看 control-plane 的日志
docker compose -f deploy/docker-compose.mac.yaml logs -f control-plane

# 只看 postgres 的日志
docker compose -f deploy/docker-compose.mac.yaml logs -f postgres
```

### 查看服务状态

```bash
./scripts/start-mac.sh ps
```

### 重新构建镜像（代码有更新时）

```bash
docker compose -f deploy/docker-compose.mac.yaml up --build -d
```

### 进入容器 shell（调试用）

```bash
# 进入 control-plane 容器
docker compose -f deploy/docker-compose.mac.yaml exec control-plane bash

# 进入 postgres 容器
docker compose -f deploy/docker-compose.mac.yaml exec postgres psql -U nanobot
```

---

## 环境变量说明

所有变量在 `deploy/docker-compose.mac.yaml` 的 `control-plane.environment` 中配置：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `NC_DATABASE_URL` | `postgresql+asyncpg://nanobot:nanobot@postgres:5432/nanobot` | 异步数据库连接（asyncpg） |
| `NC_DATABASE_URL_SYNC` | `postgresql://nanobot:nanobot@postgres:5432/nanobot` | 同步数据库连接（Alembic 迁移用） |
| `NC_S3_ENDPOINT` | `http://minio:9000` | MinIO/S3 地址 |
| `NC_S3_BUCKET` | `nanobot-data` | 存储桶名称 |
| `NC_S3_ACCESS_KEY` | `minioadmin` | S3 访问密钥 |
| `NC_S3_SECRET_KEY` | `minioadmin123` | S3 密钥 |
| `NC_JWT_SECRET` | `dev-secret-change-in-prod` | JWT 签名密钥（**生产环境必须修改**） |
| `NC_ENCRYPTION_KEY` | `dev-enc-key-32-bytes-padded-here` | MCP env 字段 Fernet 加密密钥（**生产环境必须修改**）|
| `NC_VM_IDLE_TIMEOUT` | `1800` | VM 空闲超时秒数（30 分钟） |
| `NC_VM_REAPER_INTERVAL` | `60` | 空闲检查间隔秒数 |

---

## 修改配置

### 修改 JWT 密钥（推荐生产前修改）

编辑 `deploy/docker-compose.mac.yaml`：

```yaml
NC_JWT_SECRET: "替换为一个随机长字符串"
NC_ENCRYPTION_KEY: "恰好32字节的base64字符串============"
```

生成随机密钥：

```bash
# 生成 JWT_SECRET
openssl rand -hex 32

# 生成 ENCRYPTION_KEY（32 字节 base64）
python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

修改后重启服务：

```bash
docker compose -f deploy/docker-compose.mac.yaml up -d
```

### 修改端口映射

如果 8000 端口被占用，修改 `deploy/docker-compose.mac.yaml`：

```yaml
ports:
  - "8080:8000"   # 改为本地 8080 端口
```

---

## 故障排查

### 问题：Docker Desktop 未启动

```
Cannot connect to the Docker daemon at unix:///var/run/docker.sock
```

解决：打开 Docker Desktop 应用，等待状态栏图标变为运行状态。

---

### 问题：端口被占用

```
Error: bind: address already in use
```

查看占用端口的进程：

```bash
lsof -i :8000
lsof -i :5432
lsof -i :9000
```

停止占用进程，或修改 compose 文件中的端口映射。

---

### 问题：control-plane 启动失败（数据库连接失败）

```bash
# 查看详细日志
docker compose -f deploy/docker-compose.mac.yaml logs control-plane
```

常见原因：postgres 还未完全就绪。等待 10 秒后重启：

```bash
docker compose -f deploy/docker-compose.mac.yaml restart control-plane
```

---

### 问题：镜像构建失败（网络超时）

```bash
# 使用国内镜像源（如需）
# 在 Docker Desktop 设置 → Docker Engine 中添加：
{
  "registry-mirrors": ["https://mirror.ccs.tencentyun.com"]
}
```

---

### 问题：MinIO 健康检查失败

```bash
docker compose -f deploy/docker-compose.mac.yaml logs minio
```

通常是磁盘空间不足，清理 Docker 无用镜像：

```bash
docker system prune -f
```

---

### 完全重置（清除所有容器和数据）

```bash
docker compose -f deploy/docker-compose.mac.yaml down -v --remove-orphans
docker rmi nanobot-cloud-control-plane 2>/dev/null || true
./scripts/start-mac.sh
```

---

## 完整功能部署（Linux / KVM）

要运行 Firecracker VM 沙箱（`/chat` 接口），需要：

1. **Linux 主机**，内核 >= 5.10，支持 KVM
2. **验证 KVM 可用**：
   ```bash
   ls -la /dev/kvm
   # 应显示: crw-rw---- 1 root kvm ...
   ```
3. **构建 Firecracker 镜像和内核**：
   ```bash
   cd build && make all
   ```
4. **使用完整 compose 文件**：
   ```bash
   docker compose -f deploy/docker-compose.yaml up -d
   ```

云服务器选择建议：
- 阿里云 ECS：选择「支持嵌套虚拟化」的实例规格（如 ecs.g7ne 系列）
- AWS EC2：选择 metal 实例或开启嵌套虚拟化的 .metal 规格
- 自建裸金属服务器：直接支持 KVM
