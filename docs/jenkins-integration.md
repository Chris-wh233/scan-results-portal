# Jenkins 接入约定

源码包 Pipeline 使用 `POST /api/v1/srpm/events` 发送扫描事件。请求头为：

```text
Authorization: Bearer <SCAN_SERVICE_INGEST_TOKEN>
```

事件必须携带本次构建的完整 Job 名称和 Build Number。Label 使用完整的 SRPM 文件名，这样在扫描阶段失败或结果包缺失时，页面仍可以显示包名。

开始扫描：

```json
{
  "event": "started",
  "jenkins_job_full_name": "packages/curl",
  "jenkins_build_number": 15,
  "srpm_name": "curl-8.4.0-9.ocs23.src.rpm",
  "created_at": "2026-09-24T10:00:00+08:00"
}
```

扫描失败：

```json
{
  "event": "failed",
  "jenkins_job_full_name": "packages/curl",
  "jenkins_build_number": 15,
  "finished_at": "2026-09-24T10:02:00+08:00",
  "csmock_exit_code": 2
}
```

扫描正常结束并完成归档后发送 `completed` 事件。该事件不直接代表扫描成功，Scan Results Portal 会从这个 Job 的 Jenkins Build 读取产物，确认 `.tar.xz` 可以解压，并且包含以下预期文件：

```text
scan.ini
scan-results-summary.txt
scan-results.js
scan-results.err
scan-results.html
scan.log
```

验证成功时状态为 `FINISHED`；压缩包缺失、损坏、无法解压或缺少预期文件时状态为 `NOT_AVAILABLE`。csmock 阶段本身失败时状态为 `FAILED`。

推荐额外归档 `scan-manifest.json`，其 `scan_type` 应为 `srpm`，并包含 Job 名称、Build Number、SRPM 文件名、扫描时间和 csmock 退出码。

多个包 Job 可以共用同一套 Pipeline 模板。SRP 通过 `config/config.yaml` 的 `jenkins.jobs` 或 `jenkins.discovery.folders` 接入这些 Job；页面按扫描时间统一显示，不按 Job 分组。

新的 Pipeline 只使用 `/api/v1/srpm/events`，不需要先创建任务或解析任务 ID。
