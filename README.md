# Scan Results Portal

Scan Results Portal 是一个面向 Jenkins 的软件包扫描结果展示服务。目前支持
csmock 的源码包（SRPM）扫描结果，以及 cve-bin-tool 的二进制 RPM 漏洞扫描结果。

当前系统负责：

- 接收 Jenkins Pipeline 发送的扫描事件（SRPM 与 RPM）；
- 从 Jenkins Build API 获取构建信息和归档产物；
- 解析扫描结果（SRPM 为 csmock 产物，RPM 为 cve-bin-tool 产物）；
- 在网页中展示扫描任务、状态、结果摘要和产物；
- 将任务索引、扫描摘要和 finding 保存到 PostgreSQL；
- 将完整原始扫描产物继续保存在 Jenkins。

两种扫描由不同的 agent 执行，结果各自写入独立的表：

| 扫描类型 | 扫描工具 | 执行者 | 结果表 |
| --- | --- | --- | --- |
| SRPM | csmock | 待开发） | srpm_scan_* |
| RPM | cve-bin-tool | rpm-scan-agent | rpm_scan_* |

本服务是 `scan-service` 扫描服务栈的一员，与 `rpm-scan-agent`、PostgreSQL
一起由上级目录的 `docker-compose.yml` 统一管理。

## 扫描状态

SRPM 与 RPM 共用以下四种状态：

~~~text
RUNNING
FINISHED
FAILED
NOT_AVAILABLE
~~~

- RUNNING：扫描已开始，但尚未结束；
- FINISHED：扫描正常结束，Scan Results Portal 获取到了可解析的有效结果；
- FAILED：扫描阶段本身失败，例如扫描工具返回失败、构建环境异常或输入包无法处理；
- NOT_AVAILABLE：扫描阶段结束，但结果缺失、损坏、无法解压或缺少预期结果文件。

判定 FINISHED 的条件两者不同。

SRPM：结果 .tar.xz 能够正常解压，并且包含以下预期文件：

~~~text
scan.ini
scan-results-summary.txt
scan-results.js
scan-results.err
scan-results.html
scan.log
~~~

RPM：归档中存在 `scan-manifest.json` 与 `scan-results.json`，两者校验通过，
且 cve-bin-tool 退出码为 0 或 1（1 表示发现漏洞）。

## 系统数据流

1. Jenkins Pipeline 在扫描阶段开始前发送 started 事件；
2. Scan Results Portal 创建任务并记录扫描开始时间；
3. Jenkins Agent 执行扫描（SRPM 用 csmock，RPM 用 cve-bin-tool）；
4. 扫描正常结束后，Pipeline 将结果产物归档到 Jenkins；
5. Pipeline 发送 completed 事件；
6. Scan Results Portal 通过 Jenkins API 获取 Build 和 Artifact；
7. 服务验证、解析并保存扫描结果；
8. 页面展示任务状态、结果摘要和产物链接。

扫描阶段失败时，Pipeline 发送 failed 事件，不发送 completed 事件。

## Docker 部署

门户作为 `scan-service` 扫描服务栈的一部分部署，由上一级目录的
`docker-compose.yml` 统一编排；运行时配置集中在 `.env` 的 
`scan-results-portal` 分区。

| 服务 | 容器名称 | 镜像 |
| --- | --- | --- |
| Scan Results Portal | scan-results-portal-service | scan-results-portal:latest |
| PostgreSQL | scan-results-portal-postgres | lcr.loongnix.cn/library/postgres:14-alpine3.23 |

PostgreSQL 数据保存到 Docker Volume（显式固定卷名，跨项目名稳定）：

~~~text
scanportal_pgdata
~~~

Scan Results Portal 对外提供端口：

~~~text
http://<宿主机>:8081
~~~

启动服务（在 scan-service 目录执行）：

~~~bash
cp .env.example .env
docker compose up -d --build scan-results-portal
~~~

健康检查：

~~~bash
curl http://127.0.0.1:8081/healthz
curl http://127.0.0.1:8081/readyz
~~~

## 配置

门户的运行时配置位于 scan-service 目录下 .env 的 `scan-results-portal`
分区，由 compose 注入。至少需要设置：

~~~text
DATABASE_URL=postgresql+psycopg://scanportal:密码@postgres:5432/scanportal
JENKINS_BASE_URL=http://jenkins.example
JENKINS_USER=只读Jenkins账号
JENKINS_TOKEN=只读Jenkins API Token
SCAN_SERVICE_INGEST_TOKEN=供Jenkins回调使用的随机Bearer Token
~~~

数据库初始化密码 `POSTGRES_PASSWORD` 位于同一 .env 的 `postgres` 分区，需与
DATABASE_URL 中的密码保持一致；密码如果包含 URL 特殊字符，需要进行
URL 编码。

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

SRPM 与 RPM 的接口形式基本一致，只是前缀不同。

任务列表与详情：

~~~text
GET /api/v1/{srpm|rpm}/tasks
GET /api/v1/{srpm|rpm}/tasks/{id}
~~~

任务产物：

~~~text
GET /api/v1/{srpm|rpm}/tasks/{id}/artifacts/{artifact_id}/view
GET /api/v1/{srpm|rpm}/tasks/{id}/artifacts/{artifact_id}/download
~~~

主动同步 Jenkins：

~~~text
POST /api/v1/{srpm|rpm}/sync
~~~

Jenkins 事件接口：

~~~text
POST /api/v1/{srpm|rpm}/events
~~~

SRPM 另有摘要与 finding 接口：

~~~text
GET /api/v1/srpm/tasks/{id}/summary
GET /api/v1/srpm/tasks/{id}/findings
~~~

事件接口需要请求头：

~~~text
Authorization: Bearer <SCAN_SERVICE_INGEST_TOKEN>
~~~

SRPM 事件体示例：

~~~json
{
  "event": "started",
  "jenkins_job_full_name": "packages/curl",
  "jenkins_build_number": 15,
  "srpm_name": "curl-8.4.0-9.ocs23.src.rpm",
  "created_at": "2026-09-24T10:00:00+08:00"
}
~~~

RPM 事件体示例：

~~~json
{
  "event": "started",
  "jenkins_job_full_name": "rpm-docker-test",
  "jenkins_build_number": 1,
  "scan_key": "<RPM 的 sha256>",
  "rpm_name": "docker-24.0.9-8.lns23.loongarch64.rpm",
  "rpm_sha256": "<RPM 的 sha256>",
  "created_at": "2026-09-24T10:00:00+08:00"
}
~~~

completed 与 failed 事件在各自事件体上追加结束时间与退出码：SRPM 用
`csmock_exit_code`，RPM 用 `scanner_exit_code`。completed 只表示扫描与归档阶段
已正常结束，不直接代表 FINISHED；服务会重新读取 Jenkins Artifact 验证结果。

## 数据库

PostgreSQL 保存任务索引和结构化扫描结果，不保存完整原始扫描产物。

当前 SRPM 数据表为：

~~~text
srpm_scan_task
srpm_scan_artifact
srpm_scan_summary
srpm_scan_finding
~~~

RPM 数据表为：

~~~text
rpm_scan_task
rpm_scan_artifact
rpm_scan_component
rpm_scan_vulnerability
~~~

## 代码结构

SRPM 业务代码集中在：

~~~text
app/scanservice/modules/srpm/
~~~

RPM 业务代码集中在：

~~~text
app/scanservice/modules/rpm/
~~~

## 测试

测试应在容器中执行（在 scan-service 目录执行）：

~~~bash
docker compose run --rm --no-deps scan-results-portal python3 -m pytest -q
docker compose run --rm --no-deps scan-results-portal alembic current
~~~
