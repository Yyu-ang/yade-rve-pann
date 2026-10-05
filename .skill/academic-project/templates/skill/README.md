# 项目级 WikiSkill 模板

| 模板文件 | 用途 |
|:--|:--|
| `SKILL.template.md` | 项目级自定义技能主文件骨架 |
| `eval_tasks.md` | 门禁检验任务注册表 |
| `state.json` | 技能演进状态追踪器 (`gate_status`: `gate_pending` / `passing` / `rejected`) |
| `pattern.template.md` | Wiki Pattern 模式模板（源自真实追踪记录） |
| `trace.template.md` | 原始执行与交互追踪模板 |
| `wiki_index.md` | WikiSkill 目录索引 |
| `wiki_logs.md` | WikiSkill 变更日志 |
| `skill_impact.md` | 技能部署后的影响评估记录 |

技能演进闭环路径：`原始追踪 (Raw trace) → Wiki 模式 (Wiki Pattern) → 候选技能 (Candidate Skill) → 可执行门禁验证 (Executable gate) → 正式项目技能 (Formal skill)`。
详细规范参见 `SKILL.md`。
