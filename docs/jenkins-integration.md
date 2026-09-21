# Jenkins 接入约定

当前 Jenkins 接入逻辑以项目根目录的 `pipeline-script` 为准。Pipeline 在 csmock 阶段开始时注册任务，Scan Results Portal 将任务置为 `RUNNING` 并记录 `Created`；csmock 失败时回调 `scan-failed`；csmock 成功并完成归档后回调 `scan-complete`。

`scan-complete` 不直接代表扫描成功。Scan Results Portal 会从 Jenkins 读取构建产物，确认 `.tar.xz` 可以解压，并且包含以下预期文件：

```text
scan.ini
scan-results-summary.txt
scan-results.js
scan-results.err
scan-results.html
scan.log
```

验证成功时状态为 `FINISHED`；压缩包缺失、损坏、无法解压或缺少预期文件时状态为 `NOT_AVAILABLE`。csmock 阶段本身失败时状态为 `FAILED`。

Pipeline 使用 Jenkins Secret Text Credential：

```text
scan-service-ingest-token
```

其内容必须与 Scan Results Portal 的 `SCAN_SERVICE_INGEST_TOKEN` 相同。
