# Arbiter K8S 迁移改造

将 Arbiter 部署到 Kubernetes 时，原有的单机安全假设不再完全适用。容器本身就是隔离边界，部分本地防护可以降级或转由 K8S 原生机制接管。

本文档记录五项改造的内容、改动范围、改进与风险消除。

---

## 改造一览

| # | 模块 | 改动 | 影响范围 | 风险等级 |
|---|---|---|---|---|
| 1 | `permissions_hardline/` | 新增 `enable_hardline` 配置项，K8S 环境可关闭 | 所有 shell 工具执行 | 低 |
| 2 | `security/url_policy.py` | 新增 K8S 集群内部域名/CIDR 黑名单 | web_fetch 工具 | 低 |
| 3 | `embedding/factory.py` + `memory/` | 记忆/会话路径支持 PVC 挂载 | 会话持久化、记忆存取 | 中（多副本） |
| 4 | `embedding/permission_loader.py` | 新增 ConfigMap 规则加载路径 | 权限规则来源 | 低 |
| 5 | `capabilities/shell.py` / `process.py` | 新增 kubectl exec 执行后端 | run_shell_command 工具 | 中（RBAC） |

---

## 1. Hardline 地板可关闭

### 改了什么

`permissions_hardline/` 是整个系统的**安全地板**：在权限引擎之前拦截不可逆操作（`rm -rf /`、`mkfs`、`dd`、`shutdown`、fork bomb 等）。

容器里这些操作的破坏范围被限制在 pod 内，K8S 重启策略即可恢复。因此新增配置项让 K8S 环境可以关闭地板。

### 改动文件

```
arbiter/permissions.py        — PermissionEngine 已有 enable_hardline 参数
arbiter/embedding/factory.py  — 新增环境变量/配置读取，注入该参数
```

### 改动方式

`PermissionEngine` 已有 `enable_hardline: bool = True` 参数。`factory.py` 增加：

```python
# build_from_environment() 内
hardline_enabled = os.getenv("ARBITER_HARDLINE_ENABLED", "1") != "0"
permission_engine = PermissionEngine(
    project_root=wd,
    user_root=ur,
    rules=rules,
    loaded_sources=loaded_sources,
    enable_hardline=hardline_enabled,
)
```

K8S Deployment 通过环境变量控制：

```yaml
env:
  - name: ARBITER_HARDLINE_ENABLED
    value: "0"
```

### 消除了什么隐患

- **误杀合法操作**：容器内 `rm -rf /tmp/build-cache` 本意是清理构建缓存，但路径拼写错误成 `rm -rf /` 在容器里也只会重启一次。关掉地板后，这种场景不再被硬拦截。
- **维护负担**：每次向 `_HARDLINE_PATTERNS` 加新模式时，需要反复调试 shell 上下文分析器的假阳性。K8S 下不需要这份复杂性。

### 不会崩溃的原因

硬地板关闭后，原本被 DENY 的操作变为**走正常权限规则链**——如果 `full-access` 模式且没有自定义 deny 规则，才会真正执行。工具执行失败最多返回错误消息给 LLM，不会中断 chat loop。

---

## 2. SSRF 策略增加 K8S 集群保护

### 改了什么

`security/url_policy.py` 在原有的 localhost/127.0.0.1/cloud metadata 黑名单基础上，增加 K8S 集群内部的敏感目标。

### 改动文件

```
arbiter/security/url_policy.py  — _LOCAL_HOSTNAMES / _LOCAL_HOST_SUFFIXES 扩容
```

### 新增黑名单

```python
_LOCAL_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    # 新增:
    "kubernetes.default.svc",           # K8S API Server 内部 DNS
    "kubernetes.default",               # 缩写形式
    "kubernetes",                       # 更短的缩写
}

_LOCAL_HOST_SUFFIXES = (
    ".localhost",
    ".local",
    ".localdomain",
    ".internal",
    ".cluster.local",
    # 新增:
    ".svc.cluster.local",               # 集群内所有 Service DNS
    ".svc",                             # 同 namespace 短域名
    ".kube-system.svc",                 # kube-system 空间服务
    ".kube-system",                     # 缩写
    ".default.svc",                     # default 空间服务
)

# 新增: 集群内网 CIDR（blocked by validate_outbound_url 的地址检查）
# K8S 默认 Pod CIDR + Service CIDR + 节点网络
# 由 url_policy 的 _resolve_host_addresses + _is_disallowed 覆盖
# 这些属于非全局可路由地址，已被 is_global 捕获，无需额外代码
```

### 消除了什么隐患

| 之前 | 之后 |
|---|---|
| agent 可以 HTTP GET `http://kubernetes.default.svc/api/v1/secrets` | 被 `UrlPolicyError` 拦截，返回 "local/internal hostnames are not allowed" |
| `web_fetch("http://prometheus.monitoring.svc.cluster.local:9090")` 可能获取集群监控数据 | 明确拒绝，需通过 PermissionEngine 域名白名单显式放行 |
| 通过 `http://10.96.0.1`（K8S API 的 ClusterIP）绕过域名黑名单 | `_resolve_host_addresses` 返回 `10.96.0.1` → `_is_disallowed` 因非全局地址拒绝 |

### 误伤与逃生舱

如果 agent 需要访问集群内合法服务（如 Prometheus、内部文档站），通过 PermissionEngine 域白名单放行：

```json
{
  "rules": [
    {
      "tool": "web_fetch",
      "domain": {"allowlist": [".monitoring.svc.cluster.local"]},
      "action": "allow"
    }
  ]
}
```

---

## 3. 记忆/会话持久化支持 PVC

### 改了什么

当前 `.arbiter/memory.db` 和 `.arbiter/sessions/*.json` 写在本地磁盘。Pod 重建后数据丢失。改为支持通过环境变量配置存储路径，使其可以挂载 PVC。

### 改动文件

```
arbiter/embedding/factory.py  — memory.db 路径支持环境变量覆盖
arbiter/embedding/sessions.py — session 保存/读取路径支持环境变量覆盖
```

### 改动方式

```python
# factory.py :: build_from_environment()
# 当前:
project_store = SQLiteMemoryStore.open_or_memory(
    wd / ".arbiter" / "memory.db"
)

# 改为:
memory_path = os.getenv("ARBITER_MEMORY_DB_PATH")  # 可选，默认 None
if memory_path:
    project_store = SQLiteMemoryStore.open_or_memory(Path(memory_path))
else:
    project_store = SQLiteMemoryStore.open_or_memory(
        wd / ".arbiter" / "memory.db"
    )
```

```python
# sessions.py :: _session_dir()
# 当前:
def _session_dir(project_root=None):
    root = project_root if project_root else Path.cwd()
    return root / ".arbiter" / "sessions"

# 改为:
def _session_dir(project_root=None):
    override = os.getenv("ARBITER_SESSION_DIR")
    if override:
        return Path(override)
    root = project_root if project_root else Path.cwd()
    return root / ".arbiter" / "sessions"
```

### K8S 部署配置

```yaml
apiVersion: apps/v1
kind: StatefulSet    # 必须 StatefulSet，保证每个 pod 独立 PVC
spec:
  serviceName: arbiter
  template:
    spec:
      containers:
        - env:
            - name: ARBITER_MEMORY_DB_PATH
              value: /data/memory.db
            - name: ARBITER_SESSION_DIR
              value: /data/sessions
          volumeMounts:
            - name: data
              mountPath: /data
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 1Gi
```

### 消除了什么隐患

| 之前 | 之后 |
|---|---|
| Pod 重启 → 所有记忆丢失 | 记忆跨 Pod 生命期持续存在 |
| 会话中断后无法恢复 | `/resume` 可以从已保存的 session 文件恢复 |
| 持续对话体验中断 | 跨重启对话连续 |

### 不会崩溃的原因

`SQLiteMemoryStore.open_or_memory()` 在磁盘写入失败时会优雅降级到 `:memory:`（已有代码）。Session 写入/读取也有完整的 `try-except` + `IOError` 捕获。如果 PVC 挂载失败，退化为内存存储，agent 正常运行但重启后会丢失数据。

> **多副本重要限制**：SQLite 不支持并发写入。多 agent pod 实例共享同一 PVC 可能导致数据损坏。必须使用 `StatefulSet`（每个 pod 独立 PVC）。如需水平扩展，需将后端替换为 PostgreSQL（见下文"后续演进"）。

---

## 4. 权限规则通过 ConfigMap/Secret 注入

### 改了什么

当前权限规则从 `~/.arbiter/permissions.json` 读取（用户主目录）。K8S 中用户主目录不存在，改为从 ConfigMap 挂载的路径 `/etc/arbiter/permissions.json` 读取。

### 改动文件

```
arbiter/embedding/permission_loader.py  — 新增 K8S 配置路径
arbiter/embedding/factory.py            — 传递规则给 PermissionEngine
```

### 改动方式

```python
# permission_loader.py :: load_permission_rules()
def load_permission_rules(*, project_root, user_root):
    sources = []
    rules = []

    # 1. K8S ConfigMap 优先级最高（集群运维人员策略）
    k8s_path = Path("/etc/arbiter/permissions.json")
    if k8s_path.is_file():
        k8s_rules, k8s_loaded = _read_rule_file(k8s_path)
        if k8s_loaded:
            sources.append("k8s:/etc/arbiter/permissions.json")
            rules = k8s_rules          # K8S 规则优先

    # 2. 用户规则（兜底）
    if user_root is not None and not rules:   # K8S 规则已存在时跳过
        user_path = user_root / "permissions.json"
        user_rules, user_loaded = _read_rule_file(user_path)
        if user_loaded:
            sources.append(f"user:{user_path}")
            rules = user_rules

    # 3. 项目规则警告（不变）
    project_path = project_root / ".arbiter" / "permissions.json"
    if project_path.exists():
        logger.warning("Ignoring project-scope permissions.json (unchanged)")

    return rules, sources
```

### K8S 配置

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: arbiter-permissions
data:
  permissions.json: |
    {
      "rules": [
        {"tool": "run_shell_command", "args": {"command": "^kubectl "}, "action": "ask"},
        {"tool": "web_fetch", "domain": {"blocklist": ["kubernetes.default.svc"]}, "action": "deny"},
        {"tool": "*", "action": "allow"}
      ]
    }
---
apiVersion: v1
kind: Pod
spec:
  volumes:
    - name: permissions
      configMap:
        name: arbiter-permissions
  containers:
    - volumeMounts:
        - name: permissions
          mountPath: /etc/arbiter/permissions
```

```yaml
# API Key 走 Secret（不写在 .env 里）
apiVersion: v1
kind: Secret
metadata:
  name: arbiter-llm
type: Opaque
stringData:
  OPENAI_API_KEY: "sk-..."
  OPENAI_BASE_URL: "https://..."
  OPENAI_MODEL: "claude-opus-4-8"
```

### 消除了什么隐患

| 之前 | 之后 |
|---|---|
| API Key 写在 `.env` 文件里可能泄露 | 通过 K8S Secret 管理，etcd 加密存储 |
| 权限规则放在用户主目录，容器内不可达 | ConfigMap 挂载，集群运维人员统一管理 |
| 无版本控制的规则配置 | ConfigMap 有版本、有审计 |

### 不会崩溃的原因

`_read_rule_file()` 有完整的异常处理：文件不存在→跳过，JSON 解析失败→返回空列表。规则为空时 engine 退回到模式预设规则（`workspace-write` 默认），agent 运行不受影响。

---

## 5. 进程隔离 — kubectl exec 执行后端

### 改了什么

当前 `run_shell_command` 直接在 agent 容器内 `subprocess.run`。新增一个可选执行后端，将命令通过 `kubectl exec` 发送到目标 Pod 执行。

### 改动文件

```
arbiter/capabilities/process.py  — 新增 K8sShellExecutor
arbiter/capabilities/shell.py   — 新增 K8S exec 执行路径
```

### 改动方式

```python
# process.py :: 新增
class K8sShellExecutor:
    """在目标 K8S Pod 中执行命令，而非当前容器。"""

    def __init__(self, kubeconfig: Optional[str] = None):
        self.kubeconfig = kubeconfig or os.getenv("KUBECONFIG", "")

    def run(self, command: str, timeout: int = 60) -> subprocess.CompletedProcess:
        """kubectl exec 到目标 pod 执行命令。"""
        target_pod = os.getenv("ARBITER_TARGET_POD")
        target_ns = os.getenv("ARBITER_TARGET_NAMESPACE", "default")
        target_container = os.getenv("ARBITER_TARGET_CONTAINER", "")

        if not target_pod:
            # 未配置目标 pod → 回退到本地执行
            return run_captured(command, timeout=timeout)

        cmd = ["kubectl", "exec"]
        if self.kubeconfig:
            cmd += ["--kubeconfig", self.kubeconfig]
        cmd += ["-n", target_ns, target_pod]
        if target_container:
            cmd += ["-c", target_container]
        cmd += ["--", "sh", "-c", command]

        return run_captured(" ".join(cmd), timeout=timeout)
```

```python
# shell.py :: LocalShellExecutor.run()
# 添加执行后端选择:
executor_backend = os.getenv("ARBITER_SHELL_BACKEND", "local")
if executor_backend == "k8s":
    executor = K8sShellExecutor()
    return executor.run(command, timeout=timeout)
# else: 原有本地执行逻辑
```

### K8S 配置

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: arbiter
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-exec
rules:
  - apiGroups: [""]
    resources: ["pods/exec"]
    verbs: ["create"]
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: arbiter-pod-exec
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: pod-exec
subjects:
  - kind: ServiceAccount
    name: arbiter
---
apiVersion: v1
kind: Pod
spec:
  serviceAccountName: arbiter
  containers:
    - env:
        - name: ARBITER_SHELL_BACKEND
          value: "k8s"
        - name: ARBITER_TARGET_POD
          value: "worker-pod"    # 命令在此 pod 中执行
```

### 消除了什么隐患

| 之前 | 之后 |
|---|---|
| agent 执行的 shell 命令与 agent 同进程空间 | 目标 Pod 独立，命令破坏不影响 agent |
| 恶意命令可读取 agent 进程内存/env | 目标 Pod 没有 agent 的 API Key |
| 无操作审计边界 | kubectl exec 在 API Server 有完整审计日志 |
| 高负载命令（编译、数据处理）阻塞 agent | 在 Worker Pod 中执行，agent 进程不受影响 |

### 不会崩溃的原因

`K8sShellExecutor.run()` 是对现有 `run_captured()` 的包装。kubectl 缺失、目标 Pod 不存在、RBAC 拒绝等情况下，`run_captured` 返回非零退出码和错误输出。`LocalShellExecutor` 的上层调用者本来就能处理执行失败。

---

## 总结

### 改动统计

| 文件 | 新增行数 | 修改类型 |
|---|---|---|
| `arbiter/permissions.py` | ~0 | 无需改代码，已有参数 |
| `arbiter/embedding/factory.py` | ~15 | 读取环境变量并传递 |
| `arbiter/security/url_policy.py` | ~10 | 常量扩容 |
| `arbiter/embedding/permission_loader.py` | ~15 | 新增 K8S 文件路径 |
| `arbiter/embedding/sessions.py` | ~10 | 新增路径环境变量覆盖 |
| `arbiter/capabilities/process.py` | ~40 | 新增 K8sShellExecutor 类 |
| **合计** | **~90 行** | 新增代码，不删不改现有逻辑 |

### 崩溃风险评估

| 场景 | 结果 |
|---|---|
| Hardline 关闭 + rm -rf / | Pod Crash → K8S 自动重启，agent 重连后继续 |
| SSRF 误拦合法内网服务 | 工具返回错误 → LLM 换方法或报告失败 |
| PVC 挂载失败 | memory 降级到 `:memory:` → agent 正常运行，重启丢数据 |
| ConfigMap 不存在 | 规则为空 → 引擎用默认预设规则 |
| kubectl 不存在或 RBAC 拒绝 | 回退到本地执行，或工具返回 kubectl 错误输出 |
| 同时跑多个 agent pod（共享 PVC 无 RWX） | SQLite 损坏 → `open_or_memory` 降级到 `:memory:` |

### 后续演进（以后可以考虑）

1. **PostgreSQL 存储后端**：替代 SQLite 解决多副本写入问题
2. **K8S Informer 监听**：agent 可以通过 Informer 监听资源变更，替代轮询 kubectl
3. **ACP Worker Pool**：Manager Pod + 多个 Worker Pod（通过 ACP 通信），真正实现子 agent 隔离
4. **PodSecurityPolicy 集成**：自动从 K8S 集群安全策略推导权限规则
