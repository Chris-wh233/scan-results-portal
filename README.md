# Scan Results Portal

Scan Results Portal 是一个面向 Jenkins 和 csmock 的源码包（SRPM）扫描结果展示服务。

当前系统负责：

- 接收 Jenkins Pipeline 发送的 SRPM 扫描事件；
- 从 Jenkins Build API 获取构建信息和归档产物；
- 解析 csmock 生成的 scan.ini、summary、SARIF 和结果压缩包；
- 在网页中展示扫描任务、状态、结果摘要和产物；
- 将任务索引、扫描摘要和 finding 保存到 PostgreSQL；
- 将完整原始扫描产物继续保存在 Jenkins。

Scan Results Portal 不执行 csmock，csmock 由 Jenkins Agent 执行。

## 页面

源码包任务列表：

~~~text
/srpm
~~~

源码包任务详情：

~~~text
/srpm/{id}
~~~

任务列表按照扫描创建时间倒序排列，不按照 Jenkins Job 分组。Label 使用完整 SRPM 文件名，例如：

~~~text
curl-8.4.0-9.ocs23.src.rpm
~~~

任务由以下两个字段共同确定：

~~~text
jenkins_job_full_name + jenkins_build_number
~~~

因此，不同 Jenkins Job 可以使用相同的 Build Number。

## 扫描状态

任务状态只有以下四种：

~~~text
RUNNING
FINISHED
FAILED
NOT_AVAILABLE
~~~

- RUNNING：csmock 扫描阶段已经开始，但尚未结束；
- FINISHED：csmock 正常结束，Scan Results Portal 获取到了可解析的有效结果压缩包；
- FAILED：csmock 阶段本身失败，例如 csmock 返回非零状态、Mock 环境失败或输入 SRPM 无法处理；
- NOT_AVAILABLE：扫描阶段结束，但结果压缩包缺失、损坏、无法解压或缺少预期结果文件。

只有在 .tar.xz 能够正常解压，并且包含以下预期文件时，任务才会被标记为 FINISHED：

~~~text
scan.ini
scan-results-summary.txt
scan-results.js
scan-results.err
scan-results.html
scan.log
~~~

## 系统数据流

1. Jenkins Pipeline 在 csmock 阶段开始前发送 started 事件；
2. Scan Results Portal 创建任务并记录扫描开始时间；
3. Jenkins Agent 执行 csmock；
4. csmock 正常结束后，Pipeline 将 .tar.xz 归档到 Jenkins；
5. Pipeline 发送 completed 事件；
6. Scan Results Portal 通过 Jenkins API 获取 Build 和 Artifact；
7. 服务验证、解析并保存扫描结果；
8. 页面展示任务状态、结果摘要和产物链接。

csmock 阶段失败时，Pipeline 发送 failed 事件，不发送 completed 事件。

## Docker 部署

当前使用 Docker Compose 部署两个容器：

| 服务 | 容器名称 | 镜像 |
| --- | --- | --- |
| Scan Results Portal | scan-results-portal-service | scan-results-portal:latest |
| PostgreSQL | scan-results-portal-postgres | lcr.loongnix.cn/library/postgres:14-alpine3.23 |

PostgreSQL 数据保存到 Docker Volume：

~~~text
scanportal_pgdata
~~~

Scan Results Portal 对外提供端口：

~~~text
http://<宿主机>:8081
~~~

启动服务：

~~~bash
cp .env.example .env
docker compose up -d --build
~~~

健康检查：

~~~bash
curl http://127.0.0.1:8081/healthz
curl http://127.0.0.1:8081/readyz
~~~

## 配置

Compose 从 .env 读取敏感配置。至少需要设置：

~~~text
POSTGRES_PASSWORD=数据库密码
DATABASE_URL=postgresql+psycopg://scanportal:密码@postgres:5432/scanportal
JENKINS_BASE_URL=http://jenkins.example
JENKINS_USER=只读Jenkins账号
JENKINS_TOKEN=只读Jenkins API Token
SCAN_SERVICE_INGEST_TOKEN=供Jenkins回调使用的随机Bearer Token
~~~

数据库密码如果包含 URL 特殊字符，需要进行 URL 编码。

配置文件为：

~~~text
config/config.yaml
~~~

可以配置需要主动同步的 Jenkins Job：

~~~yaml
jenkins:
  jobs:
    - packages/curl
    - packages/openssl
  discovery:
    folders:
      - packages
    recursive: true
~~~

也可以使用环境变量：

~~~text
JENKINS_JOBS=packages/curl,packages/openssl
JENKINS_DISCOVERY_FOLDERS=packages
JENKINS_DISCOVERY_RECURSIVE=true
~~~

Jenkins Pipeline 主动发送事件时，事件中的 jenkins_job_full_name 必须使用完整 Job 名称。任务事件路径不要求该 Job 预先写入配置；Job 配置主要用于手动刷新和主动同步 Jenkins 构建。

## API

任务列表：

~~~text
GET /api/v1/srpm/tasks
~~~

任务详情：

~~~text
GET /api/v1/srpm/tasks/{id}
~~~

任务摘要和 finding：

~~~text
GET /api/v1/srpm/tasks/{id}/summary
GET /api/v1/srpm/tasks/{id}/findings
~~~

任务产物：

~~~text
GET /api/v1/srpm/tasks/{id}/artifacts
GET /api/v1/srpm/tasks/{id}/artifacts/{artifact_id}/view
GET /api/v1/srpm/tasks/{id}/artifacts/{artifact_id}/download
~~~

主动同步 Jenkins：

~~~text
POST /api/v1/srpm/sync
~~~

Jenkins 事件接口：

~~~text
POST /api/v1/srpm/events
~~~

事件接口需要请求头：

~~~text
Authorization: Bearer <SCAN_SERVICE_INGEST_TOKEN>
~~~

开始扫描示例：

~~~json
{
  "event": "started",
  "jenkins_job_full_name": "packages/curl",
  "jenkins_build_number": 15,
  "jenkins_build_url": "http://jenkins/job/packages/job/curl/15/",
  "srpm_name": "curl-8.4.0-9.ocs23.src.rpm",
  "created_at": "2026-09-24T10:00:00+08:00"
}
~~~

扫描失败示例：

~~~json
{
  "event": "failed",
  "jenkins_job_full_name": "packages/curl",
  "jenkins_build_number": 15,
  "srpm_name": "curl-8.4.0-9.ocs23.src.rpm",
  "finished_at": "2026-09-24T10:02:00+08:00",
  "csmock_exit_code": 2
}
~~~

扫描完成示例：

~~~json
{
  "event": "completed",
  "jenkins_job_full_name": "packages/curl",
  "jenkins_build_number": 15,
  "srpm_name": "curl-8.4.0-9.ocs23.src.rpm",
  "finished_at": "2026-09-24T10:02:00+08:00",
  "csmock_exit_code": 0
}
~~~

completed 事件表示 csmock 已正常退出，Pipeline 已执行归档阶段；它不直接代表 FINISHED。服务会重新读取 Jenkins Artifact 并验证结果压缩包。

## Jenkins Pipeline

当前 Pipeline 脚本位于：

[pipeline-script](/home/chris/proj/jenkins/pipeline-script)

该 Pipeline 使用以下 Jenkins 配置：

- Agent 标签：csbuild；
- Jenkins Credential ID：scan-service-ingest-token；
- Scan Results Portal 地址：http://10.130.43.224:8081；
- 扫描工具：csmock；
- Agent 中需要存在 python3、curl 和 csmock；
- 默认 SRPM 路径为 /home/hy/srpm-test/curl-8.4.0-9.ocs23.src.rpm；
- 通过参数 SRPM_PATH、MOCK_CONFIG 和 CSMOCK_TOOLS 调整扫描输入；
- 只执行 SRPM 扫描和扫描产物归档，不执行后续 RPM 构建。

Pipeline 归档的主要产物为：

~~~text
scan-artifacts/*.tar.xz
~~~

## 数据库

PostgreSQL 保存任务索引和结构化扫描结果，不保存完整原始压缩包。当前 SRPM 数据表为：

~~~text
srpm_scan_task
srpm_scan_artifact
srpm_scan_summary
srpm_scan_finding
~~~

数据库结构由 Alembic 管理，当前迁移版本为：

~~~text
0002_name_srpm_tables
~~~

## 代码结构

SRPM 业务代码集中在：

~~~text
app/scanservice/modules/srpm/
~~~

主要模块包括：

~~~text
models.py                    数据库模型
parsers/csmock.py            csmock 结果解析
csmock/archive.py            扫描压缩包处理
services/events.py           Jenkins 事件处理
services/synchronization.py  Jenkins 构建同步
services/task_service.py     任务查询和页面数据
services/artifacts.py        产物查看和下载
domain/state.py              SRPM 扫描状态定义
~~~

页面模板位于：

~~~text
app/scanservice/templates/
~~~

## 测试

测试应在容器中执行：

~~~bash
docker compose run --rm --entrypoint pytest scan-service -q
docker compose run --rm --entrypoint alembic scan-service current
~~~
