# Jenkins + csmock Scan Results Portal

这是一个面向 LoongArch64 Jenkins/csmock CI 的轻量扫描结果门户 Scan Results Portal。第一版提供：

    /tasks
    /tasks/{id}

服务从 Jenkins Build API 读取构建和产物，解析包信息与扫描问题，再使用 PostgreSQL 保存可查询的任务索引。

当前实现采用“Jenkins 为真源、Scan Results Portal 为展示读模型”的方式：定时/手动同步负责恢复一致性；Jenkins 也可以通过受保护的回调接口提前登记任务和生命周期事件。

## 本地配置

    cp .env.example .env

Compose 只会自动读取文件名为 `.env` 的文件，不会读取 `.env.example`。请编辑新生成的 `.env`，不要提交它：

    编辑 .env，至少设置：

    POSTGRES_PASSWORD=...
    DATABASE_URL=postgresql+psycopg://scanportal:密码@postgres:5432/scanportal
    JENKINS_USER=只读Jenkins账号
    JENKINS_TOKEN=只读Jenkins API Token
    SCAN_SERVICE_INGEST_TOKEN=供Jenkins回调使用的随机Bearer Token

如果密码包含 URL 特殊字符，需要进行 URL 编码。

## 启动

安装 Compose v2 后执行：

    docker compose up -d --build

服务地址：

    http://10.130.43.224:8081/tasks

检查：

    curl http://127.0.0.1:8081/healthz
    curl http://127.0.0.1:8081/readyz

## 测试

    docker compose run --rm --entrypoint pytest scan-service -q
    docker compose run --rm --entrypoint alembic scan-service current

## Jenkins 产物约定

Jenkins 每次构建归档:

    csmock 生成的 tar.xz

其中包含的 scan.ini、scan-results-summary.txt、scan-results.js、scan-results.err、scan-results.html、scan.log 文件提取出来和 tar.xz 一并展示。

接入 Jenkins 的建议顺序和示例见 [docs/jenkins-integration.md](docs/jenkins-integration.md)。不修改现有 Jenkins Job 也可以先使用 `/tasks` 页面上的 Refresh 或调用 `POST /api/v1/sync` 发现最近构建。

## 回调接口

配置 `SCAN_SERVICE_INGEST_TOKEN` 后，Jenkins 可使用以下接口；请求头为 `Authorization: Bearer <token>`：

    POST  /api/v1/tasks
    PATCH /api/v1/tasks/{id}
    POST  /api/v1/tasks/{id}/scan-failed
    POST  /api/v1/tasks/{id}/scan-complete

任务注册时状态为 `RUNNING`，Scan Results Portal 记录 csmock 阶段开始时间。csmock 阶段失败时回调 `scan-failed`，正常结束并完成 Jenkins 归档后回调 `scan-complete`。后者不会直接设置 `FINISHED`，服务会验证 `.tar.xz` 及预期文件；验证成功为 `FINISHED`，否则为 `NOT_AVAILABLE`。artifact 仍从 Jenkins 拉取。

## 设计约束

- 一个 Jenkins Build 对应一个 RPM 包的一次扫描。
- Scan Results Portal 不参与 csmock 执行。
- Scan Results Portal 不作为 Jenkins Gate 的强依赖。
- 同步以 Jenkins Build Number 为幂等键。
- Console Output 只用于排错。
- PostgreSQL 不存储大型原始日志和 debug 目录。
=======
# scan-results-portal
