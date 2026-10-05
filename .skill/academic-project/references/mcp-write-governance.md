# MCP 写入收口协议参考 (mcp-write-governance)

> 本文件承载 SKILL.md §7.1 的实现细节；仅在项目声明 `mcp_governed_writes: on`
> 或需要部署/排错 academic-kanban MCP 时按需加载。规则本体以 SKILL.md 为准。

## 1. 部署形态

academic-kanban MCP 为 stdio、按项目挂载的 Python 服务器，**源码随技能发布并固化在
项目内 `.skill/academic-project/mcp/`**（`server.py` + `kanban_mcp/`），不需要另找仓库；
额外依赖仅 PyPI `mcp>=2.2,<3`。进程边界即权限边界：角色在启动参数中定死，
worker 会话的工具列表里根本不存在维护者工具。

```bash
<装有SDK的解释器> -E .skill/academic-project/mcp/server.py --root <项目根> --role maintainer
<装有SDK的解释器> -E .skill/academic-project/mcp/server.py --root <项目根> --role worker
<装有SDK的解释器> -E .skill/academic-project/mcp/server.py --doctor --root <项目根>  # 接线自检，不启服务
```

常驻共享形态（v0.4.0 起，适合多宿主复用同一进程）：

```bash
<装有SDK的解释器> -E .skill/academic-project/mcp/server.py --root <项目根> --role maintainer \
    --transport streamable-http --host 127.0.0.1 --port 8931
```

端点为 `http://127.0.0.1:8931/mcp`（streamable-http）。宿主 JSON 写法：

```json
{"academic-kanban": {"type": "streamable-http",
  "url": "http://127.0.0.1:8931/mcp"}}
```

一个 HTTP 进程仍只对应一个（项目, 角色）组合；需要双角色或双项目就多起进程（各占端口）。
服务对治理文件有写权限，**只允许回环地址**：非 127.0.0.1/localhost/::1 的 `--host` 直接
拒绝启动（退出码 2）。跨项目聚合端点尚未实现。

解释器必须是装有 mcp>=2.2,<3 的那个 Python，宿主配置 command 写它的绝对路径。PATH 上的裸 python 多半没有 SDK（启动即 ModuleNotFoundError: mcp）。--doctor 用与宿主完全相同的命令行运行，逐项输出 PASS/FAIL。服务器输出为 UTF-8 字节流（`-E` 会忽略 `PYTHONIOENCODING`，故编码在脚本内固定）：中文 Windows 的 GBK 控制台若显示乱码，先 `chcp 65001` 或重定向到文件查看，内容本身无损。

宿主在项目目录启动 stdio 进程时 `--root` 可缺省（取当前工作目录）。

`-E` 防止宿主注入的 `PYTHONPATH` 遮蔽服务器自身环境。一台机器只需准备一个装有 SDK 的 Python 环境；--root 缺省取进程当前目录，宿主在项目目录启动 stdio 进程时可省略 --root，并把 server.py 指向全局技能库的稳定副本，一条配置即服务本机所有项目（不确定时先跑 --doctor）。宿主配置示例：

- Hermes（`mcp_servers` YAML）：为 maintainer 与 worker profile 分别注册同名服务、不同 `--role`。
- 通用 JSON 配置（Qoder/Claude/Codex 类宿主）：

```json
{
  "mcpServers": {
    "academic-kanban": {
      "command": "C:/tools/pylibs/.venv/Scripts/python.exe",
      "args": ["-E", "<server.py 路径>", "--root", "<项目根>", "--role", "maintainer"]
    }
  }
}
```

未部署（或未装 mcp SDK）的机器：保持 `mcp_governed_writes: off`，技能全流程照常工作。
开发主仓（含测试与 CHANGELOG）地址见随包发布物说明或技能分发渠道；技能内固化副本（`.skill/academic-project/mcp/`）即发布物。

## 2. 工具面与权限映射

| 工具 | 角色 | 写入目标 | 强制内容 |
|---|---|---|---|
| `dashboard_update` | maintainer | `PROJECT_DASHBOARD.md` | §6.2 字数上限拒写；entry 未知字段拒写；需求行只许表尾追加且支持 update_matching 原地状态迁移；模板示例行（需求/陈列架/里程碑/待决策）首写即清除；本次写入行受沉淀保护；交付路径须真实存在；窗口超限自动沉淀底账；陈列架**按分类组独立**顶替、分类组缺失时首个条目自动建组；里程碑>10 沉淀进记忆层 milestones.md；待决策>3 拒增 |
| `worklog_append` | maintainer | `WORKLOG.md` | 标题≤40 字；目标/动作/证据必填 |
| `status_update` | maintainer | `progress/current_status.md` | 整档按模板重写 |
| `progress_append` | maintainer | `progress/progress_log.md` | 头插；>30 条自动季度归档 |
| `requirement_append` | maintainer | `requirements/requirements_log.md` | 每格≤200 字；满 100 条自动季度归档 |
| `decision_append` | maintainer | `decisions/decision_log.md` | 四要素必填，头插 |
| `contract_update` | maintainer | `AGENTS.md` | frontmatter 白名单键；replace 须唯一命中；`mcp_governed_writes` 拒绝 on→off |
| `human_edit` | maintainer | `WORKLOG.md`（追加豁免行） | 仅限人工编辑豁免：paths 必须都是真实存在的治理文件，须署名背书与理由；拒绝 AGENTS.md 与 WORKLOG.md 自身（防自洗白） |
| `dispatch_write` | maintainer | `for_manager/<task>/dispatch.md` | 拆解子任务派发单；title、goal、acceptance 为必填；限定工作者沙盒与输入依赖 |
| `review_write` | maintainer | `for_manager/<task>/<worker>/review.md` | 枚举决定；仅 COMPLETED 可判 ACCEPTED |
| `accept_deliverable` | maintainer | 正式目录迁移 | 源限 `for_user/`、`for_worker/`；目标禁入过程区/记忆根；拒绝覆盖 |
| `workflow_update` | maintainer | `workflow/<type>/*.md` | 仅本项目已激活类型可写（overview「已激活类型」声明 ∪ workflow/ 已有目录），未激活拒写并提示先经 `memory_update` 登记；append/rewrite |
| `milestone_append` | maintainer | `progress/milestones.md` | 表行追加；文件缺失自动建表 |
| `memory_update` | maintainer | `project_overview.md` / `file_registry.md` / `rules/file_layout.md` | 白名单整档重写，拒绝路径逃逸 |
| `handoff_write` | worker（maintainer 可收窄使用） | `for_manager/<task>/<worker>/handoff.md` | §2.3 字段全量；COMPLETED 须成果路径真实存在+自测证据；INCOMPLETE 拒收交付物与任何 `for_user` 路径；不覆盖旧版，自动版本号 |

不收口：业务交付物（代码/文稿/图表）、`file_registry.md`、`git/commit_log.md`、全部读取。

## 3. 台账格式

`<memory_root>/mcp_write_ledger.md`，MCP 独占追加，每行一条 JSON：

```json
{"t": 1790000000.0, "ts": "2026-09-25 11:30", "tool": "worklog_append",
 "role": "maintainer", "actor": "qoder-main", "targets": ["WORKLOG.md"],
 "sha": {"WORKLOG.md": "1a2b3c4d5e6f"}, "note": "实现核心", "sig": null}
```

- `targets` 为项目根相对 POSIX 路径；`sha` 为各目标**写入完成后内容的 sha256 前 12 位**，
  门禁据此识别"先合规写一笔、随后同窗口偷改同一文件"（哈希不匹配且无**登记于其后**的豁免行=违规）；
  旧版无 `sha` 的记录按路径级匹配（兼容）。`sig` 为签名档升级预留位，机会主义档位恒为 null。
- 治理文件豁免凭证：`WORKLOG.md` 中的
  「`未经 MCP 收口：<相对路径>；原因：<理由>`」行（降级场景，见 §7.1）。
  **豁免行只覆盖其登记时刻之前已发生的变更**（以 WORKLOG 自身 mtime 为界）；之后再改该文件
  必须重新登记或走 MCP——一次豁免不是永久白名单。

## 4. 门禁对账算法（`project_finish_check.py`，仅 on 项目）

1. 取治理文件集中 `mtime ≥ started_at−1s` 的文件（工作窗口内变更）；
2. 台账中存在 `targets` 覆盖该路径、`t ≥ started_at−1.5s` 且**当前文件内容哈希在该记录的
   `sha` 集合中** → 合规；
3. 否则当前内容哈希命中该路径的**任一历史台账版本** → 视内容未被改动
   （`cp -r`/checkout/同步盘只刷新 mtime 的整树复制不再误报）；
4. 否则 WORKLOG 含提及该路径的豁免行 → 合规（带警告）；
5. **基线宽限**：台账首条记录时间为基线；mtime 早于基线、或项目尚无任何台账记录时，
   只出「收口启用前/基线前产物」警告不判违规——收口自第一笔 MCP 写入起硬执法；
6. 其余情形报「MCP 收口违规」，退出码非零。

`--started-at` 接受 Unix 秒或本地时间字符串 `YYYY-MM-DD HH:MM[:SS]`。
`preflight` 只解析开关并报告模式（on 且无台账为提示级警告），永不因 MCP 缺席而失败。
对账不区分变更作者是 AI 还是用户本人：在线时由维护者调 `human_edit` 登记豁免——
`human_edit` 自身写 WORKLOG 并记入台账，天然可被对账覆盖。MCP 降级时按 §7.1
直写并**手书** WORKLOG 豁免行同样成立：WORKLOG 自身也是治理文件，其顺序无法自证，
门禁按「含豁免行即自证」的**警告级**接受 WORKLOG 的窗口内变更，不判违规，并提示人工抽查。

## 5. 威胁模型与边界

对账防的是模型不守规矩的惯性（忘走 MCP / 抄近路直写），不防刻意伪造台账。
三项已锁的边界：受管工具拒绝把 `mcp_governed_writes` 从 on 改回 off（含 replace 路径；
脱锁只能由用户直接编辑契约）；伪报 `--started-at` 不在防护范围（时间戳由调用方提供）；
台账内容哈希只防"合规写入后再偷改"的顺手续写，刻意伪造者同样能算哈希——这仍属
机会主义档，重要项目应由人工抽查台账与 WORKLOG 豁免行。
需要更强保证时按 `sig` 钩子升级 HMAC 签名档，但须先解决密钥与发布脱敏（§11）、
凭据隔离（§7）的冲突。HTTP 形态（v0.4.0 起）为单（项目×角色）常驻服务，跨项目聚合在 roadmap。

## 6. 已知限制清单（按严重度，模拟用户流程审计得出）

1. 豁免行只覆盖登记前已发生的变更（v2.3.1 起，以 WORKLOG mtime 为界）；此后再改须重新登记。WORKLOG 自身降级直写按「含豁免行即自证」警告级放行——代价是手书一条豁免行同时能遮蔽 WORKLOG 自身内容被改（顺序本就无法自证），人工抽查兜底。
2. 台账内容哈希能抓"合规写入后续偷改"，防不了会算哈希、会伪造台账行的刻意伪造（机会主义档定位）；内容与任一历史台账版本逐字相同视为未变更。
3. `--started-at` 与 `--no-project-change` 由调用方提供，构成自证逃逸门。
4. worker 无 MCP 时交接件直写不判对账违规（§7.1 收口范围已言明），纪律靠 §2.3+review 兜底；`accept_deliverable` 迁移后交接/复核件里的旧路径成死链，门禁不校验历史文件内容。
5. 业务工具拒写返回 `{"ok": false}` 而 MCP 层 `isError=false`——**调用方必须解析结果里的 `ok` 字段**，不能只看协议层成功。
6. 库层角色闸（v2.3.1 起维护者工具在业务层二次校验启动角色）与宿主挂载各防一半：防呆不防恶意。
