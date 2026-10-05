"""academic-kanban MCP server entry: stdio, per-project, role-mounted tools.

Launch (the process boundary IS the permission boundary):

    python -E <kanban-mcp>/server.py --root <project-root> --role maintainer
    python -E <kanban-mcp>/server.py --root <project-root> --role worker

A worker session never sees maintainer tools; a maintainer may call the worker
tool (narrowing is allowed, widening is not). Every successful write appends one
JSON record to <memory_root>/mcp_write_ledger.md for the finish-gate to
reconcile against governance-file mtimes.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Literal

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError):
        pass

try:
    from mcp.server import MCPServer
except ImportError:  # keep --doctor usable on interpreters WITHOUT the SDK — that's its job
    MCPServer = None

if __package__ in (None, ""):  # direct `python server.py` launch
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kanban_mcp import __version__, business  # noqa: E402
from kanban_mcp.model import KanbanError, Project  # noqa: E402

DESCRIPTION = (
    "academic-project 治理文件收口写入服务：治理/状态文件（看板、WORKLOG、契约、记忆根、"
    "交接/复核件）只能经本服务的角色工具组写入；条数窗口自动沉淀、字数与字段超限拒写。"
)

INSTRUCTIONS_MAINTAINER = (
    "当前会话以 maintainer 角色挂载：可调用维护者工具组与 worker 工具（收窄）。"
    "业务交付物（代码/文稿/图表）不在收口范围，仍由你直接写。若本服务不可用，按 AGENTS.md "
    "降级条款直写并在 WORKLOG 记「未经 MCP 收口：<路径>；原因：<理由>」。"
)
INSTRUCTIONS_WORKER = (
    "当前会话以 worker 角色挂载：仅可调用 handoff_write。全局看板、契约、日志与记忆对你只读；"
    "交付物只写获派的 for_worker/<task-id>/<agent-id>/ 目录。任务结束必须落盘交接件。"
)


def build_server(project_factory, role: str) -> MCPServer:
    server = MCPServer(
        name="academic-kanban",
        title="academic-kanban",
        version=__version__,
        description=DESCRIPTION,
        instructions=INSTRUCTIONS_MAINTAINER if role == "maintainer" else INSTRUCTIONS_WORKER,
    )

    def call(fn, actor: str, **kwargs) -> dict:
        p = project_factory()
        try:
            return fn(p, actor or "", **kwargs)
        except (ValueError, KeyError, FileNotFoundError, OSError) as exc:
            return {"ok": False, "error": str(exc)}

    # ---------------- maintainer tool group ----------------
    def dashboard_update(section: Literal["snapshot", "requirement", "deliverable",
                                          "milestone", "pending"],
                         entry_json: str, actor: str = "") -> dict:
        """更新 PROJECT_DASHBOARD.md。section: snapshot|requirement|deliverable|milestone|pending。
        entry_json 按小节：snapshot{stage≤20字,status:green|yellow|red,direction?}；
        requirement{demand≤50字,status:delivered|in_progress|blocked,path,value≤80字,date?,
        update_matching?{demand_contains}：命中行原地更新（推进中→已交付），否则追加}；
        deliverable{category:docs|figures|code|bench|data,name,path,note≤30字}；
        milestone{event≤40字,date?}；pending{action:add|replace,text≤60字|items[]}。
        窗口超限自动沉淀底账，字数超限拒写，entry 未知字段拒写。"""
        return call(business.dashboard_update, actor, section=section, entry_json=entry_json)

    def worklog_append(title: str, goal: str, actions: str, evidence: str,
                       blockers: str = "无", next_step: str = "",
                       related: str = "", actor: str = "") -> dict:
        """向 WORKLOG.md 追加一条工程记录（标题≤40字，目标/动作/证据必填）。"""
        return call(business.worklog_append, actor, title=title, goal=goal, actions=actions,
                    evidence=evidence, blockers=blockers, next_step=next_step, related=related)

    def status_update(stage: str, in_progress: list[str], todos: list[str],
                      blockers: list[str], next_step: str, actor: str = "") -> dict:
        """重写 <memory_root>/progress/current_status.md 状态快照。"""
        return call(business.status_update, actor, stage=stage, in_progress=in_progress,
                    todos=todos, blockers=blockers, next_step=next_step)

    def progress_append(title: str, task: str, done: list[str], changed: list[str],
                        next_step: str, actor: str = "") -> dict:
        """向 progress_log.md 头插一条进展（最新在前；超过30条自动沉淀季度归档）。"""
        return call(business.progress_append, actor, title=title, task=task, done=done,
                    changed=changed, next_step=next_step)

    def requirement_append(demand: str, completion: str, date: str = "",
                           actor: str = "") -> dict:
        """向 requirements_log.md 底账追加一行（每格≤200字；满100条自动归档）。"""
        return call(business.requirement_append, actor, demand=demand, completion=completion, date=date)

    def decision_append(title: str, context: str, decision: str, alternatives: str,
                        evidence_level: str, date: str = "", actor: str = "") -> dict:
        """向 decision_log.md 头插一条决策（背景/决定/备选/证据等级必填）。"""
        return call(business.decision_append, actor, title=title, context=context,
                    decision=decision, alternatives=alternatives, evidence_level=evidence_level, date=date)

    def human_edit(paths: list[str], reason: str, actor: str = "") -> dict:
        """为确认出自人工编辑的治理文件登记对账豁免（向 WORKLOG 追加豁免行）。
        仅限维护者核验「是用户本人改的」之后使用；不得用于洗白 AI 自己的绕道直写。"""
        return call(business.human_edit, actor, paths=paths, reason=reason)

    def contract_update(action: Literal["set_frontmatter", "replace"], key: str = "", value: str = "", old: str = "",
                        new: str = "", actor: str = "") -> dict:
        """维护 AGENTS.md。action=set_frontmatter（限 mcp_governed_writes|memory_root|legacy_memory_root）
        或 replace（old 必须全文唯一命中）。"""
        return call(business.contract_update, actor, action=action, key=key, value=value,
                    old=old, new=new)

    def dispatch_write(task_id: str, title: str, goal: str,
                       assigned_role: str = "Worker", assignee: str = "pending",
                       parent_goal: str = "", inputs: list[str] | None = None,
                       write_scope: list[str] | None = None,
                       acceptance: list[str] | None = None,
                       depends_on: list[str] | None = None,
                       priority: Literal["HIGH", "MEDIUM", "LOW"] = "HIGH",
                       status: Literal["DISPATCHED", "IN_PROGRESS", "ACCEPTED", "REWORK", "CANCELLED"] = "DISPATCHED",
                       notes: str = "", actor: str = "") -> dict:
        """写 for_manager/<task>/dispatch.md 子任务派发单。
        maintainer 专用；title、goal、acceptance 为必填项。"""
        return call(business.dispatch_write, actor, task_id=task_id, title=title,
                    goal=goal, assigned_role=assigned_role, assignee=assignee,
                    parent_goal=parent_goal, inputs=inputs or [], write_scope=write_scope or [],
                    acceptance=acceptance or [], depends_on=depends_on or [],
                    priority=priority, status=status, notes=notes)

    def review_write(task_id: str, worker_id: str, manager_id: str,
                     decision: Literal["ACCEPTED", "REWORK_REQUIRED", "HANDOFF_ACCEPTED", "CANCELLED"],
                     worker_status: Literal["COMPLETED", "INCOMPLETE_HANDOFF"],
                     standards: list[str], artifact_check: str,
                     selftest_review: str, next_step: str = "无", keep_wip: str = "无",
                     cleanup: str = "无", final_path: str = "待最终交付",
                     actor: str = "") -> dict:
        """写 for_manager/<task>/<worker>/review.md。decision: ACCEPTED|REWORK_REQUIRED|HANDOFF_ACCEPTED|CANCELLED；
        仅 COMPLETED 可判 ACCEPTED；standards 逐条必填。"""
        return call(business.review_write, actor, task_id=task_id, worker_id=worker_id,
                    manager_id=manager_id, decision=decision, worker_status=worker_status,
                    standards=standards, artifact_check=artifact_check,
                    selftest_review=selftest_review, next_step=next_step, keep_wip=keep_wip,
                    cleanup=cleanup, final_path=final_path)

    def accept_deliverable(src: str, dst: str, note: str = "", actor: str = "") -> dict:
        """把已验收成果从 for_user/ 或 for_worker/ 移入正式目录（拒绝覆盖、拒绝落入过程区/记忆根）。"""
        return call(business.accept_deliverable, actor, src=src, dst=dst, note=note)

    def workflow_update(project_type: str, filename: str,
                        action: Literal["append", "rewrite"], title: str,
                        content: str, actor: str = "") -> dict:
        """更新 <memory_root>/workflow/<type>/<filename>。filename 须含 .md 后缀且为纯文件名；
        action=append|rewrite；仅本项目已激活类型可写（见 overview 已激活类型行）。"""
        return call(business.workflow_update, actor, project_type=project_type,
                    filename=filename, action=action, title=title, content=content)

    def milestone_append(milestone: str, status: str = "✅ 达成", git_tag: str = "-",
                         date: str = "", note: str = "-", actor: str = "") -> dict:
        """向 progress/milestones.md 追加一行里程碑。"""
        return call(business.milestone_append, actor, milestone=milestone, status=status,
                    git_tag=git_tag, date=date, note=note)

    def memory_update(relpath: Literal["project_overview.md", "file_registry.md",
                                       "rules/file_layout.md"],
                      content: str, actor: str = "") -> dict:
        """整档重写白名单记忆文件（project_overview.md|file_registry.md|rules/file_layout.md）。"""
        return call(business.memory_update, actor, relpath=relpath, content=content)

    # ---------------- worker tool group (maintainer may also use: narrowing) ----------------
    def handoff_write(task_id: str, worker_id: str,
                      status: Literal["COMPLETED", "INCOMPLETE_HANDOFF"], goal: str,
                      acceptance: list[str], done: list[str], deliverables: list[str],
                      selftest_cmd: str, selftest_result: str, unfinished: list[str],
                      blocker: str, next_steps: str, wip_path: str = "",
                      verify_items: list[str] | None = None, actor: str = "") -> dict:
        """写 for_manager/<task>/<worker>/handoff.md（不可覆盖旧版，自动版本号）。
        COMPLETED：deliverables 非空且路径真实存在、必须来自测证据；
        INCOMPLETE_HANDOFF：deliverables 必须为空（只交接不交付），拒绝 for_user 路径。"""
        return call(business.handoff_write, actor, task_id=task_id, worker_id=worker_id,
                    status=status, goal=goal, acceptance=acceptance, done=done,
                    deliverables=deliverables, selftest_cmd=selftest_cmd,
                    selftest_result=selftest_result, unfinished=unfinished, blocker=blocker,
                    next_steps=next_steps, wip_path=wip_path,
                    verify_items=verify_items or [])

    maintainer_tools = [dashboard_update, worklog_append, status_update, progress_append,
                        requirement_append, decision_append, milestone_append, memory_update,
                        contract_update, human_edit, dispatch_write, review_write,
                        accept_deliverable, workflow_update]
    worker_tools = [handoff_write]

    fns = maintainer_tools + worker_tools if role == "maintainer" else worker_tools
    for fn in fns:
        server.tool()(fn)
    return server


def run_doctor(root: str) -> int:
    """接线自检：用宿主配置里的同一解释器/命令行运行，逐项 PASS/FAIL，退出码即结论。"""
    print(f"academic-kanban v{__version__} doctor  (interpreter: {sys.executable})")
    failures = 0
    py_ok = sys.version_info >= (3, 10)
    print(f"[{'OK  ' if py_ok else 'FAIL'}] Python {sys.version.split()[0]}（需 ≥3.10）")
    failures += 0 if py_ok else 1
    try:
        import importlib.metadata as _im
        print(f"[OK  ] mcp SDK {_im.version('mcp')}（要求 >=2.2,<3；升级：pip install -U 'mcp>=2.2,<3'）")
    except Exception:
        print("[FAIL] 当前解释器没有 mcp SDK → 用它执行 pip install 'mcp>=2.2,<3'，"
              "并把宿主配置的 command 换成这个解释器的绝对路径")
        failures += 1
    try:
        p = Project(root=Path(root), role="maintainer")
        print(f"[OK  ] 项目根有效：{p.root}")
        print(f"[OK  ] 记忆根 {p.memory_root.name}；mcp_governed_writes={p.governance()}"
              + ("（off：门禁不做对账，收口前请在 AGENTS.md 置 on）" if p.governance() == "off" else ""))
        ledger = p.memory_root / "mcp_write_ledger.md"
        print(f"[OK  ] 台账 {ledger.name} " + ("已存在" if ledger.exists() else "尚未生成（首次成功写入后出现，正常）"))
        print("[OK  ] 角色挂载预览：maintainer → 15 工具；worker → 1 工具（handoff_write）")
    except (KanbanError, Exception) as exc:  # noqa: B014
        print(f"[FAIL] 项目检查：{exc}")
        failures += 1
    print("doctor 结果：" + ("PASS — 宿主配置即用上述解释器绝对路径注册" if not failures
                          else f"FAIL（{failures} 项待修）"))
    return 1 if failures else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="academic-kanban MCP (stdio)")
    parser.add_argument("--root", help="项目根目录；缺省取当前工作目录（宿主一般在项目目录启动 stdio 服务器）")
    parser.add_argument("--role", choices=("maintainer", "worker"))
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--doctor", action="store_true",
                        help="接线自检：用宿主配置里的同一解释器运行，检查 Python/mcp SDK/项目根/开关/台账；不启动服务")
    parser.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio",
                        help="stdio=宿主按会话拉起（默认）；streamable-http=本机常驻服务")
    parser.add_argument("--host", default="127.0.0.1",
                        help="HTTP 监听地址（仅 --transport streamable-http 生效；默认只绑回环，禁止公网暴露）")
    parser.add_argument("--port", type=int, default=8931, help="HTTP 端口（默认 8931）")
    args = parser.parse_args(argv)
    if args.version:
        print(f"academic-kanban v{__version__}")
        return 0
    if args.doctor:
        return run_doctor(args.root or str(Path.cwd()))
    if not args.role:
        parser.error("--role 为必需参数（或使用 --version / --doctor）")
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print(f"拒绝启动：--host {args.host} 会暴露到公网/局域网。本服务对治理文件有写权限，"
              "只允许回环地址；确需跨机部署请另行评审安全方案，而不是解除本限制。", file=sys.stderr)
        return 2
    if MCPServer is None:
        print(f"[FAIL] 当前解释器 {sys.executable} 没有 mcp SDK。修复：pip install 'mcp>=2.2,<3'，"
              "或改用装有 SDK 的解释器；排查请运行本文件的 --doctor 模式", file=sys.stderr)
        return 2
    root = args.root or str(Path.cwd())
    try:
        first = Project(root=Path(root), role=args.role)
    except KanbanError as exc:
        print(f"启动失败：{exc}", file=sys.stderr)
        return 2

    def factory():
        return Project(root=first.root, role=first.role)  # re-validate memory root per call

    server = build_server(factory, args.role)
    if args.transport == "streamable-http":
        url = f"http://{args.host}:{args.port}/mcp"
        print(f"academic-kanban [{args.role}] root={first.root} 监听 {url}", flush=True)
        server.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        server.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
