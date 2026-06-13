2026年5⽉版

# DeepAgents 指南

# Harness ⼯程 · SDK 内核 · CLI · 评估体系与沙箱集成

从 Harness ⼯程视⻆拆解 LangChain 开源项⽬ deepagents：涵盖全局架构与create\_deep\_agent、后端协议与七种后端实现、中间件栈（⽂件系统、⼦代理、上下⽂压缩、记忆与技能等）、CLI 与沙箱⼯⼚、内置与外部评估基准、Harbor / TerminalBench 2.0 ACP 与合作伙伴沙箱，以及 CI/CD 质量规范与示例项⽬；共 31 篇，逐模块对照源码阅读

⽂档版本: v1.0.0

发布时间: 2026-05-26

语⾔: 简体中⽂

「⼩番薯⽣活集」官⽅整理，认准本店，持续更新！

本产品包含的产品和⼯具信息 功能描述可能随时变化 请以各产品⼯具官⽅⽂档为准。

## ⽬录

## Table of Contents

DeepAgents 指南

第 1 章：项⽬概览与仓库结构 8

第 2 章：核⼼设计哲学与架构总览 14

第 3 章：⼊⼝函数 create\_deep\_agent() 21

第 4 章：后端协议 BackendProtocol 与 SandboxBackendProtocol 29

第 5 章：后端实现详解 36

第 6 章：中间件体系总论 45

第 7 章：FilesystemMiddleware ⽂件系统中间件 62

第 8 章：SubAgentMiddleware ⼦代理中间件 68

第 9 章：AsyncSubAgentMiddleware 异步⼦代理 75

第 10 章：SummarizationMiddleware 上下⽂压缩 81

第 11 章：MemoryMiddleware 与 SkillsMiddleware 86

第 12 章：PatchToolCallsMiddleware 悬空⼯具调⽤修复 93

第 13 章：模型解析与 Provider ⽀持 97

第 14 章：CLI 架构与⼊⼝ 103

第 15 章：CLI 沙箱与集成⼯⼚ 109

第 16 章：CLI 技能系统与 Slash 命令 114

第 17 章：评估体系架构总览 120

第 18 章：评估报告与指标系统 129

第 19 章：内置评估⽤例详解 136

第 20 章：外部基准测试集成 144

第 21 章：LLM-as-Judge 评估模式 150

第 22 章：Harbor 框架集成 154

第 23 章：Terminal Bench 2.0 评估 159

第 24 章：Harbor 分析与统计⼯具 167

第 25 章：Agent Client Protocol（ACP）集成 174

第 26 章：REPL 中间件 184

第 27 章：合作伙伴沙箱集成 194

第 28 章：CI/CD 与发布流程 198

第 29 章：代码规范与质量保障 204

第 30 章：编写评估⽤例指南 219

第 31 章：示例项⽬解析 223

## DeepAgents 指南

从 Harness ⼯程⻆度系统拆解 deepagents 项⽬

本书以 LangChain 开源项⽬ Deep Agents 为分析对象，从框架设计、SDK 内核、CLI ⼯程、评估体系、沙箱集成到⼯程实践，逐模块深⼊源码，帮助读者理解⼀个⽣产级 Agent Harness 的完整⼯程全貌。

全部内容为中⽂，共 31 篇，按知识点独⽴成⽂。

## 版本与参考基准

本书以 langchain-ai/deepagents 0.6.x 为参考版本编写：正⽂中的 monorepo 路径、中间件栈与 API 形态均按该版本线整理（含 libs/cli libs/acp libs/evals 与libs/partners \* 等同期布局）

## 目录

第⼀部分：全局架构

<table><tr><td>编号</td><td>标题</td><td>简介</td></tr><tr><td>01</td><td>项目概览与仓库结构</td><td>Monorepo 布局、工具链、配置体系</td></tr><tr><td>02</td><td>核心设计哲学与架构总览</td><td>Harness 模式、三层架构、组合式 API</td></tr></table>

## 第⼆部分：SDK核⼼

<table><tr><td>编号</td><td>标题</td><td>简介</td></tr><tr><td>03</td><td>入口函数 create_deep_agent</td><td>主装配函数签名、中间件栈组装、系统提示词</td></tr><tr><td>04</td><td>后端协议 BackendProtocol</td><td>协议定义、数据类型、文件格式演进</td></tr><tr><td>05</td><td>后端实现详解</td><td>State/Filesystem/Composite/Sandbox 等 7 种后端</td></tr><tr><td>06</td><td>中间件体系总论</td><td>AgentMiddleware 机制、中间件 vs 工具</td></tr><tr><td>07</td><td>FilesystemMiddleware</td><td>文件工具集、大文件策略、结果驱逐</td></tr><tr><td>08</td><td>SubAgentMiddleware</td><td>三种子代理规格、task 工具、继承规则</td></tr><tr><td>09</td><td>AsyncSubAgentMiddleware</td><td>远程异步子代理、生命周期工具</td></tr><tr><td>10</td><td>SummarizationMiddleware</td><td>自动/手动对话压缩、历史卸载</td></tr><tr><td>11</td><td>MemoryMiddleware 与 SkillsMiddleware</td><td>记忆加载、技能渐进披露</td></tr><tr><td>12</td><td>PatchToolCallsMiddleware</td><td>悬空工具调用修复</td></tr><tr><td>13</td><td>模型解析与 Provider 支持</td><td>resolve_model、多 Provider 适配</td></tr></table>

第三部分：CLI ⼯程

<table><tr><td>编号</td><td>标题</td><td>简介</td></tr><tr><td>14</td><td>CLI 架构与入口</td><td>包结构、Settings 配置、调用链</td></tr><tr><td>15</td><td>CLI 沙箱与集成工厂</td><td>沙箱工厂、运行时模型切换</td></tr><tr><td>16</td><td>CLI 技能系统与 Slash 命令</td><td>内置技能、命令注册、Widget</td></tr></table>

## 第四部分：评估体系

<table><tr><td>编号</td><td>标题</td><td>简介</td></tr><tr><td>17</td><td>评估体系架构总览</td><td>两层断言模型、核心类型、run_agent</td></tr><tr><td>18</td><td>评估报告与指标系统</td><td>指标体系、Radar图、CI聚合</td></tr><tr><td>19</td><td>内置评估用例详解</td><td>12个测试文件逐一解析</td></tr><tr><td>20</td><td>外部基准测试集成</td><td>FRAMES / Nexus / BFCL v3 / tau2-bench</td></tr><tr><td>21</td><td>LLM-as-Judge 评估模式</td><td>LLM裁判、语义评分 vs 子串匹配</td></tr></table>

第五部分：Harbor 与 Terminal Bench

<table><tr><td>编号</td><td>标题</td><td>简介</td></tr><tr><td>22</td><td>Harbor 框架集成</td><td>DeepAgentsWrapper、HarborSandbox</td></tr><tr><td>23</td><td>Terminal Bench 2.0 评估</td><td>90+ 任务基准、LangSmith 工作流</td></tr><tr><td>24</td><td>Harbor 分析与统计工具</td><td>失败分类、统计工具、LangSmith 脚本</td></tr></table>

第六部分：扩展与集成

<table><tr><td>编号</td><td>标题</td><td>简介</td></tr><tr><td>25</td><td>ACP Agent Client Protocol</td><td>ACP 服务端集成</td></tr><tr><td>26</td><td>REPL 中间件</td><td>Interpreter、ReplMiddleware</td></tr><tr><td>27</td><td>合作伙伴沙箱集成</td><td>Daytona / Modal / QuickJS / Runloop</td></tr></table>

## 第七部分：⼯程实践

<table><tr><td>编号</td><td>标题</td><td>简介</td></tr><tr><td>28</td><td>CI/CD 与发布流程</td><td>GitHub Actions、release-please</td></tr><tr><td>29</td><td>代码规范与质量保障</td><td>Conventional Commits、ruff/ty、安全</td></tr><tr><td>30</td><td>编写评估用例指南</td><td>五步流程、分类管理、漂移测试</td></tr></table>

第⼋部分：示例与实战

<table><tr><td>编号</td><td>标题</td><td>简介</td></tr><tr><td>31</td><td>示例项目解析</td><td>6个示例项目的架构模式</td></tr></table>

## 架构概览

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/02b3528e-b243-4cb0-b036-faa38c49ff02/7ac89ebbd9bba5e617cf648f277fd95332e8d54fcf9ba504a89995b712975fae.jpg)

## 分析对象

项⽬: langchain-ai/deepagents

. 定位: 基于 LangGraph 的 batteries-included Agent Harness

核⼼能⼒: 规划 (write\_todos)、⽂件系统操作、Shell 执⾏、⼦代理分发、上下⽂压缩、记忆/技能注⼊

## 第 1 章：项目概览与仓库结构

## 主要参考源码路径

仓库根⽬录： README.md

开发指南： AGENTS.md

多包编排： libs/Makefile

各⼦包： libs/*/pyproject.toml 、 libs/*/uv.lock

## 1. 本书视角：何谓「Harness 工程」

Deep Agents 在官⽅定位中是 batteries-included agent harness（开箱即⽤的智能体「⻢具」/harness）：不强迫使⽤者从零拼装提示词、⼯具与上下⽂管理，⽽是通过 可组合的默认能⼒ 快速得到可运⾏的智能体，再按需裁剪与扩展。

从⼯程上看，本仓库是⼀个 Python 单体仓库（monorepo），内含多个 独⽴版本 独⽴锁⽂件 的发布包；根⽬录不设统⼀的 uv workspace，也没有根级 setup.py ，每个包⾃成⼀体，由 make与 libs/Makefile 聚合常⻅开发任务。

## 2. 目录树总览

下列树形结构概括仓库顶层布局（注释为⻆⾊说明；与 AGENTS.md 中的 monorepo 描述⼀致并略作扩展）：

```txt
deepagents/
├── .github/    # CI/CD、脚本、Issue/PR 模板、文档用图片等
├── examples/    # 示例工程（各自 pyproject + uv.lock）
├── libs/
│   | ─ deepagents/    # 核心 SDK
│   | ─ cli/    # 终端 CLI / TUI
```

```txt
| |— acp/    # Agent Client Protocol 集成
| |— evals/    # 评测套件与 Harbor 等集成
| |— repl/    # REPL 中间件 (langchain-repl)
| |— partners/    # 合作方沙箱/运行时集成（多子包）
|— AGENTS.md    # 贡献者与 AI 辅助开发指南
|— README.md    # 项目对外说明与快速开始
|— release-please-config.json  # 发布与版本自动化配置
```

## 3. Monorepo 各包职责

## 3.1 libs/deepagents/ — 核⼼ SDK

⻆⾊：Deep Agents 的 主库，对外通常通过 PyPI 包名 deepagents 安装。

能⼒概览：提供⼯⼚函数 create\_deep\_agent 、多层 middleware、BackendProtocol 及多种存储/执⾏后端实现等。

与全书关系：第 2 章架构与「Harness」模式均以此包为中⼼展开。

## 3.2 libs/cli/ — CLI / TUI

⻆⾊：基于 Textual 的 终端交互界⾯，提供类似「编码助⼿」的终端体验。

⼊⼝：可执⾏名通常为 deepagents deepagents-cli （以各包 pyproject.toml 中\[project.scripts] 为准）。

设计要点（⻅ AGENTS.md ）：启动路径需 延迟导⼊ 重型依赖（如 LangChain/LangGraph），避免 -v 等轻量命令也背负秒级启动成本；CLI 对 SDK 版本常有 精确 pin，与 CI 校验联动。

## 3.3 libs/acp/ — Agent Client Protocol

⻆⾊：Agent Client Protocol（ACP） 与 Deep Agents 的集成包（PyPI 名如 deepagents-acp ），⽤于与遵循 ACP 的客户端/⽣态对接。

注意：仓库根⽬录 AGENTS.md 中曾⽤「Agent Context Protocol」表述，与libs/acp/pyproject.toml 中的 Agent Client Protocol 以发布元数据为准。

## 3.4 libs/evals/ — 评测

⻆⾊：评测套件，含与 Harbor 等基础设施的集成及基准场景。

维护提示： AGENTS.md 说明 evals 下部分数据⽬录为上游 vendored，需保持字节级⼀致，且受 .pre-commit-config.yaml 中针对性排除项保护。

## 3.5 libs/repl/ — REPL 中间件

⻆⾊：包名 langchain-repl ，描述为⾯向 deepagents 的 LangChain REPL；依赖核⼼deepagents ，⽤于 交互式 REPL 场景 的中间件能⼒（与 SDK、CLI 形成不同⼊⼝形态）。

## 3.6 libs/partners/ — 合作⽅沙箱集成

⻆⾊：合作伙伴运⾏时/沙箱 的独⽴集成包，按⼦⽬录拆分，例如：

. daytona/

. modal/

. quickjs/

. runloop/

各⼦包⾃有 Makefile 、 pyproject.toml ，便于单独发版与依赖隔离。

## 3.7 examples/ — 示例⼯程

示例⽬录 各⾃独⽴ 管理依赖（ pyproject.toml + uv.lock ），便于读者按需拷⻉或参考。官⽅examples/README.md 表格中重点介绍的部分包括：

<table><tr><td>目录</td><td>侧重点(简述)</td></tr><tr><td>deep_research/</td><td>多步检索、子智能体、反思等研究型模式</td></tr><tr><td>content-builder-agent/</td><td>记忆(如 AGENTS.md)、skills、子智能体与内容生成</td></tr><tr><td>text-to-sql-agent/</td><td>自然语言转 SQL、技能工作流(本仓库另有此示例,可与书中「典型应用」对照)</td></tr><tr><td>ralph_mode/</td><td>循环自治模式,借助文件系统持久化上下文</td></tr><tr><td>downloading_agents/</td><td>「智能体即文件夹」——下载、解压、运行</td></tr></table>

此外，仓库中还可找到如 async-subagent-server/ （异步⼦智能体服务端模式）、

nvidia\_deep\_agent/ （GPU/领域技能示例）等，均属于 同⼀ examples/ ⽣态下的变体，适合作为 harness 扩展与垂直场景参考。

## 3.8 .github/

CI ⼯作流：各包 lint、测试、发布相关 workflow。

脚本与模板：PR/Issue 模板、发布说明脚本等。

静态资源：如 README.md 引⽤的 logo 等图⽚。

## 4. 构建与开发工具链

与 AGENTS.md README.md 及 libs/Makefile ⼀致，⽇常开发依赖如下：

<table><tr><td>工具</td><td>用途</td></tr><tr><td>uv</td><td>包管理与锁文件解析;替代传统pip/poetry工作流,各包目录下独立uv lock</td></tr><tr><td>make</td><td>通过libs/Makefile 聚合lint、format、lock、lock-check等,并向下调用各libs/*/Makefile</td></tr><tr><td>ruff</td><td>快速 lint 与 format;项目倾向行内# noqa 处理个别例外,per-file-ignores仅用于测试等类别策略</td></tr><tr><td>ty</td><td>静态类型检查</td></tr><tr><td>pytest</td><td>单元测试与集成测试;make test或uv run --group test pytest...(以各包配置为准)</td></tr></table>

Python 版本提示： libs/Makefile 中为 acp 包使⽤ Python 3.14，其余参与聚合的包默认按3.12 解析锁⽂件，这在多包 CI 与本地 uv lock 时需注意。

## 5. 关键配置文件

<table><tr><td>文件</td><td>作用</td></tr><tr><td>libs/*/pyproject.toml</td><td>各包元数据、依赖、工具配置(ruff、pytest、uv sources 等)</td></tr><tr><td>libs/*/uv.lock</td><td>各包独立的依赖锁定,保证可复现安装</td></tr><tr><td>release-please-config.json(根目录)</td><td>与 Release Please 流程配合的版本与 changelog 自动化(详见 .github/RELEASING.md 等文档)</td></tr><tr><td>.pre-commit-config.yaml</td><td>提交前钩子(格式化、换行、部分路径排除等)</td></tr><tr><td>.mcp.json</td><td>MCP 相关配置;AGENTS.md 建议需要时可配合文档类 MCP 使用</td></tr></table>

## 刻意未采⽤的模式：

根⽬录 ⽆ setup.py 、⽆ 单⼀「全仓库⼀体」的 uv workspace。

每个库包 独⽴发版、独⽴锁⽂件，依赖关系通过 PyPI 或 \[tool.uv.sources] 的 可编辑本地路径 在开发时桥接。

## 6. 如何从文档回到代码

1. 产品叙事与快速上⼿：读根⽬录 README.md （安装、 create\_deep\_agent 最⼩示例、CLI 简介、LangGraph 原⽣性说明）。
2. 贡献与内部约定：读 AGENTS.md （monorepo 结构、命令、测试规范、CLI/Textual 专项、evals 数据约束、PR 约定）。
3. 改某⼀包：进⼊对应 libs/<name>/ ，阅读该包 pyproject.toml 与 Makefile ，再下钻源码。

下⼀章将基于 libs/deepagents/deepagents/graph.py 等模块，从 Harness 三层架构（后端 /中间件 / 图编排）展开设计哲学与默认中间件栈顺序。

# 第 2 章：核心设计哲学与架构总览

## 主要参考源码路径

⼯⼚与默认栈： libs/deepagents/deepagents/graph.py （ create\_deep\_agent ）

后端协议与实现： libs/deepagents/deepagents/backends/protocol.py 、state.py 、 filesystem.py 、 composite.py 、 sandbox.py 等

中间件： libs/deepagents/deepagents/middleware/

对外 API 聚合： libs/deepagents/deepagents/ \_init \_.py

产品表述： README.md ；威胁建模与组件映射： libs/deepagents/THREAT\_MODEL.md

## 1. Harness 模式：不在 LangChain 之外「另起炉灶」

Deep Agents 的核⼼哲学是 Harness（⻢具）：不从零实现⼀套 Agent 运⾏时，⽽是在 LangChain提供的 create\_agent 之上，通过 中间件（middleware）、后端（backend） 与 默认系统提示，把「规划、⽂件、⼦智能体、上下⽂压缩」等能⼒ 层叠 上去。

这样做的⼯程收益包括：

复⽤ LangGraph 的 CompiledStateGraph ⽣态（流式、checkpoint、Studio 等，README.md 明确强调）。

组合优于继承：⾏为主要通过 create\_deep\_agent( .) 的 参数（ tools middlewarebackend subagents 、 skills 、 memory interrupt\_on 等）声明，⽽⾮深继承树。

边界清晰：存储与命令执⾏落在 Backend 协议；⼯具注⼊与提示增强落在 Middleware；最终执⾏图仍由 create\_agent → CompiledStateGraph 承担。

## 2. 三层架构

## 2.1 后端层（存储 + 执⾏）

抽象： BackendProtocol 定义智能体「⽂件类」能⼒（列表、读写、搜索等）的统⼀接⼝；SandboxBackendProtocol 扩展 可执⾏环境（如 shell），供 execute 等⼯具在 有沙箱 时真正跑命令。

典型实现（均在 deepagents.backends 包内，名称随版本演进以源码为准）：

StateBackend ：⽂件内容挂在 LangGraph 状态 中，适合 ephemeral、⽆本地盘暴露的场景。

： FilesystemBackend ：直接读写 真实⽂件系统（需注意路径与 virtual\_mode 等安全语义）。

： CompositeBackend ：路径前缀 路由 到不同后端（例如默认状态 + /memories/ ⾛存储后端）。

BaseSandbox 等：实现 SandboxBackendProtocol ，对接具体沙箱实现；合作伙伴包（ libs/partners \* ）常在此层提供远程/隔离执⾏环境。

设计含义：同⼀套 ⽂件类中间件与⼯具，可在「纯内存状态」「本地盘」「远程沙箱」间切换，Harness 上层 API 保持稳定。

## 2.2中间件层（⼯具注⼊+提示/状态协作）

中间件负责把 ⼯具 注册到 agent、在模型调⽤前后 改写消息或状态、以及与其它层协作（如摘要写回⽂件、⼦智能体隔离上下⽂）。

代表性中间件（模块位于 libs/deepagents/deepagents/middleware/ ）包括：

FilesystemMiddleware ：挂载 ls / read\_file write\_file edit\_file / globgrep 等与 backend 绑定的⼯具。

. SubAgentMiddleware ：提供 task ，⽤于同步/内联⼦智能体规格。

AsyncSubAgentMiddleware 当 subagents 中含 异步/远程 规格（如带 graph\_id 的AsyncSubAgent ）时启⽤。

SummarizationMiddleware （由 create\_summarization\_middleware ⼯⼚创建）：⻓对话 ⾃动摘要、⼤输出落盘等上下⽂治理。

MemoryMiddleware ：在启⽤ memory= 时，把指定 记忆⽂件（如 AGENTS.md ）注⼊系统提示。

SkillsMiddleware ：在启⽤ skills= 时，从后端路径加载 技能 描述，扩展可复⽤程序性知识。

PatchToolCallsMiddleware ：修正/规范化⼯具调⽤形态，提升与模型输出格式的兼容性。

LangChain ⾃带：如 TodoListMiddleware HumanInTheLoopMiddleware ；以及AnthropicPromptCachingMiddleware （对⾮ Anthropic 模型可配置为 ignore ，避免⽆效缓存头）。

默认 ⼯具集 在 create\_deep\_agent 的⽂档字符串中与实现中保持⼀致，包括：

```txt
write universally、ls、read_file、write_file、edit_file、glob、grep、execute
(仅当 backend 支持沙箱协议时可用)、task。
```

## 2.3 图编排层（LangGraph / LangChain Agent）

```txt
create_deep_agent 最终调用 LangChain 的 create_agent(…)，并返回经 .with_config(...) 处理后的 CompiledStateGraph。
```

其中将 recursion\_limit 设为 9999 ，避免复杂多步任务过早被默认递归上限截断（具体⻅下⽂代码引⽤）。

## 3. 组合式 API： create\_deep\_agent 作为唯一总装车间

下⾯摘录 graph.py 末尾 组装图 的核⼼⽚段（省略部分参数传递，仅突出调⽤链）：

```python
return create_agent(
    model,
    system_prompt=final_system_prompt,
    tools=tools,
    middleware=deepagent_middleware,
    response_format=response_format,
    context_schema=context_schema, 
```

python

```python
checkpoint=checkpoint,
store=store,
debug=debug,
name=name,
cache=cache,
).with_config(
{
    "recursion_limit": 9_999,
    "metadata": {
    "ls_integration": "deepagents",
    "versions": {"deepagents": __version__},
    "lc_agent_name": name,
    },
    }
) 
```

系统提示：若调⽤⽅传⼊ system\_prompt ，会与内置的 BASE\_AGENT\_PROMPT 拼接（字符串拼接或 SystemMessage 的 content blocks 合并），保证 Deep Agent ⾏为基线（简洁、少废话、先理解再⾏动等）始终存在。

## 与其它模块的关系：

. libs/cli ：消费 SDK，构建终端产品与延迟加载策略。

libs/acp / libs/repl / examples \* ：在同⼀ CompiledStateGraph 之上包装不同 ⼊⼝形态（协议、REPL、业务示例）。

. libs/partners ：多通过 Backend / 沙箱 替换，扩展执⾏环境⽽⾮改写图核⼼。

## 4. 默认中间件栈顺序 （必读）

下列顺序与 graph.py 内⽂档字符串及实现 ⼀致（ skills memory / interrupt\_on / 异步⼦智能体为 条件插⼊）：

## 1. 基底（Base）

TodoListMiddleware

. SkillsMiddleware （仅当传⼊ skills ）

. FilesystemMiddleware

. SubAgentMiddleware

. SummarizationMiddleware （⼯⼚⽣成）

. PatchToolCallsMiddleware

AsyncSubAgentMiddleware （仅当存在异步类 subagents ）

## 2. ⽤户插⼊点

. 调⽤⽅传⼊的 middleware=\[ .] 紧接在上述基底之后、AnthropicPromptCachingMiddleware 之前。

## 3. 尾部（Tail）

AnthropicPromptCachingMiddleware （ unsupported\_model\_behavior="ignore" 时对⾮Anthropic 模型静默）

. MemoryMiddleware （仅当传⼊ memory ）

HumanInTheLoopMiddleware （仅当传⼊ interrupt\_on ）

设计决策说明（源码注释）：缓存中间件放在靠后，且 记忆中间件在缓存之后，是为了避免记忆更新破坏 Anthropic 侧 prompt cache 前缀 的稳定性。

⼦智能体默认栈：主智能体中的「通⽤⼦智能体」（ general-purpose ）若未由⽤户覆盖，会由框架注⼊⼀条 略简化但同族 的中间件链（含 Todo、⽂件系统、摘要、补丁、可选 Skills、Anthropic缓存等），保证⼦调⽤与主智能体 能⼒模型对⻬；细节⻅ graph.py 中 general\_purpose\_spec与 SubAgent 预处理逻辑。

## 5. 架构分层示意图 （Mermaid）

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/02b3528e-b243-4cb0-b036-faa38c49ff02/55cf69aefd57cbd481c0f8b7cfcf9219083e2dfb43c8f434ab49328f513e96d4.jpg)

## 6. 小结：读懂 Harness 的三条线索

1. 后端换⽪、⼯具不变：⽂件类⼯具语义稳定，变的只是 数据落在 state、磁盘还是远程沙箱。
2. 中间件顺序即策略顺序：尤其是 摘要、缓存、记忆、⼈⼯审批 的相对位置，直接影响 成本、稳定性与合规。
3. 图仍是 LangGraph 原⽣产物：便于与⽣态内 checkpoint、流式、可观测性⽅案 直接对接，Deep Agents 专注把 「像 Claude Code ⼀样能⼲活」 的默认⾏为 组件化。

后续章节可沿 单类中间件源码、Backend 协议演进 或 libs/cli 如何延迟加载并 pin SDK 等专题继续深⼊。

## 第 3 章：入口函数 create\_deep\_agent()

源码路径： libs/deepagents/deepagents/graph.py

本⽂从「Harness ⼯程」视⻆说明 Deep Agents 的主装配⼊⼝：如何把模型、系统提示、中间件栈、⼦智能体与 LangGraph 运⾏配置组合成可执⾏的 CompiledStateGraph 。

## 1. 函数签名与返回类型

完整签名为：

```python
def create_deep_agent(
    model: str | BaseChatModel | None = None,
    tools: Sequence[BaseTool | Callable | dict[str, Any]] | None = None,
    *, 
    system_prompt: str | SystemMessage | None = None,
    middleware: Sequence[AgentMiddleware] = (), 
    subagents: Sequence[SubAgent | CompiledSubAgent | AsyncSubAgent] | None = None,
    skills: list[str] | None = None,
    memory: list[str] | None = None,
    response_format: ResponseFormat[ResponseT] | type[ResponseT] | dict[str, Any] | None = None,
    context_schema: type[ContextT] | None = None,
    checkpointer: Checkpointer | None = None,
    store: BaseStore | None = None,
    backend: BackendProtocol | BackendFactory | None = None,
    interrupt_on: dict[str, bool | InterruptOnConfig] | None = None,
    debug: bool = False,
    name: str | None = None,
    cache: BaseCache | None = None,
) → CompiledStateGraph[AgentState[ResponseT], ContextT, _InputAgentState, _OutputAgentState[ResponseT]]:
... 
```

Harness 要点： 该函数是「声明式装配⾯」：调⽤⽅通过参数描述能⼒边界（⼯具、后端、⼦智能体、⼈机协同等），内部统⼀转成 langchain.agents.create\_agent 可消费的结构，最后再套上LangGraph 的运⾏配置（递归深度、元数据）。

## 2. 默认模型与模型解析

## 2.1 默认模型

当 model is None 时，使⽤ get\_default\_model() ：

```python
def get_default_model() → ChatAnthropic:
    return ChatAnthropic(
    model_name="claude-sonnet-4-6",
    ) 
```

python

需要环境中配置 ANTHROPIC\_API\_KEY

这是 Deep Agent 的「开箱即⽤」默认，体现产品与 Anthropic ⽣态的默认绑定。

## 2.2 resolve\_model()

否则执⾏ resolve\_model(model) （定义于 libs/deepagents/deepagents/\_models.py ）：

. 若已是 BaseChatModel 实例，原样返回。

若为 provider:model 形式的字符串，经 langchain.chat\_models.init\_chat\_model 解析；OpenRouter 等路径还包含版本检查与归因头等策略。

设计含义： Harness 把「字符串配置」与「已构造模型对象」统⼀成单⼀下游类型，便于在中间件与⼦智能体中复⽤同⼀套 BaseChatModel 假设。

## 3. 后端默认值

```txt
backend = backend if backend is not None else StateBackend() 
```

python

未显式传⼊ backend 时，⽂件与⼯具所⻅存储落在 LangGraph 状态通道 中（线程内持久、跨线程不共享），详⻅后端章节对 StateBackend 的说明。

## 4. 系统提示拼装： BASE\_AGENT\_PROMPT

## 4.1 拼装规则

. system\_prompt is None ：仅使⽤ BASE\_AGENT\_PROMPT 。。

system\_prompt 为 str ：⽤户内容在前， BASE\_AGENT\_PROMPT 以 "\n\n" 拼接在后。

： system\_prompt 为 SystemMessage ：在 content\_blocks 末尾追加⼀段⽂本块，内容为BASE\_AGENT\_PROMPT 。

Harness 解读： ⽤户指令永远「前缀化」深度代理的通⽤⾏为契约；基座提示不可被单独省略，从⽽保证⼯具使⽤、语⽓与任务推进策略⼀致。

## 4.2 BASE\_AGENT\_PROMPT 涵盖主题（语义摘要）

源码中 BASE\_AGENT\_PROMPT 为⻓⽂本，可概括为四类约束：

1. 核⼼⾏为： 简洁直接、避免多余开场⽩；歧义时先问再动；若⽤户问「怎么做」可先解释再执⾏。
2. 专业客观性： 准确优先、可礼貌纠正⽤户错误、避免过度奉承或情绪化迎合。
3. 任务执⾏流： 先理解（读⽂件、看模式）→ 再实现 → 再对照需求验证；⻓任务要迭代⽽⾮⼀次声称完成；失败时分析原因⽽⾮盲⽬重试；真正阻塞时再交还⽤户。
4. 进度更新： ⻓任务中间给出简短进度句（已完成什么、下⼀步做什么）。

## 5. 中间件栈装配顺序

主智能体 deepagent\_middleware 的构建顺序如下（与源码⼀致）。

<table><tr><td>顺序</td><td>中间件</td><td>条件</td></tr><tr><td>1</td><td>TodoListMiddleware</td><td>始终</td></tr><tr><td>2</td><td>SkillsMiddleware</td><td>skills is not None</td></tr><tr><td>3</td><td>FilesystemMiddleware</td><td>始终(传入 backend)</td></tr><tr><td>4</td><td>SubAgentMiddleware</td><td>始终(内联/编译子智能体列表)</td></tr><tr><td>5</td><td>SummarizationMiddleware</td><td>始终(create_summarizationMiddleware(model, backend))</td></tr><tr><td>6</td><td>PatchToolCallsMiddleware</td><td>始终</td></tr><tr><td>7</td><td>AsyncSubAgentMiddleware</td><td>存在异步子智能体(见下节)</td></tr><tr><td>8</td><td>用户 middleware</td><td>middleware 非空时 extend</td></tr><tr><td>9</td><td>AnthropicPromptCachingMiddleware</td><td>始终(unsupported_model_behavior=&quot;ignore&quot;,非 Anthropic 模型则静默跳过缓存头)</td></tr><tr><td>10</td><td>MemoryMiddleware</td><td>memory is not None</td></tr><tr><td>11</td><td>HumanInTheLoopMiddleware</td><td>interrupt_on is not None</td></tr></table>

设计决策（注释原意）： AnthropicPromptCachingMiddleware 与 MemoryMiddleware 放在尾部，是为了避免记忆注⼊破坏 Anthropic 提示缓存前缀的有效性。

## 6. 子智能体：内联、编译与异步

## 6.1 分流逻辑

对 subagents 迭代时：

若 spec 含 graph\_id → 视为 AsyncSubAgent ，进⼊ async\_subagents ，由AsyncSubAgentMiddleware 处理（⾮阻塞、远程/后台任务语义）。

若含 runnable → CompiledSubAgent ，原样进⼊ SubAgentMiddleware

. 否则视为声明式 SubAgent ：补全 model （ resolve\_model ）、默认中间件栈（Todo +Filesystem + Summarization + Patch + 可选 Skills + Anthropic 缓存）、合并 tools 与interrupt\_on 继承规则后进⼊内联列表。

## 6.2 默认 general-purpose ⼦智能体

若内联⼦智能体列表中没有名为 general-purpose 的项，则在列表头部插⼊⼀份默认规格：

. 基于 GENERAL\_PURPOSE\_SUBAGENT 展开；

model 与主智能体相同；

. tools 为主调⽤传⼊的 tools （或空）；

中间件：Todo、 FilesystemMiddleware create\_summarization\_middlewarePatchToolCallsMiddleware ，若主智能体有 skills 则再加 SkillsMiddleware ，最后加AnthropicPromptCachingMiddleware ；

. 若顶层配置了 interrupt\_on ，会写⼊该默认⼦智能体规格。

Harness 要点： 这样保证 task ⼯具始终有⼀个「通⽤⼦代理」可⽤，同时允许⽤户通过同名spec 覆盖默认⾏为。

## 7. 收尾： create\_agent 与 with\_config

最终调⽤：

```python
return create_agent(
    model,
    system_prompt=final_system_prompt,
    tools=tools,
    middleware=deepagent_middleware,
    response_format=response_format,
    context_schema=context_schema,
    checkpointer=checkpoint,
    store=store,
    debug=debug,
    name=name,
    cache=cache,
).with_config(
    {
    "recursion_limit": 9_999,
    "metadata": {
    "ls_integration": "deepagents",
    "versions": {"deepagents": __version__},
    "lc_agent_name": name,
    },
    }
) 
```

recursion\_limit=9999 ： 显式抬⾼ LangGraph 递归/步数上限，避免复杂任务过早被图运⾏时截断。

metadata ： 为 LangSmith 等可观测性集成预留标识（集成名、库版本、逻辑 agent 名）。

## 8. 模块关系小结

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/02b3528e-b243-4cb0-b036-faa38c49ff02/21482159580e53efb8ce87c5a858c2cc306f075c8eed8cc637ab44bfc60ac9e5.jpg)

## 9. 参考与延伸阅读

后端契约： libs/deepagents/deepagents/backends/protocol.py

. 各中间件实现： libs/deepagents/deepagents/middleware/

模型解析： libs/deepagents/deepagents/\_models.py

## 第 4 章：后端协议 BackendProtocolSandboxBackendProtocol

源码路径： libs/deepagents/deepagents/backends/protocol.py

本章描述 Deep Agents 的「存储与⽂件操作」抽象边界：所有后端实现同⼀套同步/异步 API，供FilesystemMiddleware 等 harness 层调⽤。该模块同时定义批量传输、执⾏结果与错误码等数据结构。

## 1. BackendProtocol ：抽象基类与契约

BackendProtocol 继承 abc.ABC （注释说明使⽤ @abstractmethod 的替代⽅案以避免仅实现⼦集的⼦类被破坏），语义上仍是统⼀后端协议：

⽂件可落在状态、磁盘、对象存储、远程沙箱等任意实现，但对上层暴露相同的 ls readwrite edit / grep / glob / upload\_files / download\_files 形状。

⽂档约定逻辑上的 FileData 结构（⻅下⽂）；并说明遗留数据可能仍为 content:list\[str] （按 \n 拆⾏），实现侧应兼容并可能发出 DeprecationWarning 。

## 1.1 核⼼⽅法（同步）

<table><tr><td>方法</td><td>职责摘要</td></tr><tr><td>ls(path)</td><td>列出目录项,返回 LsResult</td></tr><tr><td>read(file_path, offset=0, limit=2000)</td><td>按行窗口读取,返回 ReadResult (内含格式化后的可读文本或错误)</td></tr><tr><td>write(file_path, content)</td><td>新建文件(已存在则失败),返回 WriteResult</td></tr><tr><td>edit(file_path, old_string, new_string, replace_all=False)</td><td>精确字符串替换,返回 EditResult</td></tr><tr><td>grep(pattern, path=None, glob=None)</td><td>字面量子串搜索(非正则),返回 GrepResult</td></tr><tr><td>glob(pattern, path=&quot;/&quot;)</td><td>路径 glob,返回 GlobResult</td></tr><tr><td>upload_files(files)</td><td>批量上传(path, bytes),返回list[FileUploadResponse]</td></tr><tr><td>download_files(paths)</td><td>批量下载路径列表,返回list[FileDownloadResponse]</td></tr></table>

## 1.2异步变体

每个主要同步⽅法对应 a\* 版本（如 als aread awrite ），默认实现为asyncio.to\_thread 包装同步⽅法，⼦类可按需覆盖以实现真异步 I/O。

## 1.3弃⽤适配层

为实现平滑迁移，仍保留 ls\_info glob\_info grep\_raw 等旧名：内部转发到新 API 并发出DeprecationWarning ，计划在 v0.7 移除。

## 2. SandboxBackendProtocol ：在执行环境中扩展

```python
class SandboxBackendProtocol(BackendProtocol):
    @property 
```

python

```python
def id(self) → str: ...
    def execute(self, command: str, *, timeout: int | None = None) → ExecuteResponse: ...
    async def aexecute(self, command: str, *, timeout: int | None = None) → ExecuteResponse: ... 
```

在普通⽂件协议之上增加 execute aexecute ：在隔离环境（容器、VM、远程主机）中运⾏shell 命令。

要求提供 id ：实例的稳定标识，便于观测与关联。

execute\_accepts\_timeout(cls) 使⽤ lru\_cache 对 execute 签名做内省，判断⼦类是否⽀持 timeout 关键字（兼容旧版后端包）。

与 harness 的关系： 仅当后端实现 SandboxBackendProtocol 时，中间件暴露的 execute ⼯具才能真实执⾏命令；否则⼯具返回错误说明（⻅ create\_deep\_agent ⽂档字符串）。

## 3. 关键数据类型

以下名称均来⾃ protocol.py ，类型以源码为准。

## 3.1 FileData （ TypedDict ）

content: str ：UTF-8 ⽂本或 base64 承载的⼆进制。

encoding: str ：如 "utf-8" / "base64" 。

created\_at / modified\_at ： NotRequired\[str] ，ISO 8601 时间戳。

## 3.2 FileInfo （ TypedDict ）

必填： path 。。

可选： is\_dir 、 size 、 modified\_at （后端可尽⼒⽽为）。

## 3.3 GrepMatch （ TypedDict ）

path 、 line （1 基⾏号）、 text （匹配⾏内容）。

## 3.4 ReadResult （ dataclass ）

. error: str | None

file\_data: FileData | None

## 3.5 WriteResult dataclass

error path files\_update 字段；构造函数仍接受已弃⽤的 files\_update ，会触发DeprecationWarning （状态更新现由后端内部处理）。

## 3.6 EditResult （ dataclass ）

error 、 path files\_update （同上）、 occurrences （替换次数或失败时为 None ）。

说明： 编辑的「前后⽂ diff」若需展示，由中间件或⼯具层基于返回信息构造；协议层的EditResult 本身不承载 old\_content / new\_content / diff 字段。

## 3.7 LsResult / GrepResult / GlobResult （ dataclass ）

统⼀为 error + 成功载荷 entries matches ）

## 3.8 FileDownloadResponse / FileUploadResponse （ dataclass ）

下载： path 1 content: bytes | None 、 error 。

. 上传： path 、 error。

⼆者均⽀持批量操作中的部分成功：按输⼊顺序⼀⼀对应，通过 error 字段区分。

## 3.9 ExecuteResponse （ dataclass ）

当前源码定义为：

. output: str ：合并后的标准输出与标准错误（便于 LLM 消费）。

exit\_code: int | None

truncated: bool ：输出是否被后端截断。

## 4. FileFormat 版本

```txt
FileFormat = Literal["v1", "v2"] 
```

```txt
python 
```

v1 （遗留）： content 为 list\[str] （按 \n 分⾏），⽆ encoding 字段。

. v2 （当前）： content 为单个 str ，并带 encoding （ utf-8 或 base64 ）。

Harness 意义： 状态后端等可在构造时选择格式，便于迁移与兼容旧 checkpoint。

## 5. FileOperationError 字面量

```python
FileOperationError = Literal[
    "file_not_found",
    "permission_denied",
    "is_directory",
    "invalid_path",
] 
```

```txt
python 
```

⽤于上传/下载等可恢复错误的规范化编码，便于模型理解并重试或换策略；⽆法归⼀化时 error也可为后端特定字符串。

## 6. BackendFactory 与 BACKEND\_TYPES

```txt
BackendFactory: TypeAlias = Callable[[ToolRuntime], BackendProtocol]
BACKEND_TYPES = BackendProtocol | BackendFactory 
```

python

BackendFactory ：按运⾏时上下⽂惰性构造后端（例如依赖 ToolRuntime 中的配置）。

在 API 演进中，⼯⼚形式可能标记为弃⽤或受限；调⽤ create\_deep\_agent( .,backend= .) 时以当前包内⽂档与类型为准。

## 7. 设计决策小结

1. 统⼀表⾯、多样实现： 中间件只依赖协议，不感知磁盘与远程沙箱的差异。
2. 同步优先 + 默认线程卸载： 降低实现⻔槛；⾼性能后端可重写异步路径。
3. 批量与部分成功： 上传/下载返回列表，契合⼯具链与 LLM 批处理习惯。
4. 执⾏能⼒分层： BackendProtocol 管⽂件； SandboxBackendProtocol 管 shell，避免⾮沙箱环境误暴露执⾏⾯。
5. 版本化⽂件载荷： FileFormat 明确 v1/v2，减轻状态迁移成本。

## 8. 模块关系

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/02b3528e-b243-4cb0-b036-faa38c49ff02/fb96e0b24f5e885d2558662e488377a3e1951d3a456fd6cd526d3ade96af9225.jpg)

延伸阅读： libs/deepagents/deepagents/backends/ 下各实现类。

## 第 5 章：后端实现详解

源码⽬录： libs/deepagents/deepagents/backends/

包导出： libs/deepagents/deepagents/backends/ \_init \_.py

本章梳理 Deep Agents 提供的全部后端实现、各⾃职责、Harness 使⽤场景，以及「从执⾏推导⽂件操作」这⼀关键抽象。

## 后端实现关系图

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/02b3528e-b243-4cb0-b036-faa38c49ff02/08f72e7f70ede21d2bec975f1921e335d737453b3c006dd0b6cd14dcab9f1ea7.jpg)

## 1. 总览与导出

\_all \_ 公开类型包括：

<table><tr><td>符号</td><td>模块</td><td>角色</td></tr><tr><td>StateBackend</td><td>state.py</td><td>默认;LangGraph 状态内 ephemeral 文件</td></tr><tr><td>FilesystemBackend</td><td>filesystem.py</td><td>本地磁盘真实读写</td></tr><tr><td>StoreBackend</td><td>store.py</td><td>LangGraph BaseStore 命名空间持久化</td></tr><tr><td>CompositeBackend</td><td>composite.py</td><td>按路径前缀路由到不同后端</td></tr><tr><td>LocalShellBackend</td><td>local_shell.py</td><td>磁盘 + 本机无隔离 shell</td></tr><tr><td>LangSmithSandbox</td><td>langsmith.py</td><td>远程沙箱 (LangSmith API)</td></tr><tr><td>BackendProtocol</td><td>protocol.py</td><td>协议基类</td></tr><tr><td>BrentContext / NamespaceFactory</td><td>store.py</td><td>存储后端命名空间构造</td></tr></table>

辅助模块 utils.py 提供 grep/glob/字符串替换等共享逻辑，各后端复⽤。

## 2. StateBackend （ state.py ）

## 2.1 语义

⽂件内容存放在 LangGraph Agent 状态 的 files 通道中。

同⼀线程/会话内随 checkpoint 持久；跨线程不共享。

create\_deep\_agent() 在未传 backend 时使⽤ StateBackend() 。

## 2.2 Harness 机制： CONFIG\_KEY\_READ / CONFIG\_KEY\_SEND

· 通过 langgraph.config.get\_config() 取得当前运⾏配置。

使⽤ LangGraph 内部的 CONFIG\_KEY\_READ CONFIG\_KEY\_SEND ，在⼯具/中间件执⾏上下⽂中读取当前 files 快照，并通过 send 将更新排队为正规 channel 写⼊，⽽不是返回遗留的files\_update 字典。

## 2.3 ⾏为要点

必须在图执⾏上下⽂中使⽤；否则抛出明确错误，提示通过 invoke( ., files={ .}) 预填。

. ⽀持 FileFormat ： v1 v2 （构造参数 file\_format ）。

设计决策： 将「代理⼯作区」与主机⽂件系统解耦，适合 API、多租户或不愿暴露真实路径的场景。

## 3. FilesystemBackend （ filesystem.py ）

## 3.1 语义

对 真实磁盘 做读写、 grep / glob （借助 wcmatch 等）、元数据来⾃ os.stat

root\_dir 控制解析根； virtual\_mode 影响路径语义及⼀定的 traversal 防护（不等于沙箱或进程隔离）。

⽂档中强调：适合本地 CLI/可信开发环境；不适合直接暴露给不可信 Web 流量。

## 3.2安全与运维提示

可读到密钥、 .env 等；配合 HumanInTheLoopMiddleware 或隔离环境使⽤。

max\_file\_size\_mb 等限制减轻⼤⽂件⻛险。

模块关系： LocalShellBackend 继承本类以复⽤全部⽂件 API。

## 4. StoreBackend （ store.py

## 4.1 语义

基于 LangGraph BaseStore ，以 namespace（元组路径）存取条⽬，实现 跨线程/持久 的键值存储抽象。

通过 get\_store() get\_runtime() 等与运⾏时绑定；命名空间可由NamespaceFactory(BackendContext) > tuple\[str, .] 动态⽣成。

## 4.2 校验

. \_validate\_namespace 限制命名空间分量字符集，降低通配符注⼊等⻛险。

设计决策： 把「⻓期记忆 / 项⽬知识」等与 ephemeral 状态分离；通常与 CompositeBackend 组合，把某前缀（如 /memories/ ）路由到存储后端。

## 5. CompositeBackend （ composite.py

## 5.1 语义

. default ：未匹配任何路由时的后端。

. routes: dict\[str, BackendProtocol] ：前缀 → 后端；按前缀⻓度降序匹配，避免歧义。

对每个操作调⽤ \_route\_for\_path ：剥离前缀，把逻辑路径传给⼦后端；返回结果再把路径 重映射 回全局虚拟绝对路径（如 grep / ls 结果中的 path ）。

## 5.2 根⽬录 ls("/") 的聚合⾏为

在根路径列出时，会合并 默认后端 的根列表与 各路由⽬录（作为虚拟⼦⽬录项），呈现统⼀根视图。

## 5.3 执⾏（ execute aexecute ）

执⾏不可按路径路由，始终委托给 default 后端。

仅当 default 实现 SandboxBackendProtocol 时成功；否则 NotImplementedError 并提示需换⽤⽀持执⾏的后端。

## 5.4 批量上传

upload\_files 按⽬标后端分组，每后端批调⽤⼀次，再按原始顺序合并结果，减少远程往返。

Harness 示例（与官⽅ docstring ⼀致）：

```txt
CompositeBackend(
    default=StateBackend(),
    routes Scottish={"memories/": StoreBackend(...)},
) 
```

python

## 6. LocalShellBackend （ local\_shell.py ）

## 6.1 语义

多重继承： FilesystemBackend + SandboxBackendProtocol 。

在本机进程中执⾏ shell：⽆容器隔离、⽆资源上限，与当前⽤户权限⼀致。

## 6.2 execute ⾏为摘要

默认超时常量 DEFAULT\_EXECUTE\_TIMEOUT = 120 （秒）。

将 stdout/stderr 合并进 ExecuteResponse.output （与协议⼀致）。

设计决策： 把「最强能⼒、最弱隔离」的后端显式命名，⽂档中⼤篇幅安全警告，引导⽣产场景改⽤ BaseSandbox 派⽣或远程沙箱。

## 7. BaseSandbox （ sandbox.py ）

## 7.1 核⼼思想：⼀切⽂件操作由 execute + upload\_files 推导

. 抽象基类实现 SandboxBackendProtocol

⼦类只需实现 execute() 与 upload\_files() （及 id 等）； ls 、 read 、 grep 、 glob等通过 在沙箱内执⾏ python3 -c " ." 完成，参数多⽤ base64 嵌⼊ 避免 shell 转义问题。

write ： 先 execute 做存在性检查与建⽬录，再通过 upload\_files 传内容（⼤⽂件不塞进命令⾏参数）。

edit ： ⼩负载⽤内联 JSON+heredoc；超过 \_EDIT\_INLINE\_MAX\_BYTES （50\_000 字节）则上传临时⽂件 再在远端脚本中替换，规避部分沙箱对请求体⼤⼩的限制。

## 7.2 Harness 价值

该模式是 远程执⾏环境 的统⼀适配层：只要远程能跑 shell 且能上传字节流，就能在不变更中间件的前提下提供完整⽂件⼯具集。

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/02b3528e-b243-4cb0-b036-faa38c49ff02/f95de1dca5a514d558d4b5cb6f3e11a604a310be2f978fb8503b46fa1ba93aa1.jpg)

## 8. LangSmithSandbox （ langsmith.py ）

## 8.1 语义

继承 BaseSandbox ，包装 LangSmith SDK 的 Sandbox 实例。

execute ：调⽤ sandbox.run(command, timeout= .) ，把 stdout/stderr 拼成ExecuteResponse.output 。

重写 write ： ⼤内容⾛ SDK 的 write （HTTP body），避免 BaseSandbox.write ⾛命令⾏触发 ARG\_MAX 限制。

重写 download\_files / 相关： 使⽤ SDK 的 read 与异常类型，映射到FileOperationError 。

## 8.2默认超时

实例默认 30 \* 60 秒，可被 execute( ., timeout= .) 覆盖。

设计决策： 在「通⽤沙箱推导」与「平台 SDK 能⼒」之间做针对性覆盖，兼顾可靠性与性能。

## 9. 实现矩阵（便于选型）

<table><tr><td>后端</td><td>持久性</td><td>真实磁盘</td><td>execute</td><td>典型用途</td></tr><tr><td>StateBackend</td><td>线程内 checkpoint</td><td>否</td><td>否</td><td>默认、API、隔离工作区</td></tr><tr><td>FilesystemBackend</td><td>是</td><td>是</td><td>否</td><td>本地开发助手</td></tr><tr><td>StoreBackend</td><td>跨线程 store</td><td>否</td><td>否</td><td>长期记忆、共享知识库</td></tr><tr><td>CompositeBackend</td><td>依子后端</td><td>依子后端</td><td>依 default</td><td>前缀分流</td></tr><tr><td>LocalShellBackend</td><td>磁盘持久</td><td>是</td><td>是(本机)</td><td>可信本机 CLI</td></tr><tr><td>LangSmithSandbox</td><td>远程环境</td><td>沙箱内</td><td>是</td><td>托管远程执行</td></tr></table>

## 10. 小结：Harness 工程师应记住的三点

1. 默认路径是状态后端，不是磁盘；预填⽂件⽤ invoke 的 files 字段。
2. 执⾏能⼒与⽂件能⼒正交：由 SandboxBackendProtocol 与中间件共同裁剪；

CompositeBackend 只在默认后端上执⾏命令。

1. BaseSandbox 是远程沙箱的枢纽设计：以 shell 与上传为最⼩原语，推导全套⽂件⼯具，降低新后端接⼊成本。

## 11. 参考路径

. libs/deepagents/deepagents/backends/protocol.py — 协议与类型

. libs/deepagents/deepagents/backends/state.py

libs/deepagents/deepagents/backends/filesystem.py

. libs/deepagents/deepagents/backends/store.py

libs/deepagents/deepagents/backends/composite.py

. libs/deepagents/deepagents/backends/local\_shell.py

libs/deepagents/deepagents/backends/sandbox.py

libs/deepagents/deepagents/backends/langsmith.py

## 源码位置

libs/deepagents/deepagents/middleware/ \_init \_.py （包说明与公共导出）

各具体中间件： libs/deepagents/deepagents/middleware/ 下各模块

## 1. LLM 侧「工具」的两条路径

在 Deep Agents 的设计⾥，模型最终看到的⼯具集合由两条路径合并⽽成（详⻅middleware/ \_init \_.py 顶部⽂档字符串）：

1. SDK 中间件（本包）：由中间件注册的 tools 、对系统提示的注⼊，以及通过钩⼦对每次请求的拦截；任何通过 create\_deep\_agent 等 SDK ⼊⼝构建的 Agent 都会⾃动带上这套能⼒。
2. 调⽤⽅传⼊的普通⼯具：通过 create\_deep\_agent( ., tools=\[ .]) 等形式传⼊的可调⽤对象，更偏「集成⽅定制、轻量、与具体 CLI/应⽤绑定」。

⼆者在 create\_deep\_agent() 组装阶段被合并为模型最终可⻅的⼯具列表。

## 2. AgentMiddleware 与 wrap\_model\_call()

中间件继承 LangChain 侧的 AgentMiddleware 典型⽤法是重写 wrap\_model\_call() （及异步的 awrap\_model\_call() ）：在每⼀次发往 LLM 的请求真正发出之前，对 ModelRequest 进⾏改写（系统消息、⼯具列表、消息列表等），再交给下游 handler 。

这与「普通⼯具函数」有本质区别：普通⼯具只能在被模型选中并调⽤时执⾏，⽆法在「模型调⽤前」统⼀改写请求。

## 3. 中间件相对普通工具能做什么

<table><tr><td>能力</td><td>说明</td><td>典型例子</td></tr><tr><td>按次过滤工具</td><td>根据运行时解析出的 backend 等条件,动态从本次请求中移除某些工具</td><td>FilesystemMiddleware: 当 backend 未实现SandboxBackendProtocol 时,从请求中去掉 execute</td></tr><tr><td>注入系统提示</td><td>每次调用前把说明追加进 system 消息,让模型知道如何用配套工具</td><td>MemoryMiddleware、SkillsMiddleware</td></tr><tr><td>变换消息</td><td>在进模型前裁剪、替换、统计 token 等</td><td>SummarizationMiddleware: 统计 token、截断旧工具参数、在上下文将满时用摘要替换历史</td></tr><tr><td>跨轮状态</td><td>配合带 reducer 的 state schema,在多轮对话间保留结构化状态</td><td>摘要相关事件、异步任务表等</td></tr></table>

普通⼯具不具备上述「请求前拦截」能⼒，也通常不承担「整段对话级」的状态机职责。

## 3.1 中间件生命周期

中间件遵循明确的⽣命周期，在智能体运⾏的不同阶段执⾏：

## ⽣命周期阶段

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/02b3528e-b243-4cb0-b036-faa38c49ff02/ceff72d4a9adb7b565288e5ecc9b47c001c32d7284e4e31faf4a7287ebfc03d4.jpg)

## ⽣命周期钩⼦

<table><tr><td>钩子方法</td><td>调用时机</td><td>典型用途</td></tr><tr><td>on_agent_init()</td><td>智能体初始化时</td><td>加载配置、初始化状态</td></tr><tr><td>wrap_model_call()</td><td>每次 LLM 调用前</td><td>过滤工具、注入提示、变换消息</td></tr><tr><td>on_tool_call()</td><td>工具执行前</td><td>权限检查、参数验证、日志记录</td></tr><tr><td>on_tool_result()</td><td>工具执行后</td><td>结果过滤、统计、后处理</td></tr><tr><td>on_error()</td><td>发生错误时</td><td>错误处理、重试逻辑、降级策略</td></tr><tr><td>on_agent_destroy()</td><td>智能体销毁时</td><td>清理资源、保存状态</td></tr></table>

## 3.2 错误传播机制

中间件栈中的错误传播遵循明确的规则：

## 错误传播流程

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/02b3528e-b243-4cb0-b036-faa38c49ff02/be6d58ffc6549b71cd51596ea6149b85e8a8577f6b1154ce5118a6b5173dd196.jpg)

## 错误处理策略

<table><tr><td>策略</td><td>说明</td><td>适用场景</td></tr><tr><td>传播</td><td>将错误向上传播,由调用方处理</td><td>非关键错误、调用方可处理</td></tr><tr><td>重试</td><td>自动重试失败的操作</td><td>网络错误、临时故障</td></tr><tr><td>降级</td><td>使用备用方案继续执行</td><td>服务不可用、超时</td></tr><tr><td>忽略</td><td>忽略错误,继续执行</td><td>非关键功能、可选操作</td></tr><tr><td>记录</td><td>记录错误但继续执行</td><td>监控、调试</td></tr></table>

## 错误处理示例

```python
python
from deepagents.middleware import AgentMiddleware
from deepagents.types import ModelRequest, ModelResponse

class ErrorHandlingMiddleware(AgentMiddleware):
    def __init__(self, max_retries: int = 3):
    self.max_retries = max_retries
    self.retry_count = 0

    async def wrap_model_call(
    self,
    request: ModelRequest,
    handler
) → ModelResponse:
    try:
    # 尝试执行请求
    response = await handler(request)
    self.retry_count = 0  # 重置重试计数
    return response
    except TimeoutError as e:
    # 超时错误：重试
    if self.retry_count < self.max_retries:
    self.retry_count += 1
    return await self.wrap_model_call(request, handler)
    raise
    except ConnectionError as e:
    # 连接错误：降级处理
```

```python
return ModelResponse(
    content="服务暂时不可用，请稍后重试。",
    error=str(e)
)

except Exception as e:
# 其他错误：记录并传播
logger.error(f"Middleware error: {e}")
raise
```

## 3.3 性能考量与最佳实践

性能影响因素

<table><tr><td>因素</td><td>影响</td><td>优化建议</td></tr><tr><td>中间件数量</td><td>每个中间件增加处理开销</td><td>保持中间件栈精简,避免不必要的中间件</td></tr><tr><td>消息变换</td><td>复杂的消息变换增加延迟</td><td>使用高效的数据结构,避免不必要的复制</td></tr><tr><td>状态管理</td><td>跨轮状态增加内存占用</td><td>及时清理过期状态,使用弱引用</td></tr><tr><td>工具过滤</td><td>动态过滤增加计算开销</td><td>缓存过滤结果,避免重复计算</td></tr></table>

## 最佳实践

# 1. 保持中间件职责单⼀

python

```python
class GoodMiddleware(AgentMiddleware):
    """只负责一个特定功能"""
    async def wrap_model_call(self, request, handler):
    # 只做工具过滤
    filtered_request = self.filter_tools(request)
    return await handler(filtered_request)
```

# 2. 避免在中间件中执⾏耗时操作

```txt
class BadMiddleware(AgentMiddleware): 
```

```python
async def wrap_model_call(self, request, handler):
    # 错误：在中间件中执行网络请求
    data = await fetch_data_from_external_api()  # 耗时!
    request.messages.append(Message(content=str(data)))
    return await handler(request)
```

# 3. 使⽤缓存优化重复计算

```python
class CachingMiddleware(AgentMiddleware):
    def __init__(self):
    self.cache = {}

    async def wrap_model_call(self, request, handler):
    cache_key = self._compute_cache_key(request)
    if cache_key in self.cache:
    return self.cache[cache_key]

    response = await handler(request)
    self.cache[cache_key] = response
    return response 
```

# 4. 合理使⽤异步

```python
class AsyncMiddleware(AgentMiddleware):
    async def wrap_model_call(self, request, handler):
    # 并行执行多个操作
    task1 = asyncio.create_task(self.preprocess(request))
    task2 = asyncio.create_task(self.load_context())

    processed_request, context = await asyncio.gather(task1, task2)
    request.messages.extend(context.messages)

    return await handler(request)
```

## 4. 何时用中间件、何时用普通工具

优先中间件，当需要：

. 按调⽤动态修改系统提示或⼯具列表；

在多轮之间维护与「请求管线」相关的状态；

. 希望能⼒对所有 SDK 消费者默认可⽤（⽽⾮仅某个 CLI）。

## 优先普通⼯具，当：

. 逻辑⽆状态、⾃包含；

不需要改系统提示、不需要在每次 LLM 调⽤前做统⼀预处理；

. ⼯具仅服务于某⼀集成⽅或单⼀应⽤场景。

## 4.1 自定义中间件完整示例

## 基础中间件模板

```python
python
from deepagents.middleware import AgentMiddleware
from deepagents.types import ModelRequest, ModelResponse, ToolCall, ToolResult

class CustomMiddleware(AgentMiddleware):
    """自定义中间件示例"""
    def __init__(self, config: dict = None):
    self.config = config or {}
    self.state = {}

    async def wrap_model_call(
    self,
    request: ModelRequest,
    handler
) → ModelResponse:
    """拦截并处理模型请求"""

    # 1. 前置处理
    processed_request = await self._preprocess(request)
    # 2. 调用下一个中间件或 LLM
```

```python
response = await handler(processed_request) 
```

# 3. 后置处理

```python
processed_response = await self._postprocess(response)

return processed_response

async def _preprocess(self, request: ModelRequest) → ModelRequest:
    """请求预处理"""
    # 注入系统提示
    system_prompt = self._build_system_prompt()
    request.messages.insert(0, Message(
    role="system",
    content=system_prompt
)) 

    # 过滤工具
    if self.config.get("filter_tools"):
    request.tools = self._filter_tools(request.tools)

    return request

async def _postprocess(self, response: ModelResponse) → ModelResponse:
    """响应后处理"""
    # 记录统计信息
    self._update_stats(response)

    # 添加元数据
    response.metadata["middleware_processed"] = True

    return response

def _build_system_prompt(self) → str:
    """构建系统提示"""
    return f"""
在使用 {self.config.get('name', 'Custom')} 中间件。
状态：{self.state}

def _filter_tools(self, tools: list) → list:
    """过滤工具列表"""
    allowed_tools = self.config.get("allowed_tools", [])
```

```python
if not allowed_tools:
    return tools
return [t for t in tools if t.name in allowed_tools]

def _update_stats(self, response: ModelResponse):
    """更新统计信息"""
stats_key = "total_requests"
self.state[stats_key] = self.state.get(stats_key, 0) + 1
```

## ⽇志记录中间件

python

```python
import logging
from datetime import datetime
from deepagents.middleware import AgentMiddleware
from deepagents.types import ModelRequest, ModelResponse

logger = logging.getLogger(__name__)
class LoggingMiddleware(AgentMiddleware):
    """日志记录中间件"""
    def __init__(self, log_level: str = "INFO"):
    self.log_level = log_level
    self.request_count = 0

    async def wrap_model_call(
    self,
    request: ModelRequest,
    handler
) → ModelResponse:
    self.request_count += 1
    request_id = f"req_{self.request_count}_{datetime.now().timestamp()}"
    # 记录请求
    logger.info(f"[{request_id}] Processing request")
    logger.debug(f"[{request_id}] Request: {request}")

    start_time = datetime.now()
    try:
```

```python
# 执行请求
response = await handler(request)

# 记录成功响应
duration = (datetime.now() - start_time).total_seconds()
logger.info(f"[{request_id}] Request completed in {duration:.2f}s")

# 添加元数据
response.metadata["request_id"] = request_id
response.metadata["duration_seconds"] = duration

return response

except Exception as e:
    # 记录错误
    duration = (datetime.now() - start_time).total_seconds()
    logger.error(f"[{request_id}] Request failed after {duration:.2f}s: {e}")
    raise
```

## 缓存中间件

```python
import hashlib
import json
from deepagents.middleware import AgentMiddleware
from deepagents.types import ModelRequest, ModelResponse

class CachingMiddleware(AgentMiddleware):
    """缓存中间件"""
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
    self.cache = {}
    self.max_size = max_size
    self.ttl_seconds = ttl_seconds

    async def wrap_model_call(
    self,
    request: ModelRequest,
    handler
```

```python
) → ModelResponse:
    # 计算缓存键
    cache_key = self._compute_cache_key(request)

    # 检查缓存
    if cache_key in self.cache:
    cached = self.cache[cache_key]
    if not self._is_expired(cached):
    logger.debug(f"Cache hit for key: {cache_key}")
    return cached["response"]
    else:
    del self.cache[cache_key]

    # 执行请求
    response = await handler(request)

    # 存储到缓存
    self._store_in_cache(cache_key, response)

    return response

def _compute_cache_key(self, request: DemandRequest) → str:
    """计算缓存键"""
    # 基于消息内容和工具列表生成键
    content = json.dumps({
    "messages": [m.content for m in request.messages],
    "tools": [t.name for t in request.tools] if request.tools else [],
    "model": request.model
    }, sort_keys=True)
    return hashlib.md5(content.encode()).hexdigest()

    def _is_expired(self, cached: dict) → bool:
    """检查缓存是否过期"""
    from datetime import datetime, timedelta
    cached_time = datetime.fromisoformat(cached["timestamp"])
    return datetime.now() - cached_time > timedelta(seconds=self.ttl_seconds)

    def _store_in_cache(self, key: str, response: DemandResponse):
    """存储到缓存"""
    from datetime import datetime
```

```python
# 清理过期缓存
self._cleanup_expired()

# 如果缓存已满，删除最旧的条目
if len(self.cache) ≥ self.max_size:
    oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k]["timestamp"])
    del self.cache[oldest_key]

# 存储新条目
self.cache[key] = {
    "response": response,
    "timestamp": datetime.now().isoformat()
}

def _cleanup_expired(self):
    """清理过期缓存"""
    from datetime import datetime, timedelta

expired_keys = [
    key for key, value in self.cache.items()
    if self._is_expired(value)
    ]
    for key in expired_keys:
    del self.cache[key]
```

## 使⽤⾃定义中间件

```python
python
from deepagents import create_deep_agent 
```

# 创建中间件实例

```python
logging_mw = LoggingMiddleware(log_level="DEBUG")
caching_mw = CachingMiddleware(max_size=500, ttl_seconds=1800)
custom_mw = CustomMiddleware(config={
    "name": "MyCustomMiddleware",
    "filter_tools": True,
    "allowed_tools": ["read_file", "write_file", "search"]
}) 
```

# 创建带有中间件的智能体

```python
agent = create_deep_agent(
    model="anthropic/claude-3-5-sonnet-20241022",
    middleware=[logging_mw, caching_mw, custom_mw]
)

# 使用智能体
response = await agent.invoke("请帮我分析这个代码库的结构")
```

## 5. middleware/__init__.py 导出的完整公共 API

以下符号在 \_all \_ 中列出，属于 Deep Agents 对外承诺的中间件相关⼊⼝：

```python
__all__ = [
    "AsyncSubAgent",
    "AsyncSubAgentMiddleware",
    "CompiledSubAgent",
    "FilesystemMiddleware",
    "MemoryMiddleware",
    "SkillsMiddleware",
    "SubAgent",
    "SubAgentMiddleware",
    "SummarizationMiddleware",
    "SummarizationToolMiddleware",
    "create_summarization_tool.middleware",
] 
```

61:73:libs/deepagents/deepagents/middleware/__init__.py

导⼊关系（同⽂件）将各实现类从⼦模块集中 re-export，便于调⽤⽅单点导⼊。

## 6. 模块关系（简图）

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/02b3528e-b243-4cb0-b036-faa38c49ff02/0dfc9485a7e236d12318bc82e574a88bb11f42446d841815b8c51b2f7ccb72a7.jpg)

主图组装逻辑⻅ libs/deepagents/deepagents/graph.py ；各中间件在 wrap\_model\_call 中与create\_agent 的⼯具合并、消息流⽔线协同⼯作。

## 7. 设计要点小结

中间件 = 请求管线扩展点：以「每次模型调⽤」为粒度做横切能⼒（⼯具可⻅性、提示词、消息形态、状态）。

普通⼯具 = 模型决策后的执⾏单元：适合业务动作，不适合替代「调⽤前」的策略与状态管理。

以 \_init \_.py 的 \_all \_ 为准判断哪些类型属于稳定对外 API；其余⼦模块中的符号可能更偏内部实现。

## 源码位置

主实现： libs/deepagents/deepagents/middleware/filesystem.py

： 依赖协议： deepagents.backends.protocol （ BackendProtocolSandboxBackendProtocol 等）

主图挂载： libs/deepagents/deepagents/graph.py 中的 create\_deep\_agent

## 1. 职责概览

FilesystemMiddleware 为 Agent 提供⼀组⽂件与（可选）沙箱执⾏相关的⼯具，并在每次模型调⽤前通过 wrap\_model\_call() ：

按当前解析的 backend 决定是否暴露 execute （不⽀持则从本次请求的⼯具列表中过滤掉）；

. 注⼊⽂件操作与（若适⽤）执⾏相关的系统提示；

对超⼤ HumanMessage 与 ToolMessage 做卸载（eviction）：将内容写⼊ backend，替换为短引⽤，缓解上下⽂窗⼝压⼒。

类⽂档字符串中的核⼼描述：

```txt
519:531:libs/deepagents/deepagents/middleware/filesystem.py
class FilesystemMiddleware(AgentMiddleware[FilesystemState, ContextT,
ResponseT]):
    """Middleware for providing filesystem and optional execution tools to an
agent.

This middleware adds filesystem tools to the agent: `ls`, `read_file`, 
`write_file`, 
`edit_file`, `glob`, and `grep'.

Files can be stored using any backend that implements the
`BackendProtocol`. 
```

```txt
If the backend implements `SandboxBackendProtocol`, an `execute` tool is also added
for running shell commands.
This middleware also automatically evicts large tool results to the file system when
they exceed a token threshold, preventing context window saturation. 
```

## 2. 提供的工具

<table><tr><td>工具名</td><td>作用</td></tr><tr><td>ls</td><td>列出目录</td></tr><tr><td>read_file</td><td>按行分页读取文件</td></tr><tr><td>write_file</td><td>写入文件</td></tr><tr><td>edit_file</td><td>字符串查找替换编辑</td></tr><tr><td>glob</td><td>按模式匹配路径</td></tr><tr><td>grep</td><td>在目录/文件中搜索</td></tr><tr><td>execute</td><td>仅当 backend 满足 SandboxBackendProtocol 时,在本次 LLM 请求中保留;否则在 wrap_model_call 中从 request.tools 移除</td></tr></table>

execute 在⼯⼚阶段仍会创建，但实际是否进⼊模型可⻅⼯具集由运⾏时 backend 能⼒决定（⻅wrap\_model\_call 中对 execute 的过滤逻辑）。

## 3. 状态与 \_file\_data\_reducer

⽂件内容在 Agent 状态中通过 FilesystemState 持有，字段 files 使⽤⾃定义 reducer 合并更新，并⽀持删除语义（右侧字典中值为 None 表示删除该路径）：

```python
79:112:libs/deepagents/deepagents/middleware/filesystem.py
def _file_data_reducer(left: dict[str, FileData] | None, right: dict[str, FileData | None]) → dict[str, FileData]:
    """Merge file updates with support for deletions.

This reducer enables file deletion by treating `None` values in the right dictionary as deletion markers. It's designed to work with LangGraph's state management where annotated reducers control how state updates merge.
...
"""
if left is None:
    return {k: v for k, v in right.items() if v is not None}

result = {**left}
for key, value in right.items():
    if value is None:
    result.pop(key, None)
    else:
    result[key] = value
return result 
```

设计取舍：与 LangGraph 的 reducer 模型对⻬，使「增量写⽂件」与「显式删除」可以⽤同⼀套files 更新协议表达。

## 4. 大文件与读取限制相关常量

源码中与本章分析直接相关的常量（节选）：

58:76:libs/deepagents/deepagents/middleware/filesystem.py

```python
EMPTY_CONTENT_WARNING = "System reminder: File exists but has empty contents"
GLOB_TIMEOUT = 20.0 # seconds
LINE_NUMBER_WIDTH = 6
DEFAULT_READ_OFFSET = 0
DEFAULT_READ_LIMIT = 100
# Template for truncation message in read_file
# {file_path} will be filled in at runtime
READ_FILE_TRUNCATION_MSG = (
    "\n\n[Output was truncated due to size limits." 
    "The file content is very large." 
    "Consider reformatting the file to make it easier to navigate." 
    "For example, if this is JSON, use execute(command='jq . {file_path}') to pretty-print it with line breaks." 
    "For other formats, you can use appropriate formatting tools to split long lines.")
)
# Approximate number of characters per token for truncation calculations.
# Using 4 chars per token as a conservative approximation (actual ratio varies by content)
# This errs on the high side to avoid premature eviction of content that might fit
NUM_CHARS_PER_TOKEN = 4 
```

<table><tr><td>常量</td><td>含义</td></tr><tr><td>DEFAULT_READ_LIMIT</td><td>默认最多读取100行(可分页)</td></tr><tr><td>NUM_CHARS_PER_TOKEN</td><td>按每token约4字符估算长度,用于截断与卸载阈值计算(偏保守,减少误伤)</td></tr><tr><td>READ_FILE_TRUNCATION_MSG</td><td>超长输出时追加的说明模板,{file_path}运行时填充</td></tr><tr><td>GLOB_TIMEOUT</td><td>glob操作超时20秒</td></tr><tr><td>LINE_NUMBER_WIDTH</td><td>带行号输出时行号列宽6</td></tr><tr><td>EMPTY_CONTENT_WARNING</td><td>文件存在但内容为空的系统提醒文案</td></tr></table>

read\_file 内部会结合⾏数上限与基于 NUM\_CHARS\_PER\_TOKEN 的字符上限做截断，避免单次⼯具返回撑爆上下⽂。

## 5. 工具结果卸载（eviction）与默认阈值

构造参数（节选）：

```python
572:612:libs/deepagents/deepagents/middleware/filesystem.py
def __init._
    self,
    *, 
    backend: BACKEND_TYPES | None = None,
    system_prompt: str | None = None,
    custom_tool_descriptions: dict[str, str] | None = None,
    tool_token_limit_before_evict: int | None = 20000,
    human_message_token_limit_before_evict: int | None = 50000,
    max_execute_timeout: int = 3600,
) → None: 
```

tool\_token\_limit\_before\_evict （默认 20000）：⼯具返回内容超过估算 token 阈值时，写⼊ backend，消息体替换为简短描述与路径引⽤。

human\_message\_token\_limit\_before\_evict （默认 50000）：对⽤户 HumanMessage 的类似卸载，避免单条⽤户输⼊占满窗⼝。

部分⼯具名会排除在卸载逻辑之外（常量 TOOLS\_EXCLUDED\_FROM\_EVICTION ），避免破坏必须内联展示的结果。

设计意图：在「仍把引⽤留在对话⾥」的前提下，把⼤块 payload 迁到 backend，由 read\_file等⼯具按需拉回，从架构上把存储与对话 token解耦。

## 6. 系统提示与 execute

中间件会注⼊⽂件操作指引；若 backend ⽀持执⾏且本次请求保留 execute 会追加执⾏⼯具说明（ EXECUTION\_SYSTEM\_PROMPT 等）。⼯具描述中亦明确 execute 与SandboxBackendProtocol 的关系，避免模型在不可⽤环境下盲⽬调⽤。

## 7. 与其他模块的关系

deepagents.backends BackendProtocol 定义读写列表等能⼒；SandboxBackendProtocol 扩展执⾏能⼒。

create\_deep\_agent ：默认将 FilesystemMiddleware(backend= .) 放⼊主 Agent 的中间件栈；⼦代理在 graph.py 中也会挂载同名中间件以继承⽂件能⼒。

. deepagents.backends.utils ：路径校验、⾏号格式化、grep 结果格式化、truncate\_if\_too\_long 等⼯具函数供本中间件复⽤。

## 8. 小结

⼯具⾯：六⼤⽂件⼯具 + 条件性 execute 。

管线⾯： wrap\_model\_call 统⼀处理⼯具过滤、提示注⼊、消息/结果卸载。

状态⾯： files + \_file\_data\_reducer ⽀持合并与删除。

常量⾯：分⻚读取、字符/token 估算、glob 超时、空⽂件提醒等共同构成「⼤仓库/⼤⽂件」场景下的可操作性与安全边界。

## 源码位置

主实现： libs/deepagents/deepagents/middleware/subagents.py

与主图集成、⼦代理默认中间件栈： libs/deepagents/deepagents/graph.py（ create\_deep\_agent ）

异步远程⼦代理（对照）： libs/deepagents/deepagents/middleware/async\_subagents.py

## 1. 三种子代理规格（TypedDict）

## 1.1 SubAgent ：声明式同步⼦代理

包含 name 、 description system\_prompt ；可选 tools model middlewareinterrupt\_on skills 。⽂档说明在通过 create\_deep\_agent 使⽤时，会⾃动获得默认中间件栈（⻅下⽂第 4 节）。

```python
21:53:libs/deepagents/deepagents/middleware/subagents
class SubAgent(TypedDict):
    """Specification for an agent.

When using `create_deep_agent`, subagents automatically receive a default middleware
stack (TodoListMiddleware, FilesystemMiddleware, SummarizationMiddleware, etc.) before
any custom `middleware` specified in this spec.
...
Optional fields:
tools: Tools the subagent can use.
...
middleware: Additional middleware for custom behavior, logging, or rate limiting. 
```

21:53:libs/deepagents/deepagents/middleware/subagents.py

```txt
interrupt_on: Configure human-in-the-loop for specific tools.
skills: Skill source paths for SkillsMiddleware. 
```

## 1.2 CompiledSubAgent ：预编译 Runnable

提供 name 、 description 与 runnable （ langchain\_core.runnables.Runnable ）。约定⼦代理结束时的状态⾥必须包含 messages ，最后⼀条消息⽂本会作为 ToolMessage 返回主代理。

## 1.3 AsyncSubAgent （ async\_subagents.py ）

⽤于远程、后台任务（ graph\_id 、 url 、 headers 等），由 AsyncSubAgentMiddleware 暴露start\_async\_task 等⼯具，不⾛本⽂的同步 task ⼯具路径。

## 2. SubAgentMiddleware 与 wrap\_model\_call()

该类向 Agent 注册 task ⼯具，并在 wrap\_model\_call() awrap\_model\_call() 中把「如何使⽤⼦代理」的说明追加到系统消息（通过 append\_to\_system\_message ）。

520:529:libs/deepagents/deepagents/middleware/subagents.py

```python
def wrap_model_call(
    self,
    request: ModelRequest[ContextT],
    handler: Callable[[ModelRequest[ContextT]],
    ModelResponse[ResponseT]],
) → ModelResponse[ResponseT]:
    """Update the system message to include instructions on using subagents."""
    if self.system_prompt is not None:
    new_system_message =
    append_to_system_message(request.system_message, self.system_prompt)
    return
    handler(request.override(system_message=new_system_message))
    return handler(request) 
```

设计要点：⼦代理的「调度策略」写在系统提示⾥，⼯具本体负责按 subagent\_type 分发；两者配合降低模型误⽤概率。

## 3. task 工具行为

⼊参： TaskToolSchema description （任务说明）、 subagent\_type （⼦代理名称）。

分发：根据名称在预构建的 subagent\_graphs 中选取 Runnable ，准备⼦状态（从⽗状态过滤\_EXCLUDED\_STATE\_KEYS ），将任务描述封装为 HumanMessage ，调⽤ invoke / ainvoke 。

返回：⼦代理最终状态若含 messages ，取最后⼀条⽂本，strip 后作为 ToolMessage 写回⽗图（ Command 更新）。

CompiledSubAgent 直接使⽤调⽤⽅提供的 runnable ；声明式 SubAgent 在SubAgentMiddleware.\_get\_subagents 中通过 create\_agent() 编译为 Runnable （此处要求spec 已带 model 与 tools 通常由 create\_deep\_agent 预处理填⼊）。

## 4. 默认 GENERAL\_PURPOSE\_SUBAGENT

若⽤户提供的同步⼦代理列表中没有名为 general-purpose 的项， create\_deep\_agent 会⾃动插⼊默认通⽤⼦代理配置：

```txt
282:287:libs/deepagents/deepagents/middleware/subagents.py
GENERAL_PURPOSE_SUBAGENT: SubAgent = {
    "name": "general-purpose",
    "description": DEFAULT_GENERAL_PURPOSE_DESCRIPTION,
    "system_prompt": DEFAULT_SUBAGENT_PROMPT,
} 
```

插⼊逻辑（节选）：

```python
347:351:libs/deepagents/deepagents/graph.py
if not any(spec["name"] = GENERAL_PURPOSE_SUBAGENT["name"] for spec in inline_subagents): 
```

```python
# Add a general purpose subagent if it doesn't exist yet inline_subagents.insert(0, general_purpose_spec) 
```

设计意图：保证主代理始终有⼀个「与主能⼒对⻬的隔离上下⽂」可选，⽤于复杂检索、多步推理等，⽽⽆需⽤户重复配置。

## 5. create\_deep\_agent 中的子代理中间件栈继承

对声明式 SubAgent （⾮ CompiledSubAgent 、⾮ AsyncSubAgent ）， graph.py 在传⼊

SubAgentMiddleware 之前会拼接默认栈：TodoList → Filesystem → Summarization →

PatchToolCalls →（可选）SkillsMiddleware → ⽤户 middleware →

AnthropicPromptCaching。

```python
321:333:libs/deepagents/deepagents/graph.py
# Build middleware: base stack + skills (if specified) + user's
middleware
subagent_middleware: list[AgentMiddleware[Any, Any, Any]] = [
    TodoListMiddleware(),
    FilesystemMiddleware(backend=backend),
    create_summarization_middleware(subagent_model, backend),
    PatchToolCallsMiddleware(),
]
subagent_skills = spec.get("skills")
if subagent_skills:
    subagent_middleware.append(SkillsMiddleware(backend=backend,
sources=subagent_skills))
subagent_middleware.extend(spec.get("middleware", [])
# "ignore" skips caching for non-Anthropic models (see comment
above).
subagent_middleware.append(AnthropicPromptCachingMiddleware(unsupported_model
_behavior="ignore")) 
```

与 SubAgent ⽂档⼀致：⽤户写在 spec ⾥的 middleware 接在默认栈与 Skills 之后，便于扩展⽽不必重写整套 Deep Agent ⾏为。

## 6. interrupt\_on 传播规则

以下⾏为以 create\_deep\_agent 的⽂档与实现为准（与源码⼀致）：

声明式 SubAgent subagent\_interrupt\_on = spec.get("interrupt\_on",interrupt\_on) 默认继承顶层 interrupt\_on ，⼦代理若显式提供 interrupt\_on 则覆盖继承值。

CompiledSubAgent ：不继承顶层 interrupt\_on ；⼈机协作需在 runnable 内部⾃⾏配置。

AsyncSubAgent ：不继承顶层 interrupt\_on ；审批逻辑应在远端图或部署侧实现。

在 SubAgentMiddleware.\_get\_subagents 中，若声明式 spec 上存在 interrupt\_on ，会追加HumanInTheLoopMiddleware(interrupt\_on= .) （需配合 checkpointer 使⽤）。

## 7. 模块关系简图

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/02b3528e-b243-4cb0-b036-faa38c49ff02/bbae2d6a87e90c792d586ace282b2cf939ca24a93d1d1a7b7ffdc8c4205761a3.jpg)

## 8. 小结

统⼀⼊⼝： task + 系统提示中的类型列表，构成主代理对⼦代理的编排⾯。

两种 Runnable 来源： create\_agent() （声明式）或⽤户 CompiledSubAgent.runnable

默认通⽤⼦代理：⽆ general-purpose 时⾃动注⼊，降低使⽤⻔槛。

栈继承在 graph.py SubAgentMiddleware 本身只消费「已加⼯」的 spec；深度默认⾏为由create\_deep\_agent 负责，避免中间件与⼊⼝重复逻辑。

## 源码位置

主实现： libs/deepagents/deepagents/middleware/async\_subagents.py

主图挂载： libs/deepagents/deepagents/graph.py （当 subagents 中含 graph\_id 的规格时归⼊异步列表并追加本中间件）

## 1. 设计背景

异步⼦代理通过 LangGraph SDK 与符合 Agent Protocol 的远端服务交互：主代理启动任务后⽴即拿到 task id，不必阻塞等待⼦图跑完；后续通过轮询、发消息、取消等⼯具与远端 run/thread 同步。

模块头部说明：

```python
1:10:libs/deepagents/deepagents/middleware/async_subagents.py
""Middleware for async subagents running on remote Agent Protocol servers.

Async subagents use the LangGraph SDK to launch background runs on remote [Agent Protocol](https://github.com/langchain-ai/agent-protocol) servers. Unlike synchronous subagents (which block until completion), async subagents return a task ID immediately, allowing the main agent to monitor progress and send updates while the subagent works.

Compatible with LangGraph Platform (managed) and self-hosted servers.
""" 
```

create\_deep\_agent 中的注释亦指出：当前路径⽀持通过 LangSmith 部署等⽅式托管的远端Agent。

## 2. AsyncSubAgent 规格

34:68:libs/deepagents/deepagents/middleware/async\_subagents.py

```python
class AsyncSubAgent(TypedDict):
    """Specification for an async subagent running on an remote Agent Protocol server.
    ...
    """
    name: str
    """Unique identifier for the async subagent."""
    description: str
    """What this subagent does.

    The main agent uses this to decide when to delegate.
    """

    graph_id: str
    """The graph name or assistant ID on the remote server."""
    url: NotRequired[str]
    """URL of the Agent Protocol server.

    Defaults to the LangGraph SDK's default endpoint. Omit to use ASGI transport for local servers.
    """

    headers: NotRequired[dict[str, str]]
    """Additional headers to include in requests to the remote server."""
""" 
```

. graph\_id ：远端上的图名或 assistant id（必填）。

url headers ：⾃选；认证可通过环境变量（如 LANGGRAPH\_API\_KEY 等，⻅类⽂档）或⾃定义头。

## 3. AsyncSubAgentMiddleware 与生命周期工具

中间件构建五类⼯具（内部名如下），覆盖异步任务全⽣命周期：

<table><tr><td>工具名</td><td>作用</td></tr><tr><td>start_async_task</td><td>创建 thread + run,立即返回 task_id(此处等于远端 thread_id),并在状态中记录AsyncTask</td></tr><tr><td>check_async_task</td><td>按task_id查询run状态;成功时拉取thread values取最后一条消息作为result</td></tr><tr><td>update_async_task</td><td>在同一thread上新建run,带上后续用户消息;multitask_strategy=&quot;interrupt&quot;打断当前run</td></tr><tr><td>cancel_async_task</td><td>取消指定run</td></tr><tr><td>list_async_tasks</td><td>列出已跟踪任务;对非终态任务会尝试拉取实时状态更新缓存</td></tr></table>

⼯具列表由 \_build\_async\_subagent\_tools 组装：

```python
837:859:libs/deepagents/deepagents/middleware/async_subagents.py
def _build_async_subagent_tools(
    agents: list[AsyncSubAgent],
) → list[StructuredTool]:
    """Build the async subagent tools from agent specs.
    ...
    """
    agent_map: dict[str, AsyncSubAgent] = {a["name']: a for a in agents}
    clients = _ClientCache(agent_map)
    agents_desc = "\n".join(f"- {a['name']}: {a['description']}" for a in agents)
    launch_desc =
ASYNC_TASK_TOOL_DESCRIPTION.format(available_agents=agents_desc)

    return [
    _build_start_tool(agent_map, clients, launch_desc),
    _build_check_tool(clients),
    _build_update_tool(agent_map, clients),
    _build_cancel_tool(clients), 
```

```python
_build_list_tasks_tool(clients), ] 
```

## 4. 状态： async\_tasks 与 reducer

113:126:libs/deepagents/deepagents/middleware/async\_subagents.py

```python
def _tasks_reducer(
    existing: dict[str,AsyncTask] | None,
    update: dict[str,AsyncTask],
) → dict[str,AsyncTask]:
    """Merge task updates into the existing tasks dict."""
    merged = dict(existing or {})
    merged.update(update)
    return merged

class AsyncSubAgentState(AgentState):
    """State extension for async subagent task tracking."""
async_tasks: Annotated[NotRequired[dict[str,AsyncTask]], _tasks_reducer] 
```

AsyncSubAgentMiddleware.state\_schema = AsyncSubAgentState ，使 task id 与元数据在多轮对话与上下⽂压缩后仍可被⼯具查找（类⽂档明确提到 survive context compaction）。

## 5. 系统提示与使用约束

默认 ASYNC\_TASK\_SYSTEM\_PROMPT 强调：

. 启动后⽴刻把 task\_id 给⽤户，不要⾃动连续轮询；

仅在⽤户要状态/结果时调⽤ check\_async\_task ，且禁⽌循环 poll；

. 历史⾥的状态可能已过期，需⽤⼯具取当前状态；

完整展示 task\_id，不要截断。

```txt
wrap_model_call() 将上述说明与「可用异步子代理类型」列表追加到主系统消息，与同步 SubAgentMiddleware 模式一致。
```

## 6. 客户端与认证

```txt
_ClientCache 按 (url, headers) 缓存 sync/async 的 LangGraph 客户端。
_resolve_headers 默认在未指定时加入 x-auth-scheme: langsmith，便于托管平台场景。
```

```txt
注意：同步路径 get_sync 在 url is None 时会报错，提示 ASGI 传输需要异步调用——集成时需按运行环境选择 sync/async 工具实现（本模块已为各工具提供 func 与 coroutine）。
```

## 7. 与同步子代理、主图的关系

```python
371:374:libs/deepagents/deepagents/graph.py
if async_subagents:
    # Async here means that we run these subagents in a non-blocking manner.
    # Currently this supports agents deployed via LangSmith deployments.
deepagent_middleware.append(AsyncSubAgentMiddleware(async_subagents=async_subagents)) 
```

同步⼦代理： SubAgent / CompiledSubAgent → task ⼯具，阻塞直到⼦ Runnable 完成。

异步⼦代理：带 graph\_id 的 spec → AsyncSubAgentMiddleware ⾮阻塞，适合⻓任务与远端专⽤部署。

## 8. 典型使用场景小结

. ⻓耗时分析、批处理、流⽔线任务，避免占满主 Agent 的 turn。

. ⼦能⼒运⾏在 LangGraph Platform / ⾃托管 Agent Protocol 上，与主应⽤解耦。

. 需要并⾏启动多个远端任务，稍后统⼀ list\_async\_task / check\_async\_task 收结果。

## 9. 小结

规格： AsyncSubAgent 以 name 、 description graph\_id 为核⼼，可选url / headers 。

. 中间件：注册五个⽣命周期⼯具 + 系统提示，状态字段 async\_tasks 持久化任务表。

集成模型：LangGraph SDK + Agent Protocol；与同步 task ⼦代理互补，⾯向远端与⾮阻塞编排。

## 第 10 章：SummarizationMiddleware 上下文压缩

源码路径： libs/deepagents/deepagents/middleware/summarization.py

## 1. 模块定位

本模块为 Deep Agents 提供对话摘要与上下⽂压缩能⼒：在 token ⽤量逼近上限时⾃动压缩历史，或将完整历史卸载到后端存储；同时可选暴露 compact\_conversation ⼯具，供智能体或⼈在回路按需触发压缩。实现上在 LangChain 的 SummarizationMiddleware（ LCSummarizationMiddleware ）之上扩展了 后端卸载、与⼯具层协同 等逻辑。

## 2. 两个中间件类

## 2.1 SummarizationMiddleware （内部类\_DeepAgentsSummarizationMiddleware ）

作⽤： 在 wrap\_model\_call awrap\_model\_call 中，于调⽤主模型前检查是否应摘要；若应摘要，则先卸载旧消息、再调⽤ LLM ⽣成摘要，并⽤ ExtendedModelResponse + Command更新私有状态 \_summarization\_event 。

公开名： SummarizationMiddleware = \_DeepAgentsSummarizationMiddleware ，外部应导⼊ SummarizationMiddleware 。

## 2.2 SummarizationToolMiddleware

作⽤： 注册 compact\_conversation ⼯具；不会⾃动压缩，仅在⼯具被调⽤时执⾏压缩。

组合关系： 构造函数接收⼀个 SummarizationMiddleware 实例，复⽤其模型、后端、阈值与摘要引擎。

与⾃动摘要共享状态： ⼯具路径与⾃动摘要均写⼊同⼀ \_summarization\_event ，⼆者可正确衔接。

资格⻔槛： \_is\_eligible\_for\_compaction 要求对话⽤量达到⾃动摘要触发阈值的⼤约 50%才允许⼿动压缩，避免过早清空上下⽂。

## 3. 工厂函数

<table><tr><td>函数</td><td>说明</td></tr><tr><td>create_summarizationMiddleware(model, backend)</td><td>model 必须是已解析的 BaseChatModel;根据 compute_summarization_defaults(model) 设置 trigger、keep、truncate_args_settings 等。</td></tr><tr><td>create_summarization_toolMiddleware(model, backend)</td><td>model 可为字符串或 BaseChatModel;字符串会先经 deepagents._models.resolve_model 解析,再创建 SummarizationMiddleware 并包一层 SummarizationToolMiddleware。</td></tr></table>

## 4. 触发与保留： trigger / keep

当模型 profile 中存在 max\_input\_tokens 时， compute\_summarization\_defaults 采⽤⽐例策略（与⽂档示例⼀致）：

trigger=("fraction", 0.85) ：⽤量达到上下⽂窗⼝约 85% 时触发摘要。

keep=("fraction", 0.10) ：压缩后保留约窗⼝ 10% 对应的近期消息（具体切分由LangChain 侧 \_determine\_cutoff\_index 等逻辑完成）。

若⽆可靠 profile，则回退为更保守的 token / 条数 默认值（例如 trigger=("tokens",170000) 、 keep=("messages", 6) ），避免误判上下⽂上限。

## 5. 处理流程概要

1. 重建有效消息列表： 若状态中已有 \_summarization\_event ，通过

\_apply\_event\_to\_messages 得到「摘要 HumanMessage + 截断点之后的消息」。

1. （可选）⼯具参数截断： TruncateArgsSettings 可在完整摘要前，对较早 AIMessage 中

write\_file edit\_file 等⼤参数做裁剪，降低 token。

1. 判断是否摘要： 委托内部 \_lc\_helper （LangChain）的 \_should\_summarize ；token 计数默

认使⽤ count\_tokens\_approximately 。

1. 卸载历史： 将待摘要段通过 \_offload\_to\_backend 写⼊后端；路径默认为

{history\_path\_prefix}/{thread\_id}.md ，默认前缀 /conversation\_history 。

1. ⽣成摘要： \_create\_summary / \_acreate\_summary 调⽤ LangChain 侧逻辑。
2. 更新请求与状态： ⽤ \_build\_new\_messages\_with\_path 构造带路径说明的 HumanMessage

（ additional\_kwargs 中 lc\_source="summarization" ），与保留段拼接后调⽤

handler ；并通过 Command(update={"\_summarization\_event": new\_event}) 写⼊事件。

设计要点： 与旧版「直接改 LangGraph messages 状态」不同，当前实现主要在 middleware 状态 中记录 \_summarization\_event ，在每次模型请求时重算有效消息列表，从⽽与 LangGraph 状态模型对⻬。

## 6. 后端文件：运行日志式追加

每个线程对应⼀个⽂件： /conversation\_history/{thread\_id}.md （ thread\_id 来⾃

get\_config()\["configurable"]\["thread\_id"] ，缺失时⽣成 session\_xxxxxxxx ）。

每次摘要事件追加⼀节： # Summarized at {ISO8601 UTC}\n\n +

get\_buffer\_string(filtered\_messages) 。

链式摘要时，会过滤掉此前摘要产⽣的 HumanMessage （ lc\_source = "summarization" ），

避免重复卸载同⼀段摘要⽂本。

读写使⽤ download\_files / adownload\_files 取原始内容，再 write / edit 或

awrite / aedit 追加（因 read 可能返回带⾏号等⾯向 LLM 的格式）。

## 7. ContextOverflowError 处理

在 未 达到预设摘要阈值时，中间件仍会先尝试⽤当前（可能已截断参数的）消息调⽤模型。若调⽤抛出 ContextOverflowError ，则捕获后转⼊摘要路径，⽤「摘要 + 保留近期消息」重试。这样在计数略滞后或边界情况下仍能恢复。

## 8. Token 计数与 LangChain 基类

默认 token\_counter=count\_tokens\_approximatelylangchain\_core.messages.utils ）。

. 核⼼摘要阈值、切分、摘要⽣成等委托给：

```python
from langchain.agents.middleware.summarization import (
    SummarizationMiddleware as LCSummarizationMiddleware,
    # ...
) 
```

python

## 9. 系统提示注入（工具中间件）

```txt
SummarizationToolMiddleware.wrap_model_call / awrap_model_call 通过
append_to_system_message 追加 SUMMARIZATION_SYSTEM_PROMPT，告知模型可使用
compact_conversation 及适用场景（新任务、已完成提炼等）。仅改提示，不自动执行工具。
```

## 10. 与其他模块的关系

deepagents.\_models.resolve\_model create\_summarization\_tool\_middleware 在传⼊字符串模型时使⽤。

. deepagents.middleware.\_utils.append\_to\_system\_message ：拼接系统提示。

： deepagents.backends.protocol backend 可为实例或可调⽤⼯⼚，与 ToolRuntimeRuntime 解析⼀致。

langgraph.types.Command ExtendedModelResponse ：在模型调⽤包装层回写\_summarization\_event 。

## 11. 小结

<table><tr><td>维度</td><td>内容</td></tr><tr><td>自动压缩</td><td>SummarizationMiddleware,比例触发85%/保留10%(有profile时)</td></tr><tr><td>按需压缩</td><td>SummarizationToolMiddleware → compact_conversation</td></tr><tr><td>历史持久化</td><td>后端Markdown按线程追加节</td></tr><tr><td>健壮性</td><td>ContextOverflowError 回退摘要;可选大工具参数预截断</td></tr><tr><td>基座</td><td>LangChain SummarizationMiddleware + Deep Agents 后端与状态扩展</td></tr></table>

## 第 11 章：MemoryMiddleware 与 SkillsMiddleware

## 源码路径：

libs/deepagents/deepagents/middleware/memory.py

. libs/deepagents/deepagents/middleware/skills.py

## 1. 总览：共同点

两者都通过 后端路径 读取内容（不假设本地直连磁盘的具体实现⽅式由 BackendProtocol 完成），并在 系统消息 侧增强模型可⻅上下⽂：

## Memory 与 Skills 协作关系图

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/02b3528e-b243-4cb0-b036-faa38c49ff02/2f946ca25dd7abb2304a6f69c0e5ddf8afc0db2aebf0aebbf5a36760d66f1c64.jpg)

\| 维度 | MemoryMiddleware | SkillsMiddleware |

<table><tr><td>维度</td><td>MemoryMiddleware</td><td>SkillsMiddleware</td></tr><tr><td>内容性质</td><td>持久「记忆」: AGENTS.md 全文注入</td><td>技能: 目录 + SKILL.md,渐进式披露(目录级元数据进提示,全文按需阅读)</td></tr><tr><td>多源策略</td><td>按 sources 顺序拼接,后出现的源排在后面</td><td>按 sources 顺序加载,同名技能后者覆盖前者 (last wins)</td></tr><tr><td>加载时机</td><td>before_agent / abefore_agent 首次写入 memory_contents</td><td>before_agent / abefore_agent 首次写入 skills_metadata</td></tr><tr><td>每次LLM 调用</td><td>wrap_model_call → modify_request将状态中的内容格式化为系统提示片段</td><td>同上,注入技能说明与列表</td></tr></table>

## 2. MemoryMiddleware（ memory.py ）

## 2.1 职责

从可配置的 AGENTS.md 路径列表 读取内容，合并后注⼊系统提示；实现上对 AGENTS.md 规范的兼容加载（模块⽂档明确引⽤该规范）。

MemoryMiddleware 使⽤示例

```python
python
from deepagents import create_deep_agent
from deepagents.middleware import MemoryMiddleware

# 配置 Memory 路径
memory_sources = [
    "~/.deepagents/AGENTS.md",    # 全局配置
    "./ deepagents/AGENTS.md",    # 项目级配置
    "./docs/ARCHITECTURE.md"    # 架构文档
]

# 创建 Memory 中间件
memory middleware = MemoryMiddleware(sources=memory_sources)
```

```python
# 创建带有 Memory 能力的智能体
agent = create_deep_agent(
    model="anthropic/clau de-3-5-sonnet-20241022",
    memory=memory_sources,  # 直接传入路径列表
    # 或者传入中间件实例
    # middleware=[memory_middleware]
)
```

```txt
# 智能体现在可以访问 AGENTS.md 中的项目规范
response = await agent.invoke("请帮我运行项目的测试命令")
```

## AGENTS.md ⽂件示例

markdown

## # 项⽬规范

## # 构建与测试

安装依赖：`uv sync`

- 运⾏测试：`make test`

代码检查：`make lint`

## # 代码⻛格

使⽤ Python 3.10+

- 遵循 PEP 8
- 使⽤ type hints

## # 架构说明

- 核⼼模块在 `libs/deepagents/`

CLI 在 `libs/cli/`

评估在 `libs/evals/`

## 2.2数据源与顺序

典型路径示例： \["\~/.deepagents/AGENTS.md", "./.deepagents/AGENTS.md"] 。

合并规则： 多个源按配置顺序处理； \_format\_agent\_memory 中按 self.sources 顺序输出"{path}\n{content}" 段落，靠后的源在拼接结果中位于更后。

展示名： ⽂档说明由路径⾃动推导（⽆需单独配置 display name 字段）。

## 2.3状态与加载

状态模式： MemoryState 含私有字段 memory\_contents: dict\[str, str] （路径 → 内容）。

缓存： 若状态中已有 memory\_contents before\_agent abefore\_agent 直接返回None ，不重复下载。

错误处理： file\_not\_found 跳过该源；其他错误抛出 ValueError

## 2.4注⼊⽅式

modify\_request 使⽤ MEMORY\_SYSTEM\_PROMPT 模板，将内容包在 \<agent\_memory> 中，并附带较⻓的 \<memory\_guidelines> （引导通过 edit\_file 等更新记忆、何时记录/不记录等）。最终通过 append\_to\_system\_message 拼到当前 system\_message 。

## 2.5 AGENTS.md 格式

标准 Markdown，⽆强制章节结构；常⻅内容包括项⽬概览、构建/测试命令、代码⻛格、架构说明等。

## 3. SkillsMiddleware （ skills.py

## 3.1 职责与模式

实现 Anthropic ⻛格的 Agent Skills 思路，配合 渐进式披露（progressive disclosure）：系统提示中展示技能⽬录（名称、描述、路径等），完整⼯作流在需要时再读取对应 SKILL.md 。

仅通过后端 API（ ls 、 download\_files 等）访问存储，便于 Filesystem / State / 远程等后端互换。

## 3.2技能⽬录结构

每个技能为⼦⽬录，其下必须有 SKILL.md （YAML frontmatter + Markdown 正⽂）；可有helper.py 等辅助⽂件。

## SkillsMiddleware 使⽤示例

```python
from deepagents import create_deep_agent 
```

# 配置 Skills 路径（⽀持多源分层）

```hcl
skills_sources = [
    "/skills/base/",    # 基础技能（只读）
    "/skills/user/",    # 用户自定义技能
    "/skills/project/"    # 项目特定技能（最高优先级）
]
```

# 创建带有 Skills 能⼒的智能体

```python
agent = create_deep_agent(
    model="anthropic/clau de-3-5-sonnet-20241022",
    skills=skills_sources
) 
```

# 智能体现在可以使⽤所有技能

```python
response = await agent.invoke("请帮我创建一个 Python 包")
```

## SKILL.md ⽂件示例

markdown

```txt
name: python-package-creator
description: 创建标准 Python 包结构，包含 pyproject.toml、测试目录等
allowed-tools: write_file, execute, read_file
license: MIT
---
```

# Python 包创建技能

## # 使⽤场景

当⽤户需要创建新的 Python 包时使⽤此技能。

## # ⼯作流程

1. 询问⽤户包名和描述
2. 创建⽬录结构
3. ⽣成 pyproject.toml
4. 创建 \_init \_.py

## 5. 设置测试⽬录

# ⽂件结构

```shell
package_name/ |— pyproject.toml |— src/ | └── package_name/ | └── init.py
└── tests/ └── test_package_name.py 
```

## 3.3 SkillMetadata（与规范对⻬的 TypedDict）

解析⾃ SKILL.md frontmatter，主要字段包括：

. name ： 技能标识（规范建议 1–64 字符、⼩写与连字符等；实现中含校验与警告）。

. description ： 描述（最⻓ 1024 字符，超⻓截断）。

path ： 后端中 SKILL.md 的路径。

可选： license compatibility （最⻓ 500）、 metadata （ dict\[str, str] ）、allowed\_tools （来⾃ allowed-tools ，⽀持空格分隔；兼容逗号分隔的解析）。

另有 MAX\_SKILL\_FILE\_SIZE （10MB）防⽌过⼤⽂件。

## 3.4 多源与覆盖（layering）

sources 为后端上的技能根路径列表，例如 \["/skills/base/", "/skills/user/","/skills/project/"] 。

加载时对每个源调⽤ \_list\_skills \_alist\_skills ，再以 all\_skills\[skill\["name"]]= skill 合并——后遍历的源覆盖同名技能，从⽽⽀持 base → user → project → team 分层。

## 3.5系统提示内容

SKILLS\_SYSTEM\_PROMPT 包含：

技能库位置说明（ \_format\_skills\_locations ，最后⼀项标注更⾼优先级）。

可⽤技能列表（ \_format\_skills\_list ）：名称、描述、可选 license/compatibility、allowed\_tools 、以及 「读取 path 获取完整说明」 的指引。

渐进式使⽤步骤与示例⼯作流。

## 3.6路径约定

使⽤ PurePosixPath 构造虚拟 POSIX 路径，与平台⽆关；具体后端负责落地映射。

## 4. 设计对比小结

Memory 偏向「始终在场的项⽬/⽤户⻓期上下⽂」；Skills 偏向「可插拔、可覆盖的程序化能⼒与流程说明」。

. ⼆者都⽀持 多源；Memory 是顺序拼接，Skills 是按名合并、后者胜。

⼆者都依赖 append\_to\_system\_message 与 后端⼯⼚/实例解析（ ToolRuntime 构造⽅式与Summarization 等中间件⼀致）。

## 5. 模块依赖关系（简图）

```txt
deepagents.backends.protocol (BackendProtocol)
↑
MemoryMiddleware / SkillsMiddleware
→ langchain.agents.middleware.types (AgentMiddleware, DemandRequest, ...)
→ deepagents.middleware._utils.append_to_system_message 
```

skills.py 中技能列表扫描依赖 backend.ls als 与 download\_filesadownload\_files memory.py 仅依赖批量 download\_files / adownload\_files 与路径列表对⻬解析。

## 第 12 章：PatchToolCallsMiddleware 悬空工具调用修复

源码路径： libs/deepagents/deepagents/middleware/patch\_tool\_calls.py

## 1. 问题背景

在多轮对话与⼯具调⽤流程中，可能出现：

. AIMessage 带有 tool\_calls ，但后续没有匹配的 ToolMessage （例如执⾏被中断、⽤户插⼊新消息、图执⾏路径异常等）。

多数聊天模型协议要求 每个 tool\_call 都有对应 tool 结果消息；缺失时易导致后续轮次⾏为异常或模型困惑。

## 2. 中间件职责

类名： PatchToolCallsMiddleware(AgentMiddleware)

在 before\_agent 钩⼦中扫描整条 state\["messages"] ，对每⼀个「有 tool\_calls 却⽆对应ToolMessage 」的调⽤，追加⼀条合成的 ToolMessage ，说明该调⽤已被取消。

## 3. 实现要点

遍历⽅式： 对索引 i 处的每条消息先原样加⼊ patched\_messages ；若为 AIMessage 且含tool\_calls ，则对每个 tool\_call 在 messages\[i:] ⼦序列中查找 type = "tool" 且tool\_call\_id 匹配的回复。

未找到时： 构造 ToolMessage content 为固定英⽂说明（⻅下节）， name 与tool\_call\_id 与原始调⽤⼀致。

. 状态写回： 返回 {"messages": Overwrite(patched\_messages)} ，使⽤ LangGraph 的Overwrite 整体替换消息列表，确保补丁后的列表成为唯⼀真源。

该实现代码量⼩（约四⼗余⾏），但对保证 tool 调⽤闭环 很关键。

## 4. 完整源码引用

```python
1:45:libs/deepagents/deepagents/middleware/patch_tool_calls.py
""Middleware to patch dangling tool calls in the messages history."""
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Overwrite

class PatchToolCallsMiddleware(AgentMiddleware):
    """Middleware to patch dangling tool calls in the messages history."""

def before_agent(self, state: AgentState, runtime: Runtime[Any]) → dict[str, Any] | None:  # noqa: ARG002
    """Before the agent runs, handle dangling tool calls from any AIMessage."""
    messages = state["messages"]
    if not messages or len(messages) = 0:
    return None

    patched_messages = []
    # Iterate over the messages and add any dangling tool calls
    for i, msg in enumerate(messages):
    patched_messages.append(msg)
    if isinstance(msg, AIMessage) and msg.tool_calls:
    for tool_call in msg.tool_calls:
    corresponding_tool_msg = next(
    (msg for msg in messages[i:] if msg.type = "tool" and msg.tool_call_id = tool_call["id"]),  # ty: ignore[unresolved-attribute] 
```

```python
None,
)
if corresponding_tool_msg is None:
    # We have a dangling tool call which needs a ToolMessage
    tool_msg = (
    f"Tool call {tool_call['name']} with id {tool_call['id']} was "
    "cancelled - another message came in before it could be completed."
)
patched_messages.append(
    ToolMessage(
    content=tool_msg,
    name=tool_call["name"],
    tool_call_id=tool_call["id"],
    )
)
return {"messages": Overwrite(patched_messages)} 
```

## 5. 设计决策说明

1. 合成消息语义： 明确告知「被取消」⽽⾮伪造成功/失败⼯具输出，避免模型误以为⼯具已执⾏。
2. 插⼊位置： 补丁紧跟在对应 AIMessage 之后（在 patched\_messages 中的顺序），符合「先调⽤、后结果」的⾃然阅读顺序。
3. 全量 Overwrite ： 避免与 reducer 增量合并产⽣重复或顺序错乱；列表由中间件⼀次性重建。
4. 空消息短路： ⽆消息时返回 None ，不触发⽆意义更新。

## 6. 与其他模块的关系

依赖 LangChain 的 AgentMiddleware AgentState AIMessage 、 ToolMessage 。

依赖 LangGraph 的 Runtime （本实现未使⽤ runtime 参数，保留签名以符合钩⼦约定）与Overwrite 。

通常与负责⼯具执⾏、⼈机协作、或可能中断⼯具链路的中间件/节点配合使⽤，作为 图运⾏前的卫⽣检查（sanitizer）。

# 第 13 章：模型解析与 Provider 支持

源码路径： libs/deepagents/deepagents/\_models.py

## 1. 模块定位

本模块提供 Deep Agents 共⽤的 模型字符串解析、OpenRouter 版本与归因、以及 模型实例与provider:model 规格⽐对 等⼯具函数，供 SDK、 create\_summarization\_tool\_middlewareCLI 配置等复⽤。

## 2. resolve\_model(model: str | BaseChatModel) -> BaseChatModel

## 2.1⾏为摘要

1. 已是 BaseChatModel ： 原样返回。
2. 以 openai: 为前缀： init\_chat\_model(model, use\_responses\_api=True) ，即 OpenAI 路径下 默认⾛ Responses API。
3. 以 openrouter: 为前缀： 先 check\_openrouter\_version() ，再 init\_chat\_model(model,\*\*\_openrouter\_attribution\_kwargs()) 。
4. 其他字符串： init\_chat\_model(model) ，由 LangChain 根据字符串 ⾃动推断 provider。

## 模型解析使⽤示例

```python
from deepagents import create_deep_agent
from deepagents._models import resolve_model
# 方式 1：使用字符串（推荐）
agent = create_deep_agent(
```

python

```python
model="anthropic/claude-3-5-sonnet-20241022",
# 或
# model="openai:gpt-4o",
# model="openrouter:anthropic/claude-3-opus",)

# 方式 2：使用已构造的模型实例
from langchain_anthropic import ChatAnthropic

model = ChatAnthropic(model="claude-3-5-sonnet-20241022")
agent = create_deep_agent(model=model)

# 方式 3：resolve_model 解析
resolved = resolve_model("anthropic/claude-3-5-sonnet-20241022")
print(type(resolved)) # <class
'langchain_anthropic.chat_models.ChatAnthropic'>

# OpenRouter 示例
agent = create_deep_agent(
    model="openrouter:anthropic/claude-3-opus",
    # 自动添加归因头
)
```

## 不同 Provider 配置示例

```python
import os
from deepagents import create_deep_agent

# Anthropic (默认)
agent_anthropic = create_deep_agent(
    model="anthropic/claude-3-5-sonnet-20241022"
)

# OpenAI (使用 Responses API)
agent_openai = create_deep_agent(
    model="openai:gpt-4o"
)

# OpenRouter (带归因)
os.environ["OPENROUTER_APP_URL"] = "https://myapp.com"
```

python

```python
os.environ["OPENROUTER_APP_TITLE"] = "My App"
agent_openrouter = create_deep_agent(
    model="openrouter:anthropic/claude-3-opus"
)

# 自定义模型实例
from langchain_openai import ChatOpenAI

custom_model = ChatOpenAI(
    model="gpt-4o",
    base_url="https://api.custom.com/v1",
    api_key=os.environ["CUSTOM_API_KEY"]
)

agent_custom = create_deep_agent(model=custom_model)
```

## 2.2 代码⻣架

```python
72:96:libs/deepagents/deepagents/_models.py
def resolve_model(model: str | BaseChatModel) → BaseChatModel:
    """Resolve a model string to a `BaseChatModel`.

    If `model` is already a `BaseChatModel`, returns it unchanged.

    String models are resolved via `init_chat_model`. OpenAI models (prefixed with `openai`:) default to the Responses API.

    OpenRouter models include default app attribution headers unless overridden
    via `OPENROUTER_APP_URL` / `OPENROUTER_APP_TITLE` env vars.
    ...
    """
    if isinstance(model, BaseChatModel):
    return model
    if model.startswith("openai:")
    return init_chat_model(model, use_responses_api=True)
    if model.startswith("openrouter:")
    check_openrouter_version()
    return init_chat_model(model, **_openrouter_attribute_kwargs())
    return init_chat_model(model) 
```

## 3. OpenRouter 集成

## 3.1最低版本

常量 OPENROUTER\_MIN\_VERSION = "0.2.0" （ langchain-openrouter ）。

check\_openrouter\_version() ： 若已安装包且版本 低于 该值，抛出 ImportError 并提示升级命令；若包未安装则跳过（后续由 init\_chat\_model 暴露缺失依赖错误）。

## 3.2 默认归因（App Attribution）

OpenRouter 建议通过 HTTP 头做应⽤归因（参⻅ OpenRouter ⽂档）。本模块默认：

app\_url ： https: /github.com/langchain-ai/deepagents （对应 HTTP-Referer 类⽤途）

. app\_title Deep Agents （对应 X-Title 类⽤途）

## 3.3环境变量覆盖

\_openrouter\_attribution\_kwargs 仅在 未设置 对应环境变量时注⼊上述默认值：

. OPENROUTER\_APP\_URL ：若已设置，不覆盖⽤户的 app\_url 。

OPENROUTER\_APP\_TITLE ：若已设置，不覆盖⽤户的 app\_title

这样显式构造参数 > 环境变量 > 本模块默认值 的优先级链与 ChatOpenRouter.from\_env() ⾏为相容。

## 4. 辅助函数

4.1 get\_model\_identifier(model: BaseChatModel) -> str | None

通过 model.model\_dump() 读取序列化配置，在 model\_name 或 model 键上取⾮空字符串。

动机： 各 provider 对「模型 ID 字段名」不统⼀，避免仅靠反射属性。

## 4.2 model\_matches\_spec(model: BaseChatModel, spec: str) -> bool

先取 get\_model\_identifier ；若为 None 则不匹配。

. spec 与 identifier 完全相等 → 匹配。

否则将 spec 按 ⾸个 : 分割为 provider 与 model\_name ；若存在分隔符且 model\_name与 identifier 相等，也视为匹配（例如 "openai:gpt-5" 与 identifier "gpt-5" ）。

约定： 项⽬内⼴泛使⽤ provider:model 单冒号形式的字符串规格。

## 5. 设计决策小结

<table><tr><td>主题</td><td>决策</td></tr><tr><td>OpenAI 前缀</td><td>默认 use_responses_api=True,与 OpenAI 新 API 路径对齐</td></tr><tr><td>OpenRouter</td><td>强制最低包版本 + 默认归因,且尊重用户环境变量</td></tr><tr><td>标识符提取</td><td>走 model_dump(),兼容多 provider 字段名</td></tr><tr><td>规格匹配</td><td>支持完整 spec 或仅模型名与实例 identifier 对齐</td></tr></table>

## 6. 在仓库中的调用关系（示例）

create\_summarization\_tool\_middleware ：当 model 为字符串时 fromdeepagents.\_models import resolve\_model 。

CLI / 配置：可与 OPENROUTER\_MIN\_VERSION check\_openrouter\_version 共享同⼀版本底线（模块注释中提及 CLI config.py ）。

## 7. 依赖

langchain.chat\_models.init\_chat\_model

langchain\_core.language\_models.BaseChatModel

packaging.version.Version （版本⽐较）

importlib.metadata.version / PackageNotFoundError （OpenRouter 包检测）

## 源码路径

. 本章分析⽬录： libs/cli/deepagents\_cli/

包配置与⼊⼝声明： libs/cli/pyproject.toml

## 包与安装

PyPI 包名： deepagents-cli （⻅ libs/cli/pyproject.toml 中 \[project].name

安装： pip install deepagents-cli 。

控制台脚本（ \[project.scripts] ）：

. deepagents deepagents\_cli:cli\_main deepagents-cli deepagents\_cli:cli\_main

⼆者指向同⼀⼊⼝，便于⽤户习惯不同命令名。

设计取舍：双⼊⼝名称降低迁移成本；实际逻辑集中在 cli\_main ，避免重复实现。

核心模块职责

<table><tr><td>模块</td><td>路径</td><td>职责概要</td></tr><tr><td>入口</td><td>deepagents_cli/main.py</td><td>cli_main():参数解析、模式分发(交互TUI、无头、ACP、skills子命令等)</td></tr><tr><td>TUI应用</td><td>deepagents_cli/app.py</td><td>基于Textual的终端UI、会话与消息流</td></tr><tr><td>Agent构建</td><td>deepagents_cli/agent.py</td><td>组装中间件、后端、工具,调用create_deep_agent(约第1202行)</td></tr><tr><td>配置</td><td>deepagents_cli/config.py</td><td>Settings 数据类、from_environment()、create_model()、ModelResult等</td></tr><tr><td>服务端生命周期</td><td>deepagents_cli/server.py</td><td>启动/停止LangGraph开发服务器、生成langgraph.json等</td></tr><tr><td>服务端图</td><td>deepagents_cli/server_graph.py</td><td>供 langgraph dev 加载的图入口;与ServerConfig 环境变量约定对齐</td></tr></table>

模块关系（简图）：

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/02b3528e-b243-4cb0-b036-faa38c49ff02/54e13c8bde878312cfed58b3bf7df859f274d94cfd41e24697ba8b0629228189.jpg)

## 调用链与启动路径

## 典型交互路径可概括为：

cli\_main() （ main.py ）被 console script 调⽤。

parse\_args() 解析命令⾏；部分快速路径（如 -version ）在重依赖导⼊前返回。

1. 在需要完整配置的路径上，通过 deepagents\_cli.config 的 settingsSettings.from\_environment() 拉取环境与⽂件配置。
2. agent.py 中逻辑构造模型、中间件、后端（含本地/沙箱分⽀），最终调⽤create\_deep\_agent( .) （SDK）得到可执⾏图/代理。
3. 交互模式由 app.py 中的 Textual 应⽤承载会话；⽆头或服务模式⾛ non\_interactive.py 、server\_manager server.py 等分⽀。

设计取舍： main.py 在 parse\_args 之后再导⼊ console / settings ，使 -help 不必承担完整配置引导成本（⻅ cli\_main 内注释）。

## __init__.py 与延迟导入

deepagents\_cli/ \_init \_.py 通过 \_getattr \_ 在⾸次访问 cli\_main 时才执⾏ fromdeepagents\_cli.main import cli\_main 。

⽬的：避免在仅引⽤⼦模块（如 config widgets ）时加载 main.py 及其 argparse、信号处理等启动栈，从⽽优化冷启动与测试导⼊性能。

## 配置体系： Settings 与环境

config.py 中的 Settings （ @dataclass ）集中描述 API Key、模型、项⽬根、Shell ⽩名单、技能⽬录扩展等。

Settings.from\_environment(cls, \*, start\_path= .) ： 从环境检测并构造实例；与⼀次性bootstrap（dotenv、LangSmith 等）配合使⽤。

create\_model( .) 与 ModelResult ：将模型规格解析为可调⽤模型实例并携带元数据（如profile、标签来源），供 agent 构建与中间件使⽤。

## 环境变量前缀 DEEPAGENTS\_CLI\_

规范登记在 deepagents\_cli/_env\_vars.py ：凡 CLI 读取且以 DEEPAGENTS\_CLI_ 开头的变量应在此定义常量，并有漂移检测测试约束裸字符串使⽤。

示例语义（⾮穷举）：

. DEEPAGENTS\_CLI\_LANGSMITH\_PROJECT ：覆盖代理轨迹所⽤的 LangSmith 项⽬名。

. DEEPAGENTS\_CLI\_SHELL\_ALLOW\_LIST ：本地模式下 Shell 命令⽩名单相关配置。

. DEEPAGENTS\_CLI\_EXTRA\_SKILLS\_DIRS ：技能路径容器的额外允许根⽬录。

另有 resolve\_env\_var 机制：对第三⽅ API Key 等⽀持 DEEPAGENTS\_CLI\_{NAME} 优先于{NAME} 的覆盖策略（详⻅ \_env\_vars.py ⽂档字符串）。

## TOML： \~/.deepagents/config.toml

⽤于持久化⽤户级配置（如模型 profile、 \[skills].extra\_allowed\_dirs 等），与命令⾏、环境变量按⽂档约定合并优先级。

## dotenv

config.py 在 bootstrap 阶段加载项⽬⽬录与全局路径下的 .env （ override=False ，shell 已导出变量优先）。

## LangSmith 项⽬分离

Bootstrap 可将 LANGSMITH\_PROJECT 临时改为代理专⽤项⽬（来⾃

DEEPAGENTS\_CLI\_LANGSMITH\_PROJECT ），同时保留⽤户原始项⽬名供⼦ Shell/⽤户代码追踪使⽤（⻅ cli\_main 与 Settings 字段 user\_langchain\_project /deepagents\_langchain\_project ）。

## 无头模式（非交互）

deepagents\_cli/non\_interactive.py 提供 run\_non\_interactive 单次任务、流式输出、通过 LangGraph ⼦进程与远程客户端协作；⽀持 -quiet 将控制台噪声与标准输出分离，以及 -shell-allow-list 控制⾮交互场景下的 Shell 策略。

设计取舍：⽆头路径与 TUI 解耦，便于 CI、脚本与⾃动化流⽔线复⽤同⼀ agent 构建逻辑。

## 网络搜索集成

依赖 Tavily（ TAVILY\_API\_KEY 等）； Settings 暴露 has\_tavily 等能⼒位。⼯具层在deepagents\_cli/tools.py （如 web\_search ）与 server\_graph.py 中按配置条件挂载，使服务端图与本地逻辑⾏为⼀致。

## 服务端模式概要

server.py ：管理 langgraph dev ⼦进程、健康检查、端⼝与配置落盘。

server\_graph.py ：模块级 make\_graph() ，通过 ServerConfig.from\_env() 与 CLI 侧ServerConfig.to\_env() 共享 schema，保证⽗⼦进程配置⼀致。

## 小结

deepagents-cli 以 cli\_main 为单⼀事实⼊⼝，⽤延迟导⼊与分阶段加载控制启动成本；Settings + TOML + dotenv + DEEPAGENTS\_CLI\_\* 形成分层配置； agent.py 在本地与远程沙箱分⽀上收敛到 SDK 的 create\_deep\_agent ； server.py server\_graph.py 将同⼀套

agent 能⼒暴露为可托管的远程图。以上设计使「终端交互、脚本⽆头、LangGraph 服务」共享核⼼构建路径，⼜各⾃优化边界⾏为。

## 源码路径

. 本章重点⽬录： libs/cli/deepagents\_cli/integrations/

关联⽂件：

deepagents\_cli/integrations/sandbox\_factory.py

deepagents\_cli/integrations/sandbox\_provider.py

deepagents\_cli/configurable\_model.py

. deepagents\_cli/agent.py （后端组合、CLI 专属中间件）

可选依赖声明： libs/cli/pyproject.toml 中 \[project.optional-dependencies]（ daytona modal runloop agentcore 等）

## 沙箱工厂： sandbox\_factory.py

create\_sandbox(provider, .) 是统⼀上下⽂管理⼊⼝：按 provider 名称 解析具体SandboxProvider ，创建或连接沙箱，可选执⾏⽤户 setup 脚本（⽀持 ${VAR} 展开），并在退出时按是否「本次新建」决定是否清理。

⽀持的 provider 类型（与代码中映射⼀致，实际可⽤性取决于可选依赖是否安装）包括但不限于：

daytona → 动态导⼊ langchain\_daytona （包名 langchain-daytona ）

. modal → langchain\_modal （ langchain-modal ）

runloop → langchain\_runloop （ langchain-runloop ）

agentcore → langchain\_agentcore\_codeinterpreter

. 另有 langsmith 等路径⽤于特定托管场景

\_get\_provider 将字符串名称映射到 (模块名, ⼯⼚属性) ，在缺少依赖时给出可读的安装提示。

设计取舍：

⼯⼚ + Provider 抽象：CLI 与具体云沙箱 SDK 解耦，新增供应商时主要扩展映射与可选依赖组。

延迟 import：仅在⽤户选择对应后端时才加载重依赖，缩短默认本地模式的启动时间。

## ConfigurableModelMiddleware ： configurable\_model.py

该类实现 运⾏时模型切换：在 LangGraph 运⾏时上下⽂中注⼊ CLIContext ⻛格的 modelmodel\_params 时，中间件在 ModelRequest 链上调⽤ create\_model 解析新实例并request.override() 。

跨⼚商切换时剥离 Anthropic 专属字段（如 cache\_control ），并同步修补系统提示中的模型身份段落，避免残留不兼容参数。

与 CLI 的关系：配合 TUI 中的 /model 等路径，使⽤户⽆需重编译图即可更换 LLM，同时保持与config.create\_model 单⼀解析⼊⼝⼀致。

## 模块关系：

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/02b3528e-b243-4cb0-b036-faa38c49ff02/00edbc5956b21e8db242c34a8951c36d469c07b1c343e0ce2647b11ec54c57cf.jpg)

## CompositeBackend 在 CLI 中的用法： agent.py

在 本地模式（ sandbox is None ）下，CLI 在默认⼯作区后端之外，再挂接两个 虚拟

FilesystemBackend 分区：

前缀 /large\_tool\_results/ ：⼤型⼯具输出落盘，避免污染⽤户⼯作⽬录。

前缀 /conversation\_history/ ：会话历史相关 offload，与摘要等中间件协同。

⼆者通过 CompositeBackend(default= ., routes={ .}) 做 路径前缀路由；远程沙箱模式下通常 routes={} ，由沙箱后端统⼀承载。

说明：此处「会话/⼤结果」后端在实现上是 带 virtual\_mode 的 FilesystemBackend 临时⽬录，⽽⾮名称上的 StateBackend ；语义上仍属于「按路径前缀隔离存储」的组合后端模式。

设计取舍：

默认后端仍是 LocalShellBackend 或 FilesystemBackend （视是否启⽤ Shell），复合路由只解决 体量与历史 的隔离。

沙箱模式简化路由，避免与远程⽂件语义冲突。

## CLI 在 SDK 中间件栈之上的扩展

agent.py 在调⽤ create\_deep\_agent 前组装的 agent\_middleware 典型包含（按配置开关）：

MemoryMiddleware ：⽤户/项⽬ AGENTS.md 等记忆源。

. SkillsMiddleware ：多路径技能发现（内置、⽤户、项⽬等）。

. LocalContextMiddleware ：可执⾏后端上的 git/⽬录树等本地上下⽂。

ShellAllowListMiddleware ：在 restrictive shell allow list 激活时限制 Shell ⼯具可执⾏命令集合；与 interrupt\_on 策略联动（⽩名单模式下以⼯具错误消息拒绝⾮法命令，保持单次LangSmith trace 连续）。

create\_summarization\_tool\_middleware ：与 composite\_backend 绑定，服务上下⽂压缩与 offload。

ConfigurableModelMiddleware ：运⾏时换模。

. 以及 HITL、询问⽤户、⼦代理等 CLI 场景所需中间件。

设计取舍：在 SDK 默认能⼒之上，CLI 聚焦 终端安全（Shell）、上下⽂体积 与 交互式模型切换，⽽不重复实现核⼼ agent 图逻辑。

## 本地模式下的 Shell 安全：允许列表

环境常量 DEEPAGENTS\_CLI\_SHELL\_ALLOW\_LIST （⻅ \_env\_vars.py ）与设置中的解析结果，⽤于定义 ⾮交互/受限模式 下允许的 Shell 命令集合（如 recommended 、 all 或显式列表）。

ShellAllowListMiddleware 在 agent 管道内执⾏策略，disallowed 命令以 ToolMessage 错误形式返回，⽽⾮依赖额外⼈机轮次。

设计取舍：将策略放在中间件层，使 策略与 UI（是否 auto-approve） 可组合，且 trace ⾏为可预测。

## 与 sandbox\_provider.py 的关系

SandboxProvider 协议封装 get\_or\_create 等⽣命周期； sandbox\_factory 负责脚本执⾏、⼯作⽬录映射（如各 provider 默认 cwd）、错误消息与 Rich 控制台输出。

## 小结

integrations/ 将 Daytona / Modal / Runloop / AgentCore 等伙伴包收敛为统⼀create\_sandbox ⼯⼚； configurable\_model.py 把 动态选模 做成标准中间件； agent.py ⽤CompositeBackend 做 ⼤结果与对话历史的路径隔离，并叠加 Shell ⽩名单 等 CLI 专属中间件。

整体上，CLI 在复⽤ deepagents SDK 核⼼的同时，把 远程执⾏环境 与 终端安全/上下⽂治理 固化在集成层。

## 源码路径

内置技能资源： libs/cli/deepagents\_cli/built\_in\_skills/

技能⼦命令与加载： libs/cli/deepagents\_cli/skills/ （含 commands.py load.py 、invocation.py 等）

Slash 命令注册： libs/cli/deepagents\_cli/command\_registry.py

终端组件： libs/cli/deepagents\_cli/widgets/ （如 chat\_input.py messages.py ）

Agent 侧挂载： libs/cli/deepagents\_cli/agent.py （ SkillsMiddleware ）

⼊⼝ wiring： libs/cli/deepagents\_cli/main.py

## 内置技能： built\_in\_skills/

⽬录内随 CLI 分发 预打包技能（每个技能通常含 SKILL.md 及可选 scripts/ ）。例如：

. remember ：与会话记忆、技能更新相关的引导内容。

. skill-creator ：创建新技能的规范与辅助脚本（如 init\_skill.py 、quick\_validate.py ）。

设计取舍：内置技能作为 只读模板与规范源，保证离线可⽤与版本⼀致性；⽤户扩展仍落在⽤户/项⽬标准⽬录。

## 技能模块： skills/

setup\_skills\_parser 与 execute\_skills\_command（ skills/commands.py ）

setup\_skills\_parser ：向主 argparse 树注册 deepagents skills ⼦命令（ listcreate / info / delete 等），统⼀ CLI 参数与校验逻辑。

execute\_skills\_command ：根据解析后的 argparse.Namespace 执⾏对应⼦命令；在main.py 的技能分⽀中调⽤。

skills/ \_init \_.py 导出上述符号，便于 main 延迟导⼊。

与 main.py 的关系：

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/02b3528e-b243-4cb0-b036-faa38c49ff02/a1bde61626217929e1c59e1625dcefb28ac28a456824991c6c41859294f13895.jpg)

## 加载与 SDK 集成： load.py invocation.py

load.py ：扩展元数据、路径安全（与 Settings 中 extra\_allowed\_dirs 协同）等，为 发现与读取 SKILL.md 提供 CLI 侧能⼒；底层与deepagents.middleware.skills.SkillsMiddleware 的约定对⻬。

invocation.py ：处理运⾏期技能调⽤相关逻辑（与消息、⼯具展示配合）。

设计取舍：CLI 负责 ⽂件系统布局、路径校验与 UX； SkillsMiddleware 负责 在 agent 运⾏时将技能注⼊为模型可⻅能⼒

## SkillsMiddleware 与技能发现： agent.py

启⽤技能时， agent.py 按 优先级从低到⾼ 拼接 sources 列表，通常包括：

1. 内置技能⽬录 settings.get\_built\_in\_skills\_dir()
2. ⽤户 \~/.deepagents / \~/.agents 下技能⽬录
3. 项⽬下 .deepagents / .agents （若存在）
4. 实验性 Claude Code 技能⽬录（若存在）

SkillsMiddleware 使⽤ FilesystemBackend 作为后端， sources 为上述路径列表，从⽽在create\_deep\_agent 之前完成与 SDK 的对接。

模块关系：

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/02b3528e-b243-4cb0-b036-faa38c49ff02/0066846cf42d50c8592e6820e1c06f4c93c6de22595dd46cd115612592fec659.jpg)

## Slash 命令注册： command\_registry.py

COMMANDS 为元组，元素为 SlashCommand 数据类（ name description bypass\_tieraliases hidden\_keywords 等）。

BypassTier 枚举描述命令在 UI 忙态/队列 下是否可插队执⾏，例如：

QUEUED ：需排队。

IMMEDIATE\_UI ：⽴即打开界⾯（如模型选择），重活可延后。

SIDE\_EFFECT\_FREE ：轻量侧效可⽴即执⾏。

设计取舍：单⼀注册表⽣成⾃动补全与 bypass 元数据，避免在多个⽂件中硬编码命令字符串导致漂移。

## 与 Slash 集成的 Widget： widgets/

chat\_input.py

. 基于 Textual 的 TextArea 等组件实现聊天输⼊。

集成 SlashCommandController （⻅ widgets/autocomplete.py ）与 SLASH\_COMMANDS ，在输⼊ / 时提供 模糊匹配、描述搜索、别名。

绑定 HistoryManager （ widgets/history.py ）持久化命令历史（默认\~/.deepagents/history.jsonl ）。

messages.py

负责 消息列表渲染、⼯具调⽤展示、流式更新等与对话主视图相关的 UI（与message\_store.py 、 tool\_renderers.py 等协同）。

设计取舍：输⼊与展示分离，便于单独测试⾃动补全与消息管线；Slash ⾏为与command\_registry 共享数据源。

## 应用层分发： app.py

Textual 应⽤在 ChatInput 提交⾏中识别 /command 形式，按注册表 路由到具体处理器（部分技能相关命令带参数，如⽂档中的 /skill: . 交互模式）。

设计取舍：Slash 层是 纯 UI 侧快捷⽅式；真正 技能能⼒ 仍由 SkillsMiddleware + 模型 在agent 内消费 SKILL.md

与 SDK SkillsMiddleware 的衔接

<table><tr><td>层次</td><td>职责</td></tr><tr><td>CLI skills/</td><td>子命令管理、磁盘布局、名称校验、路径 containment、用户文档与错误信息</td></tr><tr><td>CLI agent.py</td><td>组装 sources 列表并实例化 SkillsMiddleware</td></tr><tr><td>SDK</td><td>解析 SKILL.md 、向 agent 暴露技能工具与提示注入</td></tr></table>

## 小结

```txt
built_in_skills/ 提供 版本化、可复现 的起步技能；skills/commands.py 通过
setup_skills_parser / execute_skills_command 把技能管理纳入主 CLI；
command_registry.py 统一 Slash 命令元数据与队列策略； widgets/chat_input 与
messages 在 Textual 中落地 输入补全与消息视图；agent.py 将多源目录交给 SkillsMiddleware，与 create_deep_agent 形成闭环。整体上，CLI 在「文件与 UX」层扩展 SDK 的「运行时技能」能力，并保持单一数据源以避免命令名与描述不一致。
```

# 第 17 章：评估体系架构总览

## 主要源码路径

libs/evals/tests/evals/utils.py

. libs/evals/tests/evals/conftest.py

. libs/evals/deepagents\_evals/categories.json

本章说明 deepagents 项⽬在 libs/evals/ 下的评估架构：如何⽤轨迹数据表示⼀次智能体运⾏，如何⽤「成功断⾔」与「效率断⾔」两层模型区分「对错」与「形态」，以及 pytest 与LangSmith 如何接⼊。

## 1. 评估代码在仓库中的位置

可执⾏评估逻辑集中在 libs/evals/ ：测试与⼯具函数位于 tests/evals/ ，分类与雷达图等共享配置位于 deepagents\_evals/ 。理解评估体系应优先阅读 utils.py （轨迹、断⾔、run\_agent ）与 conftest.py （环境⻔禁与 CLI）。

## 2. 两层断言模型

评估框架将断⾔分为两类，职责清晰分离。

## 2.1 成功断⾔（Success Assertions， .success(...) ）

语义：正确性检查；任⼀失败则 硬性失败 当前测试（ pytest.fail ）。

典型能⼒：最终回复是否包含⼦串、⽂件内容是否等于预期、 LLMJudge 是否全部准则通过等。

⼯⼚函数示例（定义于 utils.py ）： final\_text\_contains file\_equals 等，均返回SuccessAssertion 的⼦类实例。

## 2.2 效率断⾔（Efficiency Assertions， .expect(...) ）

语义：对轨迹「形状」的期望（步数、⼯具调⽤次数、特定⼯具调⽤是否出现等）。

⾏为：通过 LangSmith log\_feedback 记录；不会导致测试失败（⻅ \_assert\_expectations中对 \_success 与 \_expectations 的分⽀处理）。

. 实现基类： EfficiencyAssertion ；常⻅具体类包括 AgentSteps ToolCallRequestsToolCall 。

设计取舍：把「必须做对」与「希望省步数 / ⼯具调⽤」拆开，避免模型因探索性多⾛⼀步就整例标红，同时仍能在报表与 LangSmith 中观察效率偏差。

## 3. 核心类型 （ utils.py ）

## 3.1 AgentStep （ dataclass ）

字段： index （从 1 起计）、 action （ AIMessage ）、 observations（ list\[ToolMessage] ）。

含义：智能体在⼀个「回合」内的决策及其后随的观测（⼯具返回）。

## 3.2 AgentTrajectory （ dataclass ）

. 字段： steps 、 files （路径到⽂件内容的映射）。

. answer 属性：取最后⼀步 AIMessage 的⽂本，便于断⾔最终对外回复。

pretty() ⽣成⼈类可读的轨迹摘要（每步的⼯具调⽤与⽂本预览），⽤于失败信息与 LLM 评判上下⽂。

## 3.3 SuccessAssertion

正确性断⾔的抽象基类：⼦类实现 check(trajectory) > bool 与describe\_failure(trajectory) > str 。

## 3.4 TrajectoryScorer

不可变 dataclass，采⽤ 建造者⻛格 链式配置：

. .success(\*SuccessAssertion) ：追加成功断⾔；

. .expect( .) ：通过关键字参数追加效率断⾔（如 agent\_steps=tool\_call\_requests= tool\_calls= 列表）。

内部以 \_success \_expectations 两个元组分别保存两类断⾔。

## 4. 入口函数 run\_agent

源码： run\_agent 定义于 utils.py 。

职责（调⽤⽅通常已⽤ create\_deep\_agent 等建好 CompiledStateGraph ）：

1. 将 query （字符串或消息列表）与可选 initial\_files 组装为 invoke 输⼊；
2. ⽣成或使⽤ thread\_id ，调⽤ agent.invoke ；
3. 通过 LangSmith 记录规范化后的 inputs / outputs （避免测试夹具噪声污染数据集示例）；
4. ⽤ \_trajectory\_from\_result 从 result\["messages"] 与 result\["files"] 构建AgentTrajectory ；
5. 若传⼊ scorer ，则执⾏ \_assert\_expectations ： 先记录效率相关 feedback，再逐项运⾏成功断⾔。

模块关系：测试⽂件构造 agent 与 TrajectoryScorer ，再调⽤ run\_agent ；pytest\_reporter 通过回调收集 EfficiencyResult ⽤于会话级指标。

## 5. 评估分类与雷达维度 （ categories.json ）

categories.json 中 categories 列出全部评估维度：

file\_operations

. retrieval

. tool\_use

memory

conversation

summarization

. unit\_test

radar\_categories 为雷达图所⽤ ⼦集：与 categories 相⽐ 不包含 unit\_test ，避免将偏SDK / 单元⾏为的⽤例与「模型能⼒」维度混在同⼀雷达上。

labels 提供各分类的短标签（如 UI 或图表轴标题）。

## 6. pytest 配置（ conftest.py ）

## 6.1 LangSmith 追踪⻔禁

pytest\_configure 要求启⽤追踪：检查 LANGSMITH\_TRACING LANGSMITH\_TRACING\_V2LANGCHAIN\_TRACING\_V2 LANGCHAIN\_TRACING 等环境变量是否为 "true" 。未启⽤则 整个会话以退出码 1 中⽌，并提示设置 API Key 与追踪开关。评估⽤例普遍配合@pytest.mark.langsmith 使⽤。

## 6.2 插件与 CLI

pytest\_plugins = \["tests.evals.pytest\_reporter"] ：挂载会话级报告与 JSON 输出（详⻅第 18 章）。

-model ：指定被测模型；省略时使⽤ deepagents.graph.get\_default\_model() 的模型名。

-eval-category ： 可重复；仅收集带对应 eval\_category 标记的⽤例；未知分类名会报错退出。

-openrouter-provider ：固定 OpenRouter 提供⽅（需 openrouter: 前缀模型名）。

## 6.3 Fixture

model\_name ：由 pytest\_generate\_tests 与 -model 参数化。

： model ：基于 model\_name 调⽤ init\_chat\_model ；对 openrouter: 模型注⼊超时等kwargs。

langsmith\_experiment\_metadata ：会话级元数据（模型、⽇期、deepagents 版本），供实验组织使⽤。

## 7. 代码示例

## 7.1组合效率期望与成功断⾔

```python
scorer = (
    TrajectoryScorer()
    .expect(agent_steps=2, tool_call_requests=1)
    .success(final_text_contains("three", case_insensitive=True))
) 
```

含义：期望 2 步、1 次⼯具调⽤请求（仅记录与指标，失败不红）；最终回复须包含 "three" （不区分⼤⼩写），否则测试失败。

## 7.2完整评估⽤例示例

```python
import pytest
from deepagents import create_deep_agent
from tests.equals.utils import (
run_agent,
TrajectoryScorer,
final_text_contains,
file_equals,
)
@pytest.mark.langsmith
@pytest.mark.eval_category("file_operations")
class TestFileOperations:
    """文件操作类评估用例。"""
```

python

```python
def test_create_and_read_file(self, model):
    """测试智能体创建并读取文件的能力。"""
    agent = create_deep_agent(model=model)

    scorer = (
    TrajectoryScorer()
    .expect(agent_steps=3, tool_call_requests=2)
    .success(
    file_equals("output.txt", "Hello, World!");
    final_text_contains("file created"),
    )
    )

    trajectory = run_agent(
    agent=agent,
    query="Create a file called output.txt with the content 'Hello, World!'", scorer=scorer,
    )

    # 可选：手动检查轨迹细节
    assert len(trajectory.steps) ≤ 5, "Too many steps"

    def test_file_edit(self, model):
    """测试智能体编辑文件的能力。"""
    agent = create_deep_agent(model=model)

    scorer = (
    TrajectoryScorer()
    .expect(agent_steps=2)
    .success(
    file.equals("config.json", '{"debug": true}),
    )
    )

    run_agent(
    agent=agent,
    query="Edit config.json to set debug to true",
    initial_files={"config.json": '{"debug": false"},
    scorer=scorer,
    )
```

7.3⾃定义断⾔定义示例

````python
from tests.equals.utils import SuccessAssertion, AgentTrajectory

class ResponseContainsCode(SuccessAssertion):
    """检查最终回复是否包含代码块。"""

    def __init__(self, language: str = "python"):
    self.language = language

    def check(self, trajectory: AgentTrajectory) → bool:
    answer = trajectory.answer
    return f"```{self.language}" in answer

    def describe_failure(self, trajectory: AgentTrajectory) → str:
    return (
    f"Expected response to contain a {self.language} code block, "
    f"but got: {trajectory.answer[:200]}..." 
    )

class FileExists(SuccessAssertion):
    """检查指定文件是否存在于轨迹终态。"""

    def __init__(self, path: str):
    self.path = path

    def check(self, trajectory: AgentTrajectory) → bool:
    return self.path in trajectory.files

    def describe_failure(self, trajectory: AgentTrajectory) → str:
    available = ", ".join(trajectory.files.keys()) or "(none)"
    return f"Expected file '{self.path}' to exist. Available files: {available}"
````

# 使⽤⾃定义断⾔

```python
scorer = (
    TrajectoryScorer()
    .success(
    ResponseContainsCode(language="python"),
    FileExists("solution.py"), 
```

```txt
) 
```

7.4效率断⾔详解

```python
from tests.equals.utils import TrajectoryScorer

# 仅记录效率指标，不影响测试结果
scorer = (
    TrajectoryScorer()
    .expect(
    agent_steps=4,    # 期望步数（容忍范围由框架定义）
    tool_call_requests=3,    # 期望工具调用次数
    tool_calls=["read_file", "write_file"],    # 期望出现的工具
    )
)

# 结合成功断言与效率断言
scorer = (
    TrajectoryScorer()
    .expect(agent_steps=5, tool_call_requests=3)
    .success(
    final_text_contains("passed"),
    file_equals("test_output.py", EXPECTED_CONTENT),
    )
)
```

## 8. 小结

<table><tr><td>组件</td><td>作用</td></tr><tr><td>AgentStep / AgentTrajectory</td><td>结构化表示一次运行的消息与文件终态</td></tr><tr><td>SuccessAssertion / EfficiencyAssertion</td><td>硬失败 vs 仅记录</td></tr><tr><td>TrajectoryScorer</td><td>统一挂载两类断言的不可变建造者</td></tr><tr><td>run_agent</td><td>invoke、轨迹构建、断言与 LangSmith 记录</td></tr><tr><td>categories.json</td><td>分类全集与雷达子集</td></tr><tr><td>conftest.py</td><td>追踪门禁、模型与分类筛选 fixture</td></tr></table>

下⼀章将说明会话结束后的报告字段、雷达图⽣成与 CI 聚合脚本如何消费这些输出。

## 第 18 章：评估报告与指标系统

## 主要源码路径

libs/evals/tests/evals/pytest\_reporter.py

libs/evals/deepagents\_evals/radar.py

. .github/scripts/aggregate\_evals.py

本章说明⼀次 pytest 评估跑完后，终端摘要、JSON 报告、核⼼指标定义、雷达图⽣成，以及GitHub Actions 中如何聚合多份 evals\_report.json

## 评估报告流程图

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/02b3528e-b243-4cb0-b036-faa38c49ff02/39fd9a7d6a923136760b21cab44f38fd2f588f5911b175706e5f9030dbd684c8.jpg)

## 1. pytest 报告插件 （ pytest\_reporter.py ）

该⽂件作为 pytest 插件注册（⻅ conftest.py 中的 pytest\_plugins ），在收集、运⾏与收尾阶段维护全局状态并写出制品。

## 1.1 会话结束后的终端摘要

pytest\_sessionfinish 中通过 terminalreporter 输出 deepagents evals summary 分隔块，包括：

. created\_at 、 sdk\_version 、 model

. 通过 / 失败 / 跳过 / 总数

聚合指标（⻅下⽂）

若存在多条 LangSmith 实验链接，单独⼀节列出（含可选 public\_url ）

## 1.2 JSON 报告路径

CLI： -evals-report-file <路径>

环境变量：若未传 CLI，默认读取 DEEPAGENTS\_EVALS\_REPORT\_FILE

写⼊内容为 排序键的 JSON（ indent=2 ），⽗⽬录不存在时会创建。该⽂件是 CI 聚合脚本的输⼊之⼀。

## 1.3 LangSmith 实验预创建

当设置环境变量 LANGSMITH\_TEST\_SUITE 时， pytest\_sessionstart 会尝试在⾸轮测试前调⽤LangSmith 内部 API（ \_start\_experiment 等）预先创建实验，并把实例注册到\_LangSmithTestSuite.\_instances ，以便后续 @test 装饰器复⽤同⼀实验，从⽽在跑测开始即可在终端打印对⽐链接（含数据集 compare?selectedSessions= URL）。

设计说明：依赖 LangSmith 私有内部 API，失败时以 stderr 警告形式降级，不阻塞整次 pytest。

## 1.4 其他钩⼦要点

pytest\_configure ：将 tests.evals.utils.\_on\_efficiency\_result 设为向\_EFFICIENCY\_RESULTS 追加回调，与 run\_agent 内的效率记录衔接。

pytest\_collection\_modifyitems ：建⽴ nodeid > eval\_category 映射，供分类正确率统计。

pytest\_runtest\_logreport ：在 when = "call" 时累加计数、时⻓，并回填最近⼀条EfficiencyResult 的 duration\_s 与 passed 。

注意：插件在 session.exitstatus = 1 时将 exitstatus 置为 0 ，以便在「有失败⽤例」时仍能完成报告写出（具体策略以仓库 CI 约定为准）。

## 2. 核心指标定义

以下字段由 pytest\_sessionfinish 组装的 payload 给出（与 JSON 报告⼀致）。

## 2.1 correctness

含义： passed / total （会话内计⼊摘要的测试调⽤总数为分⺟），保留两位⼩数。

解释：在「会话级」意义上，等价于 通过所有成功断⾔ 的⽤例⽐例（因失败⽤例由成功断⾔触发pytest.fail ）。

## 2.2 step\_ratio

计算： \_micro\_step\_ratio() 对所有提供了 期望步数 的⽤例，计算(\sum \text{actual\_steps} / \sum \text{expected\_steps})，再四舍五⼊到两位⼩数。

缺失：若没有任何⽤例带期望步数，则为 null （JSON 中省略或键为 null ，视序列化⽽定）。

## 2.3 tool\_call\_ratio

计算：与 step\_ratio 类似，对 期望⼯具调⽤次数 做微平均（总和⽐）。

## 2.4 solve\_rate

计算：对每条 EfficiencyResult ，若存在 expected\_steps 与 duration\_s ：通过则⽤expected\_steps / duration\_s （时⻓为 0 时贡献 0），失败则贡献 0；再对所有此类⽤例取算术平均，保留四位⼩数。

直觉：在「步数期望」存在时，刻画单位时间内相对期望步数的吞吐（仅作辅助指标，受模型延迟与任务难度影响）。

## 2.5 median\_duration\_s

. 含义：每次测试 call 阶段墙钟时间（秒）的 中位数，保留四位⼩数。

## 2.6 category\_scores

含义：按 eval\_category 标记汇总的 分类正确率：每个分类内 passed / (passed +failed) （跳过不计⼊该分类分⺟）。

## 3. 雷达图（ deepagents\_evals/radar.py ）

## 3.1 ModelResult

```txt
@dataclass(frozen=True)
class ModelResult:
    model: str
    scores: dict[str, float]  # 分类 → [0, 1] 正确率
```

## 3.2 generate\_radar

签名： generate\_radar(results: list\[ModelResult], \*, categories=None, title= .,output= ., figsize= .)

⾏为：使⽤ matplotlib 极坐标图，按 categories （默认 EVAL\_CATEGORIES ，来⾃categories.json 的 radar\_categories ）绘制每个模型⼀条封闭折线，径向范围为 (\[0,1])，并在点上标注百分⽐。

依赖：需安装带图表依赖的环境（⽂档与 pyproject 中常⻅说明为 uv sync -extracharts ）。

## 3.3 与分类过滤跑测的关系

命令⾏脚本 libs/evals/scripts/generate\_radar.py 在汇总结果时，若各模型 scores 中出现的分类数 少于 3，会 跳过 绘图并以退出码 0 退出（避免窄分类筛选跑测产⽣⽆意义的低维雷达）。同时会按 EVAL\_CATEGORIES 顺序排列已知轴，并排除仅属于 ALL\_CATEGORIES 但不在EVAL\_CATEGORIES 的项（如 unit\_test ）。

## 3.4 ⽣成⼊⼝

scripts/generate\_radar.py ：⽀持 -toy -summary evals\_summary.jsonresults 等数据源，输出 PNG（及可选每模型单独图）。

load\_results\_from\_summary 可从聚合后的 summary JSON 数组读取 model 与category\_scores 转为 ModelResult 列表。

## 4. CI 聚合

（ .github/scripts/aggregate\_evals.py ）

## 4.1 输⼊与输出

扫描： evals\_artifacts/\*\*/evals\_report.json （递归 glob）

写出：当前⼯作⽬录下的 evals\_summary.json ，内容为 所有报告⾏的 JSON 数组（便于多模型、多 job 合并）

## 4.2 GITHUB\_STEP\_SUMMARY

若存在环境变量 GITHUB\_STEP\_SUMMARY ，脚本将 Markdown 写⼊该⽂件，供 GitHub Actions 界⾯展示，包括：

1. Evals summary：按 provider 分组、按正确率排序的总表（ model , passed failed ,skipped , total , correctness , solve\_rate , step\_ratio tool\_call\_ratio ,

```txt
median_duration_s) 
```

1. Ranked by correctness / solve rate：另⼀排序视⻆
2. Per-category correctness：从各报告的 category\_scores 并集构建列，表头使⽤

```txt
categories.json 的 labels
```

1. 可选脚注：当部分⾏缺少效率类指标时，说明 solve\_rate / step\_ratio

```txt
tool_call_ratio 仅在有期望步数/工具调用配置的用例中才有意义
```

1. LangSmith experiments：从 experiment\_links 或退化为 experiment\_urls 渲染链接

同时相同内容 print 到 stdout，便于⽇志归档。

## 4.3 模块关系示意

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/02b3528e-b243-4cb0-b036-faa38c49ff02/68285351c9a72f246707028cc1166d226e4b7369597213bed0e4612b29fc0dba.jpg)

## 5. 设计小结

终端 + JSON 双通道：⼈机可读摘要与机器可读制品并存，CI 只做聚合不加业务逻辑。

指标分层： correctness 是会话主指标； step\_ratio / tool\_call\_ratio / solve\_rate

依赖⽤例是否声明效率期望，解释时需对照⽤例设计。

雷达图：⾯向 跨分类模型对⽐，故意排除 unit\_test ；窄跑测需依赖脚本内的「最少轴数」保

护避免误导性图表。

## 第 19 章：内置评估用例详解

## 主要源码路径

libs/evals/tests/evals/ ⽬录下各 test\_\*.py ⽂件

本章按测试⽂件梳理 内置 评估套件（不含第 20 章单独说明的外部基准与 tau2、MemoryAgentBench ⽬录）。每个⽂件均通过 @pytest.mark.eval\_category( .) 或模块级pytestmark 打上分类，供 -eval-category 筛选与 category\_scores 聚合。

## 1. test\_file\_operations.py

分类： file\_operations （多数⽤例）、 retrieval （检索相关⼦集）

## 评估焦点

⽂件类⼯具：读、写、编辑、列⽬录等典型⼯作流；并⾏读、并⾏写；在 种⼦⽂件状态 下完成任务。

检索类能⼒： grep glob 等在⼯作区中定位内容；与⽂件内容断⾔（ file\_equalsfile\_contains 等）结合，检查⼯具使⽤与最终结果是否⼀致。

设计要点：⽤ initial\_files 与 TrajectoryScorer 将「⼯具调⽤形态」与「终态⽂件 / 最终⽂本」同时约束，覆盖单⽂件与多⽂件场景。

## 2. test\_tool\_selection.py

分类： tool\_use

## 评估焦点

从 ⾃然语⾔意图 中选择 正确⼯具：直接意图、间接表述、需要多步推理才能锁定⼯具等。

使⽤ 相互独⽴的 mock ⼯具，降低外部依赖，突出「选型」⽽⾮业务 API 细节。

## 3. test\_tool\_usage\_relational.py

分类： tool\_use

## 评估焦点

多步⼯具链：后⼀步依赖前⼀步结果（例如 ⽤户 → 地理位置 → 天⽓ ⼀类依赖链）。

. 验证智能体能否在 数据依赖 下连续调⽤⼯具并整合答案。

## 4. test\_todos.py

分类： tool\_use

## 评估焦点

待办（todo）类⼯具 的使⽤：任务拆解、规划步骤、在执⾏过程中维护列表等⾏为是否符合预期。

## 5. test\_memory.py

分类： memory

## 评估焦点

· 从 AGENTS.md 等记忆⽂件中 回忆规则与⾏为指引。

· 偏好持久化、复合后端 等配置下记忆是否可读、可⽤、可影响后续⾏为。

## 6. test\_memory\_multiturn.py

分类： memory

## 评估焦点

多轮对话记忆：从对话中 隐式抽取偏好、响应显式「请记住」类指令。

瞬时信息过滤：不应⻓期记住的内容是否被正确区别对待。

## 7. test\_followup\_quality.py

分类： conversation

## 评估焦点

. 在 ⽤户请求⽋明确 时，追问（follow-up） 是否相关、有⽤。

常结合 llm\_judge （⻅第 21 章）做语义层评判，⽽⾮仅靠关键词匹配。

## 8. test\_summarization.py

分类： summarization

## 评估焦点

. 摘要中间件 是否在合适时机触发。

摘要发⽣后智能体能否 继续执⾏任务（⽽⾮「总结完就停」）。

历史卸载到⽂件系统 等⾏为是否与中间件设计⼀致。

## 9. test\_hitl.py

分类： unit\_test

## 评估焦点

Human-in-the-loop： interrupt\_on 等机制下的 ⼈⼯审批 流程。

⼦智能体场景下的 HITL、⾃定义 interrupt 配置 等变体。

说明： unit\_test 类⽤例更多验证 框架⾏为与编排，与「纯模型能⼒」雷达维度区分（⻅categories.json 中 radar\_categories ）。

## 10. test\_subagents.py

分类： unit\_test

## 评估焦点

. ⼦智能体委派：主 agent 是否在合适条件下委托⼦任务、⼦ agent 结果是否回流。

## 11. test\_system\_prompt.py

分类： unit\_test

## 评估焦点

? 智能体是否 遵循系统提示 中的约束（格式、⻆⾊、禁⽌项等）。

## 12. test\_skills.py

分类： unit\_test

## 评估焦点

从 SKILL.md 发现、读取并 应⽤技能：技能加载、按说明执⾏、与⼯具/⽂件交互的⼀致性。

## 13. 模块关系与共用模式

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/02b3528e-b243-4cb0-b036-faa38c49ff02/5e37e91a0f03504f9621f1d8ac69bf2dd8a24d5924e56895bfb8bfc4f43c97ea.jpg)

## 14. 表：文件 — 分类 — 摘要

<table><tr><td>测试文件</td><td>分类</td><td>评估侧重点</td></tr><tr><td>test_file_operations.py</td><td>file_operations, retrieval</td><td>文件工具链、并行 IO、grep/glob、种子工作区</td></tr><tr><td>test_tool_selection.py</td><td>tool_use</td><td>意图到工具的映射 (mock 工具)</td></tr><tr><td>test_tool_usage_relational.py</td><td>tool_use</td><td>多步有依赖的工具链</td></tr><tr><td>testTodos.py</td><td>tool_use</td><td>待办规划工具</td></tr><tr><td>test_memory.py</td><td>memory</td><td>AGENTS.md、偏好、复合后端</td></tr><tr><td>test_memory_multiturn.py</td><td>memory</td><td>多轮隐式/显式记忆、过滤</td></tr><tr><td>test_followup_quality.py</td><td>conversation</td><td>欠指定场景下的追问质量(常LLM 评判)</td></tr><tr><td>test_summarization.py</td><td>summarization</td><td>摘要触发、摘要后继续任务、历史卸载</td></tr><tr><td>test_hitl.py</td><td>unit_test</td><td>中断与审批、子 agent HITL</td></tr><tr><td>test_subagents.py</td><td>unit_test</td><td>子智能体委派</td></tr><tr><td>test_system_prompt.py</td><td>unit_test</td><td>系统提示遵循</td></tr><tr><td>test_skills.py</td><td>unit_test</td><td>SKILL.md 发现与应用</td></tr></table>

外部基准（FRAMES、Nexus、BFCL v3）、MemoryAgentBench、tau2 航空域等多在独⽴模块或test\_external\_benchmarks.py 中接⼊，⻅第 20 章。

# 第 20 章：外部基准测试集成

## 主要源码路径

libs/evals/tests/evals/external\_benchmarks.py

libs/evals/tests/evals/test\_external\_benchmarks.py

libs/evals/tests/evals/tau2\_airline/

libs/evals/tests/evals/memory\_agent\_bench/

. 精选数据： libs/evals/tests/evals/data/benchmark\_samples/ （ frames\_final.json ,nexus\_final.json , bfcl\_v3\_final.json ）

本章说明 deepagents 评估库如何集成 外部学术与⾏业基准 的⼦集：多跳检索、嵌套函数组合、多轮有状态⼯具调⽤、⻓上下⽂记忆评测，以及源⾃ τ-bench 的航空客服多轮对话任务。

## 1. FRAMES、Nexus、BFCL v3 （ external\_benchmarks.py

实现与数据装载集中在 external\_benchmarks.py ；pytest ⽤例在test\_external\_benchmarks.py 中按分类标记（如 retrieval 、 tool\_use ）。

## 1.1 FRAMES

性质：多跳检索 类基准⼦集。

能⼒：多步 ⽹⻚/检索模拟搜索 与 信息综合；智能体需在多源信息间跳转并给出合成答案。

数据：从 data/benchmark\_samples/frames\_final.json 加载，按预定义 ID 过滤⼦集（ \_FRAMES\_IDS ）。

## 1.2 Nexus

. 性质：嵌套函数组合 类基准。

能⼒：考察 复杂⼯具调⽤链、组合调⽤与参数传递，⽽⾮单次简单调⽤。

数据： nexus\_final.json ，按 \_NEXUS\_IDS 选取固定案例。

## 1.3 BFCL v3

性质：多轮、有状态 ⼯具调⽤（Berkeley Function Calling Leaderboard ⼀脉）。

实现：Python API 实现位于 libs/evals/tests/evals/data/bfcl\_apis/ （如ticket\_api travel\_booking vehicle\_control trading\_bot message\_api 、long\_context 等），作为 StructuredTool 暴露给 agent。

评分：结合 状态⽐较 与最终输出是否符合预期（具体断⾔与 TrajectoryScorer 在external\_benchmarks.py 中组织）。

## 1.4 精选 JSON 与元数据

\_load\_final 从 \*\_final.json 读取 tasks 或 cases \_external\_eval\_metadata 等为LangSmith 记录 case\_id 、 origin\_benchmark 等字段，便于追溯来源。

## 2. MemoryAgentBench（ICLR 2026）

⽬录： libs/evals/tests/evals/memory\_agent\_bench/

## 2.1 ⽬标

. ⻓上下⽂记忆 与 分块上下⽂ 上的回忆、问答。

仓库集成 Conflict Resolution 与 Test-Time Learning 等拆分⼦集所需⼦集（以源码注释为准）。

## 2.2 eval\_utils.py

提供轻量评分⼯具，便于与字符串答案对⽐：

. normalize\_answer ：⼩写、去标点、去冠词、折叠空⽩。

substring\_match ：规范化后 ground truth 是否为 prediction 的⼦串。

substring\_match\_any ：多个可接受答案任⼀命中即通过。

## 2.3 test\_memory\_agent\_bench.py

分类： memory （模块级 pytestmark ）。

将 MemoryAgentBench 协议转为本仓库的 run\_agent + 断⾔ 流程，与内置 memory ⽤例共享同⼀分类聚合。

## 3. tau2-bench 航空域（ tau2\_airline/ ）

## 3.1 来源与许可

衍⽣⾃ sierra-research/tau-bench（MIT License）；⽬录内保留 LICENSE 与引⽤说明。

场景：多轮 智能体—⽤户对话，模拟航空客服与旅客交互。

## 3.2核⼼⽂件职责

<table><tr><td>文件</td><td>职责</td></tr><tr><td>evaluation.py</td><td>TaskReward:reward为DB匹配得分与communicate子串覆盖率的乘积;含EpisodeScore等结构</td></tr><tr><td>runner.py</td><td>多轮对话执行器(消息循环、工具调用与状态推进)</td></tr><tr><td>user_sim.py</td><td>模拟用户行为与回复</td></tr><tr><td>domain.py</td><td>航空域数据模型、工具创建、FlightDB等</td></tr><tr><td>data/tasks.json</td><td>任务定义(期望动作、communicate信息等)</td></tr><tr><td>test_tau2_airline.py</td><td>pytest入口;分类为conversation</td></tr></table>

## 3.3评分逻辑（概念）

DB check：在⼲净数据库上重放期望动作，与对话结束后的实际库状态⽐对。

Communicate check：期望告知⽤户的信息是否以 ⼦串 等形式出现在智能体消息中。

Action check：期望⼯具调⽤是否发⽣（偏诊断、信息性）。

整体 reward 与 τ² 策略对⻬：DB 与 communicate 的乘积 体现「既要做对后台状态，⼜要对⽤户说清楚」。

## 4. 精选基准数据目录

路径： libs/evals/tests/evals/data/benchmark\_samples/

<table><tr><td>文件</td><td>用途</td></tr><tr><td>frames_final.json</td><td>FRAMES 子集</td></tr><tr><td>nexus_final.json</td><td>Nexus 子集</td></tr><tr><td>bfcl_v3_final.json</td><td>BFCL v3 子集</td></tr></table>

这些⽂件与 external\_benchmarks.py 中的 ID ⽩名单共同定义 固定可复现 的评估⼦集，避免整库全量运⾏成本过⾼。

## 5. 与内置评估的衔接

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/02b3528e-b243-4cb0-b036-faa38c49ff02/846a7b9a91962d8bb9dfb02a7ee3b1f3d4d3e396c474d3d960cd642408a5163f.jpg)

外部基准 不替换 utils.py 中的轨迹模型：仍以 LangGraph invoke 结果构建

AgentTrajectory ，成功断⾔决定成败；tau2 等则在⾃身 evaluation.py 中计算 任务级reward，再与 pytest 的通过/失败策略结合（⻅ test\_tau2\_airline.py 具体断⾔）。

## 6. 小结

FRAMES / Nexus / BFCL v3：统⼀在 external\_benchmarks.py 装配 agent 与评分，数据来⾃ benchmark\_samples 与 bfcl\_apis 。

MemoryAgentBench： eval\_utils 提供规范化匹配；⽤例归类 memory 。

tau2 航空：完整对话环与 DB × communicate 乘积奖励；归类 conversation ，代码与数据在tau2\_airline/ ⾃洽。

若需扩展新基准，建议优先复⽤ run\_agent 、元数据字典与 eval\_category 标记，以便雷达与CI 聚合⾃动收录。

# 第 21 章：LLM-as-Judge 评估模式

## 主要源码路径

```txt
- libs/evals/tests/evals/llm_judge.py 
```

本章说明 deepagents 如何将 LLM 作为评判器（LLM-as-Judge） 接⼊现有的

```txt
SuccessAssertion / TrajectoryScorer 体系：依赖 openevals 的 create_llm_as_judge，按条准则独立打分，全部通过则断言成功。
```

## 1. 设计动机

部分评估⽬标难以⽤ ⼦串包含 或 ⽂件字节级相等 表达，例如：

. 语义是否正确、是否答⾮所问；

. 语⽓是否⾃然、是否符合⻆⾊；

是否覆盖要点、推理是否完整。

此类 细粒度、主观或组合性 标准适合交给 独⽴评判模型 按提示词判定，同时仍作为 成功断⾔ 的⼀部分：评判不通过则 整例测试失败，与 final\_text\_contains 等⾏为⼀致。

## 2. LLMJudge 类

继承： SuccessAssertion （定义⻅ tests/evals/utils.py ）。

核⼼依赖： openevals.llm.create\_llm\_as\_judge

字段要点：

. criteria ：若⼲条⼈类可读的准则字符串；每条单独调⽤ 评判器。

judge\_model ：评判⽤模型，默认 claude-sonnet-4-6 （模块常量\_DEFAULT\_JUDGE\_MODEL ）。

include\_tool\_calls ：

False （默认）：评判器只看到各步 ⽂本回复，适合评判「说了什么」。

. True ：将 trajectory.pretty() 全⽂（含⼯具名与参数）送⼊提示，适合准则涉及 是否执⾏了某⼯具/写⼊了⽂件 等 ⾏为证据。

## 2.1 check 与 describe\_failure

. check ：对每条 criterion 运⾏ evaluator(outputs= ., criterion= .) ，要求返回 dict且含 score ；所有 score 为真才返回 True 。

describe\_failure ：汇总未通过准则的序号与 comment ，便于 pytest 失败信息定位。

## 2.2 提示模板

模块内两套 prompt（ \_RESPONSES\_PROMPT \_TRAJECTORY\_PROMPT ）约束评判者为 严格评分助⼿，明确输⼊为 单条准则 + 序列化后的智能体输出或轨迹。

## 2.3 LangSmith 反馈

评分结束后尝试 t.log\_feedback ，键 llm\_judge\_all\_passed ，⽤分数与 comment 记录「⼏条准则通过」，便于在 LangSmith 上过滤分析。⽇志失败时以 warnings.warn 降级，不掩盖 断⾔结果。

## 2.4 内部缓存

使⽤ \_last\_results 在 check 与 describe\_failure 之间复⽤ 同⼀次评判调⽤，避免重复计费。

## 3. 工厂函数 llm\_judge

⾯向⽤例作者的 便捷⼊⼝：

```python
def llm_judge(
    *criteria: str,
    judge_model: str = _DEFAULT_JUDGE_MODEL,
    include_tool_calls: bool = False, 
```

python

```txt
) → LLMJudge:
... 
```

返回配置好的 LLMJudge ，可直接传⼊ TrajectoryScorer.success( .) 。

## 4. 与 TrajectoryScorer 组合示例

```python
from tests.evals.llm_judge import llm_judge

scorer = TrajectoryScorer().success(
    llm_judge(
    "The answer mentions the capital of France is Paris.",
    "The tone is conversational, not robotic.",
    )
) 
```

python

含义：两条准则 都必须 被评判模型判为通过，否则 run\_agent 末尾的成功断⾔阶段触发pytest.fail 。

若准则需要引⽤⼯具调⽤证据，例如「必须调⽤过 edit\_file 」，应设include\_tool\_calls=True 。

## 5. 何时用 LLM Judge，何时用子串匹配

<table><tr><td>方式</td><td>适用场景</td><td>优点</td><td>注意</td></tr><tr><td>子串 / 文件断言</td><td>事实性短答案、固定短语、精确文件内容</td><td>成本低、可复现、无二次模型方差</td><td>无法覆盖语义等价表述</td></tr><tr><td>LLMJudge</td><td>语义正确性、风格、完整性、多条件综合</td><td>灵活,接近人类验收标准</td><td>成本与延迟更高,需固定judge_model 以便横向对比</td></tr></table>

实践建议：能⽤确定性断⾔处尽量不⽤ Judge；Judge 准则宜 单条可判定、表述⽆歧义，避免⼀条准则内堆砌过多要求，以便失败时 comment 可定位。

## 6. 模块关系

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/02b3528e-b243-4cb0-b036-faa38c49ff02/9eab6e212e96ecfa7ea1aa29b8683c4dbfc2e00abfee1cca600e4909fa689e58.jpg)

```txt
run_agent 在 _assert_expectations 中按顺序执行 scorer._success ; LLMJudge 与其他 SuccessAssertion 子类无特殊分支，统一走 check / describe_failure 协议。
```

## 7. 小结

LLMJudge 是 openevals 与 deepagents 评估框架的 薄适配层，将 LLM 评判结果映射为硬性成功/失败。

llm\_judge(\*criteria) 提供与 final\_text\_contains ⼀致的⼯⼚⻛格 API。

通过 include\_tool\_calls 在「仅评⽂本」与「评完整轨迹」之间切换，与准则是否依赖 ⼯具层证据 对⻬。

## 第 22 章：Harbor 框架集成

## 主要参考源码路径

libs/evals/deepagents\_harbor/ （Harbor 适配与 LangSmith 集成核⼼）

libs/evals/deepagents\_harbor/deepagents\_wrapper.py

libs/evals/deepagents\_harbor/backend.py

libs/evals/deepagents\_harbor/langsmith.py

libs/evals/deepagents\_harbor/metadata.py

libs/evals/README.md （Harbor / Terminal Bench 总述）

## 1. Harbor 是什么

Harbor 是⼀套 ⾯向智能体评测的编排框架，⽬标是在⾼难度基准上 以统⼀⽅式拉起沙箱、运⾏智能体、打分并落盘轨迹，从⽽降低「⾃建评测流⽔线」的⼯程量。

典型能⼒包括：

<table><tr><td>能力</td><td>说明</td></tr><tr><td>沙箱环境</td><td>支持Docker、Modal、Daytona、E2B、Runloop等多种后端,任务在隔离环境中执行</td></tr><tr><td>自动测试与校验</td><td>基准自带验证器(verifier),Harbor负责调度执行并汇总结果</td></tr><tr><td>奖励分数</td><td>通常将测试通过率映射为0.0~1.0的标量奖励(harbor_reward等下游消费)</td></tr><tr><td>轨迹记录(ATIF)</td><td>轨迹以Agent Trajectory Interchange Format(ATIF)序列化,便于跨工具分析与可视化(参见Harbor官方trajectory文档)</td></tr></table>

Deep Agents 在 libs/evals/deepagents\_harbor/ 中提供 Harbor 侧的 Agent 实现 与 沙箱后端桥接，使同⼀套 Deep Agent（CLI 或 SDK 模式）可在 Harbor 选定的环境中复⽤。

## 2. DeepAgentsWrapper ：Harbor 入口智能体

⽂件： deepagents\_harbor/deepagents\_wrapper.py

类： DeepAgentsWrapper(BaseAgent)

## 2.1 职责

. 继承 Harbor 的 BaseAgent ，在 run(instruction, environment, context) 中完成⼀次trial 的完整执⾏。

将 Harbor 的 BaseEnvironment 封装为 HarborSandbox 后端，供 Deep Agents 的⽂件系统⼯具与（间接）命令执⾏使⽤。

. ⽀持两种构建路径：

use\_cli\_agent=True （默认）： deepagents\_cli.agent.create\_cli\_agent ，在 Harbor中 关闭 HITL（ auto\_approve=True ）、关闭 memory/skills/shell（沙箱由HarborSandbox 提供执⾏⾯）。

use\_cli\_agent=False deepagents.create\_deep\_agent ，传⼊同⼀ HarborSandbox与带⽬录上下⽂的 系统提示。

可观测性：当设置环境变量 LANGSMITH\_EXPERIMENT 时，使⽤ LangSmith 的 trace( .) 包裹 ainvoke ，把单次 trial 关联到实验项⽬，并写⼊ reference\_example\_id （若启动时能从LangSmith 数据集构建 instruction → example\_id 映射）。

## 2.2系统提示与「设计决策」

模块级 SYSTEM\_MESSAGE 在任务开始时注⼊ 当前⼯作⽬录 与 初始⽂件列表（最多展示前 10项），明确告诉模型：不要为重复罗列⽽滥⽤ ls ，仅在状态变化或需要探索⼦⽬录时再列⽬录。这是对 token 浪费与冗余⼯具调⽤ 的显式约束。

模型默认与 Harbor 侧对⻬：若未指定 model\_name ，使⽤ SDK 的 get\_default\_model()并在模型⽀持时应⽤ Harbor 传⼊的 temperature

## 2.3 ATIF 轨迹写出

\_save\_trajectory 将 LangGraph 返回的 messages 转为 Harbor 的 Trajectory 模型：Step ToolCall / Observation ，并统计 token ⽤量写⼊ FinalMetrics 。

schema\_version 固定为 ATIF-v1.2 ；在 agent.extra 中附带 frameworklangchain\_\* 版本，以及可选的 infrastructure 元数据（⻅下⼀章节的InfraMetadata ）。

## 2.4 CLI 启动⽅式

Harbor 通过 import 路径 加载智能体类，典型写法为：

```txt
harbor run --agent-import-path deepagents_harbor:DeepAgentsWrapper ... bash 
```

在 libs/evals ⽬录下也可配合 uv run 使⽤（与 README 示例⼀致）：

```txt
bash
uv run harbor run --agent-import-path deepagents_harbor:DeepAgentsWrapper ... 
```

Makefile 中通过 AGENT\_KWARG 传⼊ -agent-kwarg use\_cli\_agent= . ，在 本地 CLI 模式 与CI SDK 模式 间切换。

## 3. HarborSandbox ：文件系统与执行的桥

⽂件： deepagents\_harbor/backend.py

类： HarborSandbox(SandboxBackendProtocol)

## 3.1 协议⻆⾊

实现 Deep Agents 的 SandboxBackendProtocol （异步变体）： aexecute areadawrite aedit als agrep aglob ，以及批量 aupload\_filesadownload\_files 。

同步⽅法 ⼀律 NotImplementedError ，强制调⽤⽅⾛异步路径，与 Harbor 环境 API ⼀致。

## 3.2设计决策

## 1. ⼤⽂件与 ARG\_MAX

awrite aedit 使⽤ Harbor 环境的 upload\_file download\_file 传内容，避免把巨量字符串塞进 shell 参数，规避操作系统 ARG\_MAX 限制。

## 2. 读/搜/列⽬录⾛ shell

aread ⽤ awk 做⾏区间读取； als aglob agrep 通过受控 shell 脚本解析为结构化LsResult GlobResult GrepResult 。

## 3. 超时与可诊断性

aexecute 默认 300 秒 超时（ DEFAULT\_COMMAND\_TIMEOUT\_SEC ），超时返回 exit code 124（与 GNU timeout 约定⼀致），并在输出中给出 可操作的缩短建议（分包安装、后台构建等）。

## 4. ⾮交互 shell 噪声过滤

过滤常⻅于⽆ TTY 环境下的 bash 提示（如 job control 相关），减少污染模型观测的stdout/stderr。

## 4. langsmith.py ：数据集、实验与反馈

⽂件： deepagents\_harbor/langsmith.py

CLI 薄封装： scripts/harbor\_langsmith.py （⻅第 24 章）

## 4.1 从 Harbor 任务构建 LangSmith 数据集

create\_dataset ：经 Harbor RegistryClientFactory 下载指定数据集版本到临时⽬录，扫描每个任务的 instruction.md task.toml solution/solve.sh 等，⽣成带 稳定example id（ create\_example\_id\_from\_instruction ：指令⽂本 + seed 的 SHA-256 →UUID）的 examples，并 create\_examples 写⼊ LangSmith。

## 4.2 实验会话

create\_experiment\_async create\_experiment ：在 LangSmith 上创建 Tracer Session（ /sessions ），绑定 reference\_dataset\_id ，返回可在 UI 中对⽐的 URL；实验名通常作为LANGSMITH\_EXPERIMENT 传给 Harbor 运⾏。

## 4.3 反馈： harbor\_reward

add\_feedback ：遍历某次 job ⽬录下各 trial，读取 result.json 中verifier\_result.rewards.reward ，以 harbor\_reward 为 key 写⼊ LangSmithFeedback。

通过 trial\_name 元数据 在 LangSmith 中定位 唯⼀根 run，避免与错误 trial 错配；已存在同key 反馈时 跳过（去重）。

## 5. metadata.py 与基础设施噪声

⽂件： deepagents\_harbor/metadata.py

InfraMetadata 记录编排机（host）与沙箱内（sandbox）的 CPU、内存、OS、HARBOR\_CONCURRENCY 等，⽤于 事后分析「环境抖动」对分数的影响。

： collect\_sandbox\_metadata DeepAgentsWrapper.run 在 trial 开始时 尽⼒采集（失败只打⽇志，不中断 trial），结果写⼊ ATIF agent.extra.infrastructure 。

## 6. 模块关系小结

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/02b3528e-b243-4cb0-b036-faa38c49ff02/2cd7aa6d22c933c6965d544818d508116cdf8b16a4d360a6e934aaba60cbbd6e.jpg)

⼀句话：Harbor 负责「在哪跑、怎么验、多少分」； DeepAgentsWrapper + HarborSandbox 负责「把 Deep Agents 接到那个世界」； langsmith.py 负责「把同⼀批任务在 LangSmith ⾥变成可对⽐、可打分的实验资产」。

## 第 23 章：Terminal Bench 2.0 评估

## 主要参考源码路径

libs/evals/README.md （Terminal Bench 2.0、运⾏⽅式、LangSmith ⼯作流、失败模式表）

libs/evals/Makefile （ run-terminal-bench-\* ⽬标与并发参数）

libs/evals/deepagents\_harbor/deepagents\_wrapper.py （Harbor 智能体⼊⼝）

libs/evals/scripts/harbor\_langsmith.py （LangSmith CLI）

## 1. Terminal Bench 2.0 是什么

Terminal Bench 2.0 是⼀个 终端/计算机使⽤向 的智能体评测基准，覆盖 90+ 个任务，⽤于衡量智能体在 真实或接近真实的命令⾏环境 中 理解任务、操作仓库、运⾏构建与测试、调试失败 的综合能⼒。

## 1.1领域与难度跨度

任务横跨 软件⼯程、⽣物信息、安全、游戏 等多个领域；同⼀套 harness 下，既有「写脚本即可的⼩任务，也有需要 多步推理、⻓链路⼯具调⽤与环境状态依赖 的硬任务。

## Terminal Bench 评估流程图

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/02b3528e-b243-4cb0-b036-faa38c49ff02/f2fdf7461d757b83c1b4a18d3b75547eea1abeeaaa5863749bafe48eb30892c7.jpg)

## 1.2示例任务（README与社区描述⼀致）

<table><tr><td>任务标识(示例)</td><td>考察点(概括)</td></tr><tr><td>path-tracing</td><td>从渲染图像 反推/还原 C 程序 一类逆向与实现能力</td></tr><tr><td>chess-best-move</td><td>调用棋类引擎或环境,求 最优着法</td></tr><tr><td>git-multibranch</td><td>多分支 Git 操作、合并冲突处理等版本控制实战</td></tr><tr><td>sqlite-with-gcov</td><td>构建 SQLite、开启 gcov、分析覆盖率报告等工程链路</td></tr></table>

具体指令与 verifier 以 Harbor 下发的任务包为准；上表⽤于理解 基准在测什么类型的「终端智能」。

## 2. 在 Deep Agents 仓库中如何运行

⼯作⽬录建议为 libs/evals/ （与 README、 Makefile 致）。需配置 模型 API（如ANTHROPIC\_API\_KEY ）与 LangSmith 追踪（ LANGSMITH\_API\_KEYLANGSMITH\_TRACING=true ）等；使⽤ Daytona 等云沙箱时再配置对应 API Key。

## 2.1 直接使⽤ harbor run

Docker（本地、顺序 slot，README 示例 -n 1 ）：

```shell
uv run harbor run --agent-import-path deepagents_harbor:DeepAgentsWrapper \
--dataset terminal-bench@2.0 -n 1 --jobs-dir jobs/terminal-bench --env docker 
```

bash

Daytona（云沙箱，可提⾼并发；README 示例 -n 10 ）：

```shell
uv run harbor run --agent-import-path deepagents_harbor:DeepAgentsWrapper \
--dataset terminal-bench@2.0 -n 10 --jobs-dir jobs/terminal-bench --env daytona 
```

bash

说明：

-n Harbor 侧的 并发 trial 槽位数（并⾏沙箱数量），不是「只跑前 n 个任务」；限制任务数量应使⽤ Harbor 的 -l N （README 注明）。

-jobs-dir ：job 输出根⽬录（含各次运⾏的 trial ⼦⽬录），后续 分析脚本与 add-feedback路径 都依赖此结构。

## 2.2 Makefile 快捷⽬标

libs/evals/Makefile 封装了常⽤环境；注意 各⽬标的默认并发与后端不同：

<table><tr><td>目标</td><td>环境</td><td>默认 -n (并发槽)</td></tr><tr><td>make run-terminal-bench-docker</td><td>docker</td><td>1</td></tr><tr><td>make run-terminal-bench-daytona</td><td>daytona</td><td>40</td></tr><tr><td>make run-terminal-bench-modal</td><td>modal</td><td>4</td></tr><tr><td>make run-terminal-bench-runloop</td><td>runloop</td><td>10</td></tr></table>

本地调试可优先 Docker + ⼩ -n ；⼤规模跑分可在 Daytona / Modal 上提⾼并发，但需权衡 成本、配额与失败重试。

AGENT\_MODE 默认为 cli ；通过 AGENT\_KWARG 传⼊ use\_cli\_agent 与 CI 默认的 SDK 模式对⻬。

## 3. 可用沙箱环境一览

Harbor -env 常⻅取值（与 README ⼀致）：

<table><tr><td>值</td><td>适用场景</td></tr><tr><td>docker</td><td>本机 Docker,适合复现与调试</td></tr><tr><td>daytona</td><td>Daytona 云沙箱,需 DAYTONA_API_KEY</td></tr><tr><td>modal</td><td>Modal 云端算力</td></tr><tr><td>runloop</td><td>Runloop 沙箱</td></tr></table>

选择环境是 「评测可信度 vs 成本/速度」 的权衡：本地 Docker 更易排错，云环境更适合 ⾼并⾏sweep。

## 4. LangSmith 工作流（与 Harbor 奖励对齐）

整体链路：Deep Agents → Harbor 评测 → LangSmith 追踪与分析 → 迭代提示词/⼯具/模型。

## 4.1创建数据集

从 Harbor registry 拉取任务定义，在 LangSmith 中⽣成与指令对⻬的 examples（实现⻅deepagents\_harbor/langsmith.py ）：

```batch
python scripts/harbor_langsmith.py create-dataset terminal-bench --version 2.0 
```

## 4.2 创建实验会话

```txt
python scripts/harbor_langsmith.py create-experiment terminal-bench --name deepagents-baseline-v1 
```

脚本会在标准输出打印 实验名与对⽐ URL（stdout 约定两⾏，供⾃动化解析）。

## 4.3带追踪运⾏

将实验名设为环境变量，使 DeepAgentsWrapper ⽤ langsmith.trace 包裹运⾏：

```batch
set LANGSMITH_EXPERIMENT=deepagents-baseline-v1
make run-terminal-bench-daytona 
```

bash

（Linux/macOS 使⽤ export 。）亦可在开发阶段改⽤ LANGSMITH\_PROJECT 指向固定项⽬，获得更简单的项⽬视图（README 选项说明）。

## 4.4 回写 Harbor 奖励到 LangSmith

评测结束后，把各 trial 的 result.json 奖励 写成 Feedback harbor\_reward （0.0～1.0）：

```shell
python scripts/harbor_langsmith.py add-feedback jobs/terminal-bench/2025-12-02_16-25-40 --project-name deepagents-baseline-v1 
```

-project-name 须与 LangSmith 中存放该次追踪的 项⽬名 ⼀致（与 README 中「实验名作为项⽬视图」的⽤法对⻬；若以 LANGSMITH\_EXPERIMENT 运⾏，通常传⼊同名实验名）。

## 5. Deep Agent harness：经 Terminal Bench 验证的默认模式

README 将下列四点总结为 跨任务表现较好的默认组合（与 SDK / CLI harness 设计理念⼀致）：

## 1. 细致的系统提示（Detailed System Prompt）

明确⼯作⽬录、⼯具使⽤边界、何时列⽬录、何时测试等，减少 ⽆⽬的探索。

## 2. 规划中间件（Planning Middleware， write\_todos ）

把⻓链路任务拆成可勾选步骤，降低 跳步实现与遗忘约束 的概率。

## 3. ⽂件系统⼯具（Filesystem tools）

ls read\_file write\_file edit\_file / glob / grep 等，⽀持 ⼤代码库导航与增量修改。

## 4. ⼦智能体（SubAgents， task ⼯具）

将⼦任务隔离在独⽴上下⽂中，减轻 主线程上下⽂污染 与 ⼯具调⽤纠缠。

在 Harbor 集成中，CLI 模式会 关闭 CLI ⾃有的 shell/skills/memory 部分能⼒，由

HarborSandbox 提供执⾏与⽂件语义；上述设计仍体现在 默认⼯具组合与系统提示策略 上。

## 6. 常见失败模式 （README 归纳）

下列模式来⾃ libs/evals/README.md 的运维与排错经验，适合作为 看轨迹时的检查清单：

<table><tr><td>模式</td><td>典型症状</td><td>可能改进方向</td></tr><tr><td>规划不足(Poor Planning)</td><td>未读需求直接改代码</td><td>提示词要求 先复述目标与计划 再动手</td></tr><tr><td>工具使用不当(Incorrect Tool Usage)</td><td>滥用 bash cat 而非read_file</td><td>强化 工具说明与正反例</td></tr><tr><td>缺少增量测试(No Incremental Testing)</td><td>一次大改后才发现失败</td><td>要求 每完成一小步就运行测试/检查</td></tr><tr><td>路径幻觉(Hallucinated Paths)</td><td>未确认文件存在就读取</td><td>规则化:先 ls / glob 再read_file</td></tr><tr><td>模型错配(Wrong Model)</td><td>复杂推理持续失败</td><td>对硬任务 升级模型 或 拆分子任务</td></tr></table>

## 7. 本章与源码的对应关系

「跑起来」： Makefile 的 run-terminal-bench-\* + Harbor CLI；智能体类deepagents\_harbor:DeepAgentsWrapper

. 「可对⻬ LangSmith」： scripts/harbor\_langsmith.py +deepagents\_harbor/langsmith.py

「事后分析」：第 24 章的 scripts/analyze.py 与 failure / stats 模块。

Terminal Bench 2.0 在⼯程上的价值，不仅是 分数，更是 可复现的失败样本 与 ATIF 轨迹，为Deep Agents 的默认 harness 提供 回归基线。

## 第 24 章：Harbor分析与统计工具

主要参考源码路径

```txt
- libs/evals/scripts/analyze.py
- libs/evals/scripts/harbor_langsmith.py
- libs/evals/scripts/generate_radar.py
- libs/evals/scripts/generate_eval_catalog.py
- libs/evals/scripts/generate_model_groups.py
- libs/evals/deepagents_harbor/failure.py
- libs/evals/deepagents_harbor/stats.py
- libs/evals/deepagents_harbor/metadata.py
- libs/evals/deepagents_harbor/langsmith.py (CLI 背后的业务实现)
- libs/evals/Makefile (radar、eval-catalog、model-groups 等目标)
```

## 1. 总览：评测后的「数据闭环」

Harbor job 落盘后，仓库在 libs/evals 内提供多层⼯具：

1. 作业扫描与统计： scripts/analyze.py 读取 trial ⽬录、 trajectory.json result.json等，结合 失败分类 与 置信区间，输出可解释的汇总。
2. 与 LangSmith 对⻬： scripts/harbor\_langsmith.py 管理数据集、实验会话与harbor\_reward 反馈。
3. 报告与⽬录⽣成：雷达图、 EVAL\_CATALOG.md MODEL\_GROUPS.md 等 ⽂档/图表产物 由独⽴脚本从结构化数据再⽣

本章按模块说明 职责、设计取舍与依赖关系。

## 2. scripts/analyze.py ：Job 与 trial 的 CLI 分析器

## 2.1 职责

. 扫描 jobs/ 下某次运⾏产⽣的 trial ⽬录树，解析：

奖励/是否通过（兼容多种结果⽂件约定，如 reward ⽂本、 result.json 等——以脚本实现为准）；

. trajectory.json （ATIF） 路径与⼯具使⽤统计；

. exception.txt 等旁路⽂件。

调⽤ deepagents\_harbor.failure 做 基础设施 vs 能⼒ 归因，调⽤deepagents\_harbor.stats 输出 Wilson 置信区间 与 最⼩可检测效应（MDE） 提示。

可选路径下会涉及 数据集⽬录中 solution/solve.sh 的索引（ scan\_dataset\_for\_solutions ），⽤于对⽐或辅助分析（详⻅脚本内注释与⼦命令）。

## 2.2 设计决策

失败分类输⼊可控：退出码优先从 ATIF 观测⽂本 结构化提取（ extract\_exit\_codes ），避免在整段轨迹上盲⽬正则导致 误报；解析失败再回退原始⽂本扫描

统计与分类解耦： analyze.py 负责编排 I/O；数学与分类规则 留在 failure.pystats.py ，便于单元测试与复⽤。

## 3. deepagents\_harbor/failure.py ：失败类别与退出码

## 3.1 FailureCategory

枚举区分：

CAPABILITY ：模型能⼒或策略问题（答案错 未完成等），且 ⽆明确基础设施信号

. INFRA\_OOM ：典型 exit 137 / OOM 相关⽂案。

. INFRA\_TIMEOUT ：典型 exit 124 / 超时⽂案。

. INFRA\_SANDBOX ：沙箱崩溃、⽹络不可达、 exec failed 等。

. UNKNOWN ：有异常⽂本但 ⽆法归类 到上述基础设施模式。

提供 is\_infrastructure 属性，便于在报表中 剥离环境噪声

## 3.2 classify\_failure(...)

优先使⽤退出码（ exit\_codes 列表）判断 OOM/超时。

模式匹配仅针对 exception.txt 类受控⽂本，刻意 不 对整个模型⽣成内容做关键字扫描，以降低误判。

## 3.3 extract\_exit\_codes(trajectory\_json)

解析 ATIF JSON，从 observation.results\[].content 收集⼯具输出，再在其中匹配exit\_code / exit code 等形态。

若 JSON ⾮法或⾮ ATIF，则 回退 到 \_extract\_exit\_codes\_raw 对整段字符串做正则（兼容性路径）。

## 4. deepagents\_harbor/stats.py ：二项比例与显著性直觉

## 4.1 wilson\_ci(successes, total, z=1.96)

对成功率这类 ⼆项⽐例 计算 Wilson 置信区间，在⼩样本或⽐例接近 0/1 时⽐正态近似更稳健；注释说明与 Anthropic 基础设施噪声研究 的建议⼀致。

## 4.2 format\_ci(...)

. 将点估计与区间格式化为⼈类可读字符串，例如：72.3% \[68.1%, 76.2%] (95% CI, n=90) （实现以源码为准）。

## 4.3 min\_detectable\_effect(total, z=1.96, p=0.5)

在 两次独⽴运⾏、样本量相同 的简化假设下，估计 最⼩可检测效应（MDE）：若两次成功率差距⼩于 MDE，则 可能⽆法与噪声区分。

. 默认 p=0.5 取 最保守（⽅差最⼤） 的基准⽐例。

设计意图：防⽌在 90 题级别 上对 1～2 个 task 的涨跌 过度解读。

## 5. deepagents\_harbor/metadata.py ：沙箱与宿主元数据

InfraMetadata ：宿主平台、Python 版本、沙箱类型名、 nproc /内存/ uname 等 尽⼒采集字段，以及 HARBOR\_CONCURRENCY 等上下⽂。

collect\_sandbox\_metadata(backend) ：对实现 SandboxLike （含 HarborSandbox ）的后端执⾏短命令；任何异常都被吞掉并打⽇志，不影响 trial。

元数据最终由 DeepAgentsWrapper 写⼊ ATIF（⻅第 22 章），供 analyze.py 或外部notebook 做分层分析。

## 6. scripts/harbor\_langsmith.py langsmith.py

## 6.1 分⼯

deepagents\_harbor/langsmith.py ：全部业务逻辑（数据集扫描、Harbor registry 下载、HTTP 创建 session、 result.json → Feedback）。

scripts/harbor\_langsmith.py ：argparse 薄封装，加载 .env ，根据⼦命令路由。

## 6.2 ⼦命令

<table><tr><td>子命令</td><td>作用</td></tr><tr><td>create-dataset</td><td>从Harbor拉取任务并在LangSmith创建数据集与examples</td></tr><tr><td>ensure-dataset</td><td>若不存在则创建,否则打印已存在信息</td></tr><tr><td>create-experiment</td><td>绑定数据集的实验会话;stdout输出名称与URL(两行)</td></tr><tr><td>add-feedback</td><td>遍历job目录trial,按trial_name元数据找根run,写入harbor_reward(0.0~1.0),并做去重</td></tr></table>

## 6.3 add-feedback 与 trial 对⻬⽅式

. 使⽤ LangSmith 过滤条件：

```txt
eq(metadata_key, "trial_name") 且 eq(metadata_value, "<trial_dir_name>")
```

要求 恰好⼀条 根 run；多条或⽆匹配均记为错误，避免 错误地把分打到别的 trace 上。

## 7. 其他生成类脚本（与 Harbor 并列的 evals 工具链）

下列脚本主要服务 内置 pytest eval 套件与 CI，但与 「分析、报表、⽬录」 同⼀层级，常⼀起出现在 Makefile 中：

## 7.1 scripts/generate\_radar.py

依赖 deepagents\_evals.radar ，从 evals\_summary.json -results JSON 或 -toy⽣成 雷达图 PNG

. ⽤于 按 eval 类别 对⽐多模型能⼒（与 Harbor 轨迹分析互补）。

## 7.2 scripts/generate\_eval\_catalog.py

扫描 tests/evals 与 deepagents\_evals/categories.json ，重写 EVAL\_CATALOG.md --check ⽤于 CI 防漂移。

## 7.3 scripts/generate\_model\_groups.py

从仓库 .github/scripts/models.py 导⼊注册表，⽣成 MODEL\_GROUPS.md ，与 GitHubActions eval ⼯作流⽂档对⻬。

## 8. 模块关系图

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/02b3528e-b243-4cb0-b036-faa38c49ff02/b683f5643d01b7e2f8987f8f48ae3592419ced56972e7245788a7600d73f49a4.jpg)

## 9. 使用建议（工程化）

. 先保证轨迹与 result.json 完整，再跑 analyze.py 与 add-feedback ，否则统计与LangSmith 侧会出现 ⼤量 fallback / 找不到 run。

解读分数时 同时看 format\_ci 与 min\_detectable\_effect ，并把FailureCategory.is\_infrastructure 为真的 trial 单独分层。

与第 23 章的 Terminal Bench 流程结合：Harbor 跑分 → add-feedback 关联 LangSmith →analyze.py 本地汇总，形成 可重复的改进闭环。

文档来源与路径

<table><tr><td>类型</td><td>路径</td></tr><tr><td>包根目录</td><td>libs/acp/</td></tr><tr><td>Python 包源码</td><td>libs/acp/deepagents_acp/</td></tr><tr><td>示例</td><td>libs/acp/examples/</td></tr><tr><td>测试</td><td>libs/acp/tests/</td></tr><tr><td>构建与依赖声明</td><td>libs/acp/pyproject.toml、libs/acp/uv.lock</td></tr></table>

## 概述

libs/acp/ 为 Deep Agents 提供 Agent Client Protocol（ACP） 侧的服务端集成：在标准化协议之上，把 Deep Agent 的能⼒暴露给客户端，使「客户端—智能体」之间的会话、⼯具调⽤与消息流能够以统⼀⽅式交互。

仓库顶层 AGENTS.md 中将该⽬录记为协议相关能⼒；本包通过 PyPI 依赖 agent-client-protocol 使⽤官⽅ ACP 协议实现（⻅ pyproject.toml 中的 agent-client-protocol ）。

## 包与构建

发⾏包名： deepagents-acp （ pyproject.toml 中 \[project].name ）。

构建后端：Hatchling（ \[build-system] 中 hatchling.build ）。

可安装模块命名空间： deepagents\_acp/ （与发⾏名中的连字符对应为下划线导⼊路径）。

## 设计取舍

独⽴⼦包：ACP 与核⼼ SDK 解耦，便于单独版本化、单独测试，且依赖 deepagents 时通过\[tool.uv.sources] 指向可编辑的 ./deepagents ，符合 monorepo 本地开发习惯。

协议优先：服务端逻辑集中在 server.py ，与 acp 库的 schema、会话⽣命周期 API 对⻬，减少⾃研协议分叉。

## 运行方式

可通过模块⼊⼝直接启动（对应 deepagents\_acp/ \_main \_.py ）：

```batch
python -m deepagents_acp 
```

bash

\_main \_.py 调⽤ server 中的 \_serve\_test\_agent() ，⽤于拉起可演示/可测试的 ACP 服务端⾏为。

## 模块关系（核心文件）

<table><tr><td>模块 / 文件</td><td>职责</td></tr><tr><td>deepagents_acp/__init__.py</td><td>包说明与对外符号(当前以包级文档字符串为主)。</td></tr><tr><td>deepagents_acp/__main__.py</td><td>CLI/模块运行入口,main() → 异步服务。</td></tr><tr><td>deepagents_acp/server.py</td><td>ACP 服务端实现:对接 acp 库的 Agent、会话、工具调用与 Deep Agents 的 create_deep_agent、后端组合等。</td></tr><tr><td>deepagents_acp/utils.py</td><td>服务端辅助逻辑。</td></tr></table>

与上游的关系： server.py 依赖 deepagents.create\_deep\_agent 以及deepagents.backends （如 CompositeBackend 、 FilesystemBackend StateBackend ），

## ACP 协议消息格式

ACP 协议定义了标准化的消息格式，⽤于客户端与智能体之间的通信：

消息类型

<table><tr><td>类型</td><td>方向</td><td>说明</td></tr><tr><td>TextMessage</td><td>双向</td><td>纯文本消息内容</td></tr><tr><td>ToolCall</td><td>客户端→服务端</td><td>工具调用请求</td></tr><tr><td>ToolResult</td><td>服务端→客户端</td><td>工具执行结果</td></tr><tr><td>StateUpdate</td><td>服务端→客户端</td><td>状态变更通知</td></tr><tr><td>Error</td><td>双向</td><td>错误信息</td></tr></table>

## 消息结构示例

```python
from agent_client_protocol import TextMessage, ToolCall
# 文本消息
text_msg = TextMessage(
    content="Hello, how can I help you?", 
    role="assistant"
)
# 工具调用
tool_call = ToolCall(
    name="read_file",
    arguments={"path": "/tmp/test.txt"},
```

```txt
id="call_123"
) 
```

## 会话生命周期管理

ACP 会话遵循明确的⽣命周期状态机：

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/02b3528e-b243-4cb0-b036-faa38c49ff02/349b02778426e9d4c48606923a3b12dbee3f1a55d6ff2d7568d4d9d276ddd86a.jpg)

会话状态

<table><tr><td>状态</td><td>说明</td><td>可执行操作</td></tr><tr><td>Created</td><td>会话已创建,未初始化</td><td>初始化</td></tr><tr><td>Active</td><td>会话活跃,可接收消息</td><td>发送消息、调用工具</td></tr><tr><td>Processing</td><td>正在处理请求</td><td>等待、取消</td></tr><tr><td>Paused</td><td>会话暂停</td><td>恢复</td></tr><tr><td>Closed</td><td>会话已关闭</td><td>无</td></tr></table>

会话管理代码示例

```python
from deepagents_acp.server import create_acp_server
# 创建服务端实例
server = create_acp_server(agent=my_agent)
# 创建新会话
session = await server.create_session(session_id="session_001")
# 发送消息并获取响应
response = await session.send_message(
    TextMessage(content="分析这个文件", role="user")
)
# 关闭会话
await session.close()
```

## 错误处理机制

ACP 定义了标准化的错误类型和处理流程：

错误类型

<table><tr><td>错误代码</td><td>说明</td><td>处理建议</td></tr><tr><td>INVALID_REQUEST</td><td>请求格式错误</td><td>检查消息结构</td></tr><tr><td>SESSION_NOT_FOUND</td><td>会话不存在</td><td>重新创建会话</td></tr><tr><td>TOOL_NOT_FOUND</td><td>工具不存在</td><td>检查工具注册</td></tr><tr><td>EXECUTION_ERROR</td><td>工具执行失败</td><td>检查参数和权限</td></tr><tr><td>TIMEOUT</td><td>处理超时</td><td>重试或增加超时</td></tr><tr><td>INTERNAL_ERROR</td><td>服务端内部错误</td><td>联系管理员</td></tr></table>

## 错误处理示例

```python
from agent_client_protocol import ACPError, ErrorType
try:
    response = await session.send_message(message)
except ACPError as e:
    if e.error_type == ErrorType.SESSION_NOT_FOUND:
    # 重新创建会话
    session = await server.create_session()
    response = await session.send_message(message)
elif e.error_type == ErrorType.EXECUTION_ERROR:
    # 记录错误并通知用户
    logger.error(f"Tool execution failed: {e.message}")
    await session.send_message(
    TextMessage(content=f"抱歉，工具执行失败：{e.message}")
else:
    raise
```

python

## Python 客户端连接示例

基础连接示例

```python
import asyncio
from agent_client_protocol import ACPClient, TextMessage

async def main():
    # 创建客户端连接
    client = ACPClient(server_url="http://localhost:8080")

    # 创建会话
    session = await client.create_session()

    # 发送消息
    response = await session.send_message(
    TextMessage(content="你好，请帮我分析一下当前目录的文件结构", role="user")
)

    # 处理响应
    for message in response.messages:
    if isinstance(message, TextMessage):
    print(f"Agent: {message.content}")

    # 关闭连接
    await session.close()
    await client.close()

if __name__ = "__main__":
    asyncio.run(main())
```

带⼯具调⽤的完整示例

```python
import asyncio
from agent_client_protocol import (
    ACPClient, TextMessage, ToolCall, ToolResult
) 
```

```python
async def handle_tool_call(tool_call: ToolCall) → ToolResult:
    """处理工具调用请求"""
    if tool_call.name = "read_file":
    # 模拟文件读取
    content = "文件内容示例"
    return ToolResult(
    call_id=tool_call.id,
    content=content,
    is_error=False
    )
    elif tool_call.name = "write_file":
    # 模拟文件写入
    return ToolResult(
    call_id=tool_call.id,
    content="文件写入成功",
    is_error=False
    )
    else:
    return ToolResult(
    call_id=tool_call.id,
    content=f"未知工具：{tool_call.name}",
    is_error=True
    )

async def main():
    client = ACPClient(server_url="http://localhost:8080")
    session = await client.create_session()

# 注册工具处理器
session.on_tool_call(handle_tool_call)

# 发送需要工具调用的消息
response = await session.send_message(
    TextMessage(content="请读取 config.json 文件", role="user")
)

# 处理响应中的工具调用
for message in response.messages:
    if isinstance(message, ToolCall):
    result = await handle_tool_call(message)
    await session.send_tool_result(result)
```

```python
elif isinstance(message, TextMessage):
    print(f"Agent: {message.content}")

await session.close()

await client.close()

if __name__ = "__main__":
    asyncio.run(main()) 
```

异步流式处理示例

```python
import asyncio
from agent_client_protocol import ACPClient, TextMessage

async def stream_conversation():
    client = ACPClient(server_url="http://localhost:8080")
    session = await client.create_session()

    # 流式发送消息并接收响应
    async for chunk in session.stream_message(
    TextMessage(content="请详细解释 Python 的异步编程", role="user")
    ):
    if isinstance(chunk, TextMessage):
    # 实时打印响应内容
    print(chunk.content, end="", flush=True)

    print()  # 换行
    await session.close()
    await client.close()

if __name__ = "__main__":
    asyncio.run(stream_conversation())
```

## 示例与测试

示例（ libs/acp/examples/ ）：如 demo\_agent.py local\_context.py ，展示如何结合本地上下⽂或演示代理使⽤ ACP 集成。

测试（ libs/acp/tests/ ）：覆盖主流程、⼯具、模型切换、命令⽩名单、危险模式检测等（如test\_main.py test\_agent.py test\_model\_switching.py 等）。

## 小结

deepagents-acp 把 Deep Agents 嵌⼊ ACP 服务端⻆⾊，客户端按协议连接即可获得统⼀的智能体会话体验；源码以 deepagents\_acp.server 为枢纽，示例与测试分别位于 examples/ 与tests/ 。

文档来源与路径

<table><tr><td>类型</td><td>路径</td></tr><tr><td>包根目录</td><td>libs/repl/</td></tr><tr><td>Python 包源码</td><td>libs/repl/langchain_repl/</td></tr><tr><td>测试</td><td>libs/repl/tests/ (含 unit_tests/ 等)</td></tr><tr><td>构建与依赖声明</td><td>libs/repl/pyproject.toml、libs/repl/uv.lock</td></tr></table>

## 概述

libs/repl/ 提供 langchain-repl 包，为智能体运⾏时增加 REPL ⻛格的可执⾏环境：模型⽣成的代码可在受控解释器中执⾏，并通过中间件挂⼊ LangGraph / Deep Agents 的请求链路。

典型⽤途：在智能体会话中需要 交互式执⾏代码（验证⽚段、数据处理、快速试探 API ⾏为）时，由 ReplMiddleware 注⼊能⼒，由 Interpreter 负责实际执⾏语义。

## 包与对外 API

. 发⾏包名： langchain-repl （⻅ libs/repl/pyproject.toml ）。

公开导出（ langchain\_repl/ \_init \_.py ）：

. Interpreter ：在 REPL 式环境中执⾏代码。

. ReplMiddleware ：将 REPL 能⼒以中间件形式接⼊智能体。

. \_version \_ ：包版本字符串。

```txt
langchain_repl/
├── __init__.py    # 导出 Interpreter, ReplMiddleware, __version__
├── interpreter.py    # 解释器实现
├── middleware.py    # ReplMiddleware
└── _foreign_function_docs.py  # 与外部函数/工具文档相关的辅助
```

## 核心概念

## Interpreter

职责：在 交互式 类 REPL 的语义下执⾏代码（具体隔离级别与语⾔运⾏时由实现决定）。

关系：被中间件或上层编排调⽤，是「执⾏」⼀层的核⼼抽象。

## ReplMiddleware

职责：作为 中间件，把 REPL / 解释器能⼒接到智能体管道中（与消息、⼯具调⽤、系统提示等协同）。

关系：依赖 Interpreter 的⾏为；测试中存在端到端⽤例（如

tests/unit\_tests/test\_end\_to\_end.py test\_end\_to\_end\_async.py ）以及系统提示快照测试，验证与⽆⼯具/混合外部函数等场景下的提示词与⾏为。

## 执行隔离机制

Interpreter 提供多层隔离机制，确保代码执⾏的安全性和可控性：

## 隔离级别

<table><tr><td>级别</td><td>说明</td><td>适用场景</td></tr><tr><td>NONE</td><td>无隔离,直接在主进程执行</td><td>开发调试</td></tr><tr><td>SUBPROCESS</td><td>子进程隔离,共享文件系统</td><td>一般用途</td></tr><tr><td>SANDBOX</td><td>沙箱隔离,受限文件系统和网络</td><td>不可信代码</td></tr><tr><td>CONTAINER</td><td>容器隔离,完全独立环境</td><td>生产环境</td></tr></table>

## 隔离实现示例

```python
python
from langchain_repl import Interpreter, IsolationLevel

# 创建不同隔离级别的解释器
dev_interpreter = Interpreter(isolation_level=IsolationLevel.NONE)
prod_interpreter = Interpreter(isolation_level=IsolationLevel.CONTAINER)

# 执行代码
result = await dev_interpreter.execute("print('Hello, World!')")
print(result.stdout)  # 输出：Hello, World!
```

## 资源限制

```python
python
from langchain_repl import Interpreter, ResourceLimits
# 配置资源限制
limits = ResourceLimits(
    max_memory_mb=512,    # 最大内存 512MB
    max_cpu_seconds=30,    # 最大 CPU 时间 30 秒
    max_output_size=1024*1024, # 最大输出 1MB
    network_access=False,    # 禁止网络访问
    filesystem_readonly=True  # 文件系统只读
)
interpreter = Interpreter(resource_limits=limits)
```

## 支持的语言运行时

Interpreter ⽀持多种语⾔运⾏时，通过配置选择：

<table><tr><td>语言</td><td>运行时</td><td>版本</td><td>说明</td></tr><tr><td>Python</td><td>CPython</td><td>3.10+</td><td>默认运行时,完整支持</td></tr><tr><td>JavaScript</td><td>Node.js</td><td>18+</td><td>通过子进程调用</td></tr><tr><td>TypeScript</td><td>tsx</td><td>4.0+</td><td>基于 Node.js 的 TypeScript 运行时</td></tr><tr><td>Shell</td><td>bash/zsh</td><td>-</td><td>系统默认 shell</td></tr><tr><td>SQL</td><td>sqlite3</td><td>-</td><td>内置 SQLite 支持</td></tr></table>

## 多语⾔配置示例

```python
from langchain_repl import Interpreter, LanguageConfig
# Python 配置
python_config = LanguageConfig(
    language="python",
    runtime="cpython",
    version="3.11",
    startup_code="import sys; print(f'Python {sys.version}')"
)

# JavaScript 配置
js_config = LanguageConfig(
    language="javascript",
    runtime="node",
    version="18",
    startup_code="console.log('Node.js', process.version)"
)

# 创建多语言解释器
interpreter = Interpreter(languages=[python_config, js_config])
```

# 执⾏不同语⾔

```lua
python_result = await interpreter.execute("print('Hello from Python')", language="python")
js_result = await interpreter.execute("console.log('Hello from JavaScript')", language="javascript") 
```

## 系统提示注入细节

ReplMiddleware 通过系统提示注⼊，让模型了解可⽤的 REPL 能⼒：

## 提示注⼊流程

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/02b3528e-b243-4cb0-b036-faa38c49ff02/bb75683f938c3e43fb9ecae17402bca1d87a1f73ddd47c2fff5b61eb97dd0df0.jpg)

## 注⼊的提示内容

REPL\_SYSTEM\_PROMPT = """

你有⼀个交互式代码执⾏环境（REPL）可以使⽤。

# 可⽤能⼒

- 执⾏ Python、JavaScript、SQL 等代码
- 访问⽂件系统（受限）
- 安装临时包（会话内有效）

# 使⽤⽅式

使⽤代码块标记要执⾏的代码：

\`python

python

```txt
# 你的代码 here
print("Hello")
```

## 注意事项

代码在隔离环境中执⾏

. 每次执⾏独⽴，不共享状态

错误会返回详细信息 """

````python
##
### 基础使用示例
```python
from langchain_repl import Interpreter, ReplMiddleware
from deepagents import create_deep_agent

# 创建解释器
interpreter = Interpreter()

# 创建 REPL 中间件
replMiddleware = ReplMiddleware(interpreter=interpreter)

# 创建带有 REPL 能力的智能体
agent = create_deep_agent(
    model="anthropic/claude-3-5-sonnet-20241022",
    middleware=[replMiddleware]
)

# 智能体现在可以执行代码
response = await agent.invoke(
    "请计算 fibonacci 数列的前 10 项，并用 matplotlib 绘制图表"
)
````

python

```python
from langchain_repl import (
Interpreter, ReplMiddleware,
IsolationLevel, ResourceLimits, LanguageConfig
) 
```

# 配置资源限制

```python
limits = ResourceLimits(
    max_memory_mb=1024,
    max_cpu_seconds=60,
    network_access=True, # 允许网络访问（用于下载包）
    allowed_domains=["pypi.org", "github.com"] # 限制可访问的域名
)
```

# 配置 Python 运⾏时

```python
python_config = LanguageConfig(
    language="python",
    runtime="cpython",
    version="3.11",
    startup_code="""
import sys
import os
print(f"Python {sys.version}")
print(f"Working directory: {os.getcwd()}")
","",
allowed_packages=["numpy", "pandas", "matplotlib"] # 预装的包)
```

# 创建⾼级解释器

```bazel
interpreter = Interpreter(
    isolation_level=IsolationLevel.SANDBOX,
    resource_limits=limits,
    languages=[python_config]
) 
```

# 创建中间件

```python
repl_middleware = ReplMiddleware(
    interpreter=interpreter,
    inject_system_prompt=True,  # 自动注入系统提示
    auto_execute=True,  # 自动执行代码块
```

```python
max_execution_time=30 # 单次执行最大时间
)
```

错误处理示例

```python
python
from langchain_repl import Interpreter, ExecutionError

interpreter = Interpreter()

try:
    result = await interpreter.execute("""
# 故意制造错误
undefined_variable + 1
""")

except ExecutionError as e:
    print(f"执行错误：{e.message}")
    print(f"错误类型：{e.error_type}")
    print(f"行号：{e.line_number}")
    print(f"堆栈跟踪：\n{e.traceback}")
```

## ⼀设计取舍

中间件⽽⾮单 ⼯具：REPL 能⼒以 Middleware 形式出现，便于与现有 Deep Agents /LangGraph 中间件链组合，⽽不是零散⼯具函数堆砌。

测试分层： unit\_tests 覆盖解释器、系统提示、外部函数⽂档等； smoke\_tests 含快照，防⽌提示词或⾏为静默漂移。

## 测试布局

<table><tr><td>区域</td><td>说明</td></tr><tr><td>libs/repl/tests/unit_tests/test_interpreter.py</td><td>解释器行为。</td></tr><tr><td>libs/repl/tests/unit_tests/test_end_to_end.py、test_end_to_end_async.py</td><td>与智能体链路的端到端行为。</td></tr><tr><td>libs/repl/tests/unit_tests/smoke_tests/</td><td>系统提示等快照回归。</td></tr></table>

## 与 Deep Agents 生态的关系

langchain-repl 位于 libs/repl/ ，与 libs/deepagents/ 核⼼ SDK 并列，供需要在 会话中执⾏代码 的场景选⽤：在应⽤侧将 ReplMiddleware 加⼊ create\_deep\_agent( .,middleware=\[ .]) ⼀类的中间件列表即可（具体参数名以 SDK ⽂档为准）。

## 小结

langchain-repl 通过 Interpreter + ReplMiddleware 提供可组合的 REPL 执⾏能⼒；源码集中在 langchain\_repl/ ，质量由 libs/repl/tests/ 单元测试与快照测试保障。

文档来源与路径

<table><tr><td>类型</td><td>路径</td></tr><tr><td>合作伙伴根目录</td><td>libs/partners/</td></tr><tr><td>Daytona</td><td>libs/partners/daytona/</td></tr><tr><td>Modal</td><td>libs/partners/modal/</td></tr><tr><td>QuickJS</td><td>libs/partners/quickjs/</td></tr><tr><td>Runloop</td><td>libs/partners/runloop/</td></tr><tr><td>CLI 统一工厂(选型入口)</td><td>libs/cli/deepagents_cli/integrations/sandbox_factory.py</td></tr><tr><td>协议定义 (SDK)</td><td>libs/deepagents/deepagents/backends/protocol.py(SandboxBackendProtocol)</td></tr></table>

## 概述

libs/partners/ 下的多个 独⽴ Python 包 为 Deep Agents 提供 远程或可隔离的执⾏后端：多数实现为 Sandbox，与 SDK 中的 SandboxBackendProtocol 对⻬，从⽽在⽂件系统中间件等位置挂载 execute ⼯具（仅当后端⽀持该协议时）。

CLI 侧： deepagents\_cli.integrations.sandbox\_factory.create\_sandbox() 按 provider 名称 解析并创建/连接对应后端（如 daytona modal runloop 等），与 SDK 直接传⼊backend 实例 两种⽅式并存。

## 协议与统一抽象

SandboxBackendProtocol （定义于 Deep Agents SDK 的 backends 协议模块）：合作伙伴提供的 Sandbox 类 应实现该协议，以便与 CompositeBackend 、⽂件系统中间件、 execute ⼯具逻辑⼀致协作。

⼯⼚函数 create\_sandbox(provider, .) ： 返回 Generator\[SandboxBackendProtocol,None, None] ，内部通过 sandbox\_provider 等模块完成各⼚商 SDK 的适配与⽣命周期管理。

## 四个合作伙伴一览

## 1. Daytona（ libs/partners/daytona/ ）

<table><tr><td>项</td><td>内容</td></tr><tr><td>包名</td><td>langchain-daytona</td></tr><tr><td>主要导出</td><td>DaytonaSandbox (langchain_daytona)</td></tr><tr><td>定位</td><td>云端开发沙箱,适合在隔离环境中跑命令与项目</td></tr><tr><td>凭证</td><td>通常需要 DAYTONA_API_KEY (以各包 README / 厂商文档为准)</td></tr></table>

## 2. Modal（ libs/partners/modal/ ）

<table><tr><td>项</td><td>内容</td></tr><tr><td>包名</td><td>langchain-modal</td></tr><tr><td>主要导出</td><td>ModalSandbox</td></tr><tr><td>定位</td><td>Serverless 云算力,适合弹性、可扩展执行;支持 GPU,便于重计算场景</td></tr><tr><td>依赖</td><td>modal Python SDK(见 pyproject.toml)</td></tr></table>

## 3. QuickJS（ libs/partners/quickjs/ ）

<table><tr><td>项</td><td>内容</td></tr><tr><td>包名</td><td>langchain-quickjs</td></tr><tr><td>主要导出</td><td>QuickJSMiddleware (中间件,不是 Sandbox 类)</td></tr><tr><td>定位</td><td>轻量 JavaScript 执行(嵌入式 QuickJS)</td></tr><tr><td>模式说明</td><td>与 Daytona/Modal/Runloop 的 SandboxBackendProtocol 路径不同:以 Middleware 注入 JS执行能力,集成点偏向中间件链而非统一 execute 沙箱后端</td></tr></table>

## 4. Runloop（ libs/partners/runloop/ ）

<table><tr><td>项</td><td>内容</td></tr><tr><td>包名</td><td>langchain-runloop</td></tr><tr><td>主要导出</td><td>RunloopSandbox</td></tr><tr><td>定位</td><td>托管沙箱环境(Runloop 平台)</td></tr><tr><td>依赖</td><td>runloop-api-client</td></tr></table>

## 各包工程结构 （共同模式）

每个合作伙伴⽬录通常包含：

. 独⽴的 pyproject.toml 与 uv.lock

源码⼦包（如 langchain\_daytona/ langchain\_modal/ 等）

各⾃的 tests/ ⽬录

便于 独⽴发版、独⽴ CI 矩阵项（与主仓库 .github/workflows/ci.yml 中按路径检测的daytona 、 modal 、 runloop 、 quickjs 等 filter 输出⼀致）。

## 选型与集成路径

1. CLI：⽤户选择 sandbox provider 时，由 sandbox\_factory.create\_sandbox 统⼀创建；默认⼯作⽬录等映射在⼯⼚模块的 \_PROVIDER\_TO\_WORKING\_DIR 等常量中维护（如 daytona →/home/daytona modal /workspace 等）。
2. SDK / 应⽤代码：可直接构造 DaytonaSandbox ModalSandbox RunloopSandbox 等，作为 create\_deep\_agent( ., backend= .) 或复合后端的⼀部分传⼊。
3. QuickJS：在需要 JS ⽚段执⾏ 且不希望⾛完整远程沙箱时，优先考虑 QuickJSMiddleware 。

## ⼀设计取舍

协议 致 实现分散：Sandbox 实现放在 libs/partners \* ，避免核⼼ SDK 直接依赖所有云⼚商；需要时再安装对应可选依赖。

QuickJS 例外导出 Middleware：JS 执⾏体量与集成⽅式与「远程 Linux 沙箱」不同，故采⽤中间件模式更贴切。

CLI ⼯⼚集中化：降低主程序对各 import langchain\_\* 细节的重复代码，统⼀⽣命周期（创建、复⽤ sandbox\_id 、setup 脚本等）。

## 小结

libs/partners/ 提供 Daytona / Modal / Runloop 三类 SandboxBackendProtocol 实现及QuickJS 的 Middleware 路线；与 Deep Agents 核⼼通过 协议 + CLI ⼯⼚ 连接，可按场景选择云端沙箱或轻量 JS 执⾏。

<br />

<br />

````markdown

文档来源与路径


<table><tr><td>类型</td><td>路径</td></tr><tr><td>GitHub 工作流</td><td>.github/workflows/</td></tr><tr><td>脚本与自动化</td><td>.github/scripts/</td></tr><tr><td>发布说明</td><td>.github/RELEASING.md</td></tr><tr><td>Release Please 配置(仓库根)</td><td>release-please-config.json、.release-please-manifest.json</td></tr><tr><td>PR 模板与标签</td><td>.github/PULL_REQUEST_TEMPLATE.md、pr_label.yml、pr-labeler.js、pr-labeler-config.json</td></tr></table>

## 概述

Deep Agents monorepo 使⽤ GitHub Actions 驱动 持续集成（按变更路径选择性跑各包）、⾏为评估（Evals）、Harbor / Terminal Bench 类基准、版本与可选依赖⼀致性检查，以及基于release-please 的 CLI 发布流⽔线。辅助逻辑集中在 .github/scripts/ 。

## CI/CD 工作流图

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/97d1b029-1348-47aa-8a07-cdafd8905b7f/b5c2fa15715ca00f56d5c533a01d25f1c6970fa2474c646f1eeb4bd3cc59a14f.jpg)


## 主要工作流（ .github/workflows/ ）

## CI（ ci.yml 及复⽤⼦⼯作流）

. 触发： pull_request 、 push ⾄ main 、 merge_group 等。、

. ⾏为要点：

通过 paths filter 检测 libs/deepagents libs/cli 、 libs/evals 及各 partnersrepl 等是否变更，仅对受影响包跑 lint / 单元测试；SDK 变更会连带触发 CLI 测试。

与 _lint.yml _test.yml 等复⽤⼯作流配合，完成 ruff / ty / pytest 等质量⻔禁。

并发：同⼀ workflow + ref 分组， cancel-in-progress 取消冗余运⾏。

## Evals（ evals.yml ）

定位：对 真实 LLM 跑 libs/evals 下的⾏为评估（需 LANGSMITH_* 及各⼚商 API Key 等secrets）。

. 模型选择：⼯作流 inputs 提供 预设集合 与 单模型 规格；预设定义可参考libs/evals/MODEL_GROUPS.md 。

矩阵来源：与 .github/scripts/models.py ⽣成的 JSON 矩阵配合（⻅下⽂「模型矩阵」）。

Eval 并发：按 provider 分组的 concurrency，同⼀提供商上的多个 job 串⾏排队，不同提供商并⾏，减轻速率限制与配额冲突（详⻅ libs/evals/README.md 中「CI concurrency」）。

## Harbor（ harbor.yml ）

定位：Terminal Bench 等基准场景的运⾏（与 eval 体系共享模型注册脚本思路，环境变量侧使⽤ HARBOR_MODELS 等）。

## Release / release-please（ release.yml 、 release-please.yml ）

. release-please：根据 Conventional Commits 分析变更，打开/更新 发布 PR，合并后触发PyPI 发布与 GitHub Release（细节以 .github/RELEASING.md 为准）。

## SDK pin 检查（ check_sdk_pin.yml 等）

⽬的：保证 CLI 等对 SDK 的 版本钉选（pin） 与仓库策略⼀致，避免发版时依赖版本漂移。

## 其他质量⻔禁

. check_versions.yml ：配合 check_version_equality.py 。

. check_extras_sync.yml ：配合 check_extras_sync.py 。

. check_lockfiles.yml ：锁⽂件⼀致性。

. pr_lint.yml ：PR 标题等符合约定式提交与 scope。

auto-label-by-package.yml 、 pr_labeler.yml 、 pr_labeler_backfill.yml ：PR ⾃动打标签；脚本实现⻅ .github/scripts/pr-labeler.js 与 pr-labeler-config.json 。

## release-please-config.json 与多包发布

根⽬录 release-please-config.json 声明 changelog 分段、PR 标题模板、tag 规则等。当前仓库中 packages 映射以 libs/cli （ deepagents-cli ）为主：包含 pyproject.toml 与deepagents_cli/_version.py 等 extra-files，由 release-please 统⼀改版本号与CHANGELOG.md 。

说明：配置结构 ⽀持扩展多个路径键（每个 lib ⼀段）；若未来增加更多 PyPI 包，可在同⼀⽂件的 packages 下追加条⽬，并配合 .release-please-manifest.json 维护各路径版本。请以仓库内实际 JSON 为准。

## 版本一致

性： .github/scripts/check_version_equality.py

作⽤：确保 pyproject.toml 中的版本 与 _version.py 等单⼀真源 对 deepagents、cli 等指定包 保持⼀致，防⽌发布物与导⼊版本字符串不⼀致。

## 可选依赖同

步： .github/scripts/check_extras_sync.py

作⽤：校验各包 optional dependency groups / extras 在 monorepo 内 声明同步，避免⽂档或元数据与可安装 extras 漂移。

## 模型矩阵： .github/scripts/models.py

Model 具名元组： spec （如 anthropic:claude-sonnet-4-6 ）+ groups （frozenset，标签含 eval:* harbor:* 等）。

REGISTRY 全量模型清单；预设集合通过 _EVAL_PRESETS _HARBOR_PRESETS （及⽂档中的EVAL_MODELS HARBOR_MODELS 环境变量语义）解析为 并⾏矩阵 JSON，供 Actions 使⽤。

. 调⽤⽅式（脚本注释摘要）：

. python .github/scripts/models.py eval — 读取 EVAL_MODELS

## Eval CI 并发（再述）

同 provider：共享 concurrency group，第⼆个 job 等待第⼀个。

跨 provider：可 并⾏，提⾼吞吐并分散配额⻛险。

## PR 标签与贡献体验

pr-labeler.js + pr-labeler-config.json 按规则为 PR ⾃动加标签，便于筛选与发布说明归类。

PULL_REQUEST_TEMPLATE.md ：引导贡献者填写 AI 辅助声明、测试说明等（与 AGENTS.md 中PR 准则呼应）。

## 设计取舍

. 变更敏感 CI：仅测改动相关包，缩短反馈时间；核⼼ SDK 变更仍拉通 CLI，避免集成断裂。

脚本单源化模型列表： models.py 避免在 YAML 中⼿写冗⻓矩阵，降低 eval 与 harbor 分叉⻛险。

release-please 与版本脚本双保险：⾃动化发版 + CI 版本相等检查，减少⼈为漏改。

## 小结

CI/CD 以 .github/workflows/ 为⼊⼝，脚本层（ check_version_equality.py 、check_extras_sync.py 、 models.py 等） 承担可复⽤策略；发布以 release-please 与.github/RELEASING.md 为权威流程说明。


文档来源与路径


<table><tr><td>类型</td><td>路径</td></tr><tr><td>全局开发指南</td><td>AGENTS.md (仓库根目录)</td></tr><tr><td>各包工具配置</td><td>各 libs/*/pyproject.toml 中的 [tool.ruff]、[tool.ty]、[tool.pytest.ini_options] 等</td></tr></table>

## 概述

AGENTS.md 定义 Deep Agents Python monorepo 的架构认知、⼯具链、提交与 PR 规范、代码质量与安全红线、测试布局 以及 公共 API 稳定性 要求。本⽂档提炼其要点，便于写书或onboarding 时快速对⻬。

## 提交与 PR 规范

## Conventional Commits

PR 标题建议符合 约定式提交，类型与 scope 以 .github/workflows/pr_lint.yml 为准。

. 示例（ AGENTS.md ）：

feat(sdk): add new chat completion feature 

fix(cli): resolve type hinting issue 

. chore(evals): update infrastructure dependencies 

⼤⼩写：除专有名词外，标题倾向 ⼩写。

## AI 辅助贡献

PR 描述中需 声明 AI 如何参与；说明变更动机（「为什么」）与 需重点⼈⼯审查 的区域。


工具链


<table><tr><td>工具</td><td>用途</td></tr><tr><td>uv</td><td>依赖与虚拟环境管理;各 libs/ 包自有 pyproject.toml / uv.lock。</td></tr><tr><td>make</td><td>聚合常用命令(make test、make lint、make format等,以根与各包 Makefile为准)。</td></tr><tr><td>ruff</td><td>Lint + 格式化(替代 flake8、black、isort 等分散工具)。</td></tr><tr><td>ty</td><td>静态类型检查。</td></tr><tr><td>pytest</td><td>测试运行框架。</td></tr></table>

## 抑制 ruff 规则

优先⾏内 # noqa: RULE ：精确到⾏，避免掩盖同⽂件其他问题。

per-file-ignores ：仅⽤于 整类⽂件策略（如 tests/** 不要求 docstring、允许assert ），不为单⾏例外滥⽤。

## Ruff 配置示例

```toml
# pyproject.toml 中的 ruff 配置
[tool.ruff]
target-version = "py310"
line-length = 88
[tool.ruff.lint]
```

toml 

```toml
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "B",    # flake8-bugbear
    "C4",    # flake8-comprehensions
    "UP",    # pyupgrade
    "SIM",    # flake8-simplify
    "TCH",    # flake8-type-checking
    "RUF",    # Ruff-specific rules
]
ignore = [
    "E501",    # line too long (handled by formatter)
    "B008",    # do not perform function calls in argument defaults
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "D", "ANN"]  # 允许 assert, 不要求 docstring
"scripts/**" = ["T20"]  # 允许 print 语句

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

## Ty 类型检查配置

```toml
# pyproject.toml 中的 ty 配置
[tool.ty]
python-version = "3.10"
strict = true
[tool.ty.per-file-ignores]
"tests/**" = ["possibly-undefined", "unused-ignore-comment"]
```

toml 

## 常⽤ Makefile 命令


# 根⽬录 Makefile


```makefile
.PHONY: lint format test type-check 
```


lint:


```batch
@echo "Running ruff linter..."
ruff check .
@echo "Running ty type checker..."
ty check . 
```


format:


```batch
@echo "Formatting code..."
ruff format .
ruff check --fix . 
```


test:


```batch
@echo "Running unit tests..."
pytest tests/unit_tests -v --tb=short
@echo "Running integration tests..."
pytest tests/integration_tests -v --tb=short 
```


type-check:


```txt
@echo "Running type checks..." ty check. 
```

```makefile
all: format lint type-check test 
```

## 代码质量规则

公共 API：完整类型标注与返回值类型。

⽂档字符串：Google ⻛格（含 Args 等）；类型信息放在 签名 中，避免在 docstring 重复默认可从签名读出的默认值。

语⾔：美式英语（如 behavior，⾮ behaviour）。

内联代码格式：禁⽌ Sphinx 双反引号 code ``；在 docstring/注释中使⽤ **单反引号**code` ``。

. API 演进：新增参数宜为 仅限关键字（ *, new_param= . ），利于向后兼容。

## Python 代码规范示例

## 类型标注规范


# 正确：完整类型标注


```python
def process_agent_response(
    response: AgentResponse,
    *, 
    max_tokens: int = 4096,
    temperature: float = 0.7,
) → ProcessedResult:
    """处理智能体响应。

    Args:
    response: 原始响应对象。
    max_tokens: 最大 token 数量。
    temperature: 生成温度。

    Returns:
    处理后的结果对象。
    """
    pass

# 错误：缺少类型标注
def process_agent_response(response, max_tokens=4096, temperature=0.7):
    pass
```

python 

## ⽂档字符串规范


# 正确：Google ⻛格⽂档字符串


```python
def create_deep_agent(
    model: str,
    tools: list[Tool] | None = None,
    *, 
    system_prompt: str | None = None,
) → Agent:
    """创建深度智能体实例。
```

python 

```python
Args:
    model: 模型标识符，如 "anthropic/claude-3-5-sonnet-20241022"。
    tools: 可用工具列表，None 表示使用默认工具集。
    system_prompt: 自定义系统提示，None 使用默认提示。

Returns:
    配置好的智能体实例。

Raises:
    ValueError: 当模型标识符格式错误时。
    AuthenticationError: 当 API 密钥无效时。
    """
    pass

# 错误：Sphinx 风格文档字符串
def create_deep_agent(model, tools=None, system_prompt=None):
    """创建深度智能体实例。

    :param model: 模型标识符
    :param tools: 可用工具列表
    :param system_prompt: 自定义系统提示
    :returns: 配置好的智能体实例
    """
    pass
```

## 命名规范

# 正确：美式英语命名

```python
class FileSystemMiddleware:
    def organize_files(self) → None:
    pass

    def recognize_patterns(self) → list[str]:
    pass 
```

# 错误：英式英语或⾮标准命名

```python
class FileSystemMiddleware:
    def organise_files(self) → None:  # 英式拼写
    pass
```

python 

```python
def recognise_patterns(self) → list[str]: # 英式拼写
    pass
```

## TypeScript 代码规范示例

## 类型定义规范

```typescript
// 正确：明确的接口定义
interface AgentConfig {
    readonly model: string;
    readonly tools?: Tool[];
    readonly systemPrompt?: string;
    readonly maxTokens?: number;
}

// 正确：函数类型标注
async function createAgent(config: AgentConfig): Promise<Agent> {
    // 实现
}

// 错误：any 类型使用
async function createAgent(config: any): Promise<any> {
    // 实现
}
```


typescript


## 导⼊规范


/ 正确：按类型分组导⼊


```typescript
import { Agent, Tool } from './types';
import { createAgent } from './factory';
import { validateConfig } from './utils';
// 错误：混合导入或默认导入
import Agent, { Tool, createAgent, validateConfig } from './module';
```


typescript


## 安全约束

禁⽌对⽤户可控输⼊使⽤ eval exec pickle。

不可信代码须在 沙箱边界 内执⾏（与 SandboxBackendProtocol 、合作伙伴沙箱包的设计⼀致）。

异常处理避免 裸 except: ；错误信息宜使⽤明确变量（如 msg ）。

## 安全实践详细规范

## 输⼊验证


# 正确：严格的输⼊验证



python


```python
from pydantic import BaseModel, validator

class AgentInput(BaseModel):
    prompt: str
    max_tokens: int = 4096

    @validator('prompt')
    def validate_prompt(cls, v):
    if len(v) > 100000:
    raise ValueError('Prompt too long')
    if '<script>' in v.lower():
    raise ValueError('Invalid content detected')
    return v

    @validator('max_tokens')
    def validate_max_tokens(cls, v):
    if v < 1 or v > 100000:
    raise ValueError('max_tokens must be between 1 and 100000')
    return v 
```


# 错误：直接使⽤⽤户输⼊


```python
def process_input(user_input: str):
    result = eval(user_input) # 危险!
    return result
```

## 危险函数使⽤规范

```python
# 错误：使用 eval/exec 处理用户输入
def execute_code(code: str):
    return eval(code)  # 禁止！

# 正确：使用沙箱执行
from deepagents.backends import SandboxBackend

async def execute_code_safely(code: str):
    sandbox = SandboxBackend()
    return await sandbox.execute(code)

# 错误：使用 pickle 反序列化不可信数据
def load_data(data: bytes):
    return pickle.loads(data)  # 禁止！

# 正确：使用安全的序列化格式
import json

def load_data_safely(data: str):
    return json.loads(data)
```

python 

## 异常处理规范

```python
# 错误：裸 except 和不明确的错误信息
try:
    result = risky_operation()
except:  # 禁止裸 except
    return "Error occurred"  # 不明确的错误信息
# 正确：明确的异常处理
try:
    result = risky_operation()
except ValueError as e:
    msg = f"Invalid input: {e}"
    logger.error(msg)
    return {"error": msg}
except ConnectionError as e:
    msg = f"Connection failed: {e}"
```

python 

```python
logger.error(msg)
return {"error": msg}
except Exception as e:
    msg = f"Unexpected error: {type(e).__name__}: {e}"
    logger.exception(msg)
    return {"error": msg} 
```


密钥和敏感信息处理


```python
# 错误：硬编码密钥
API_KEY = "sk-1234567890abcdef" # 禁止！
# 正确：使用环境变量
import os
API_KEY = os.environ.get("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable not set")
# 错误：日志中记录敏感信息
logger.info(f"User password: {password}") # 禁止！
# 正确：脱敏处理
logger.info(f"User login attempt for user_id: {user_id}")
```

## CI 配置示例


GitHub Actions ⼯作流配置


```yaml
# .github/workflows/ci.yml
name: CI

on:
    push:
    branches: [main, develop] 
```

```yaml
pull_request:
    branches: [main]

jobs:
    lint:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python
    uses: actions/setup-python@v5
    with:
    python-version: "3.11"
    - name: Install uv
    uses: astral-sh/setup-uv@v3
    - name: Install dependencies
    run: uv sync
    - name: Run ruff lint
    run: uv run ruff check .
    - name: Run ruff format check
    run: uv run ruff format --check .
    - name: Run ty type check
    run: uv run ty check .
test:
    runs-on: ubuntu-latest
    strategy:
    matrix:
    python-version: ["3.10", "3.11", "3.12"]
steps:
    - uses: actions/checkout@v4
    - name: Set up Python ${{ matrix.python-version }}
    uses: actions/setup-python@v5
    with:
    python-version: ${{ matrix.python-version }} 
```

```yaml
- name: Install uv
    uses: astral-sh/setup-uv@v3

- name: Install dependencies
run: uv sync

- name: Run unit tests
run: uv run pytest tests/unit_tests -v --tb=short --cov=deepagents --cov-report=xml

- name: Run integration tests
if: github.event_name = 'push'
env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
run: uv run pytest tests/integration_tests -v --tb=short

- name: Upload coverage
if: matrix.python-version = "3.11"
uses: codecov/codecov-action@v4
with:
    file: ./coverage.xml

security:
runs-on: ubuntu-latest
steps:
- uses: actions/checkout@v4

- name: Run safety check
uses: pyupio/safety@v2
with:
    api-key: ${{ secrets.SAFETY_API_KEY }}
- name: Run bandit security linter
run: |
    pip install bandit
    bandit -r libs/deepagents/ -ll -ii 
```

## PR Lint 配置

yaml 

```yaml
# .github/workflows/pr_lint.yml
name: PR Lint

on:
    pull_request:
    types: [opened, edited, synchronize]

jobs:
    lint:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Check PR title format
    uses: amannn/action-semantic-pull-request@v5
    env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }} with:
    types: |
    feat
    fix
    docs
    style
    refactor
    perf
    test
    build
    ci
    chore
    revert
    requireScope: false
    subjectPattern:^[a-z].+$
    subjectPatternError: |
    PR title "{subject}" does not match the required pattern.
    PR title must start with a lowercase letter. 
```

## Makefile 集成 CI 命令

```txt
# 本地运行 CI 检查
.PHONY: ci-local

ci-local: format lint type-check test
@echo "All CI checks passed!"
# 生成测试覆盖率报告
.PHONY: coverage

coverage:
    pytest tests/unit_tests --cov=deepagents --cov-report=html --cov-report=term-missing
    @echo "Coverage report generated in htmlcov/" 

# 安全扫描
.PHONY: security-scan

security-scan:
    safety check
    bandit -r libs/deepagents/ -ll -ii
    @echo "Security scan completed"
```


测试布局


<table><tr><td>目录</td><td>约定</td></tr><tr><td>tests/unit_tests/</td><td>快速、禁止网络依赖。</td></tr><tr><td>tests/integration_tests/</td><td>允许网络;可能需要 API Key。</td></tr><tr><td>async</td><td>包内 pyproject.toml 通常设 asyncio_mode = &quot;auto&quot;,不要在单个测试上冗余加 @pytest.mark.asyncio。</td></tr><tr><td>结构</td><td>测试目录 镜像源码结构,便于定位。</td></tr><tr><td>风格</td><td>少 mock,多测真实实现;避免把业务逻辑复制进测试。</td></tr></table>

## 公共接口稳定性

修改前检查符号是否在 _init _.py 导出。

搜索测试与示例中的⽤法；任意签名变动都应视为⾼⻛险并告知维护者。

实验能⼒⽤ docstring 显著标注（如 MkDocs Material 的 !!! warning 类提示）。

## 本地开发：可编辑依赖

monorepo 内常⽤ [tool.uv.sources] 指向 path + editable，使 SDK 与各集成包联调时⽆需反复安装 wheel。

## 设计取舍

ruff ⼀体化：降低配置分散与格式化/检查不⼀致问题。

测试⽬录约定：从路径即可判断能否离线跑，便于 CI 分层。

. keyword-only 新参数：在快速迭代期仍尽量保护下游调⽤⽅。

## 小结

质量保障由 AGENTS.md 规范 + ruff/ty/pytest ⼯具链 + 测试⽬录约定 + 安全清单 共同构成；贡献前应先读 AGENTS.md 全⽂，再对照⽬标包的 pyproject.toml 微调。


文档来源与路径


<table><tr><td>类型</td><td>路径</td></tr><tr><td>评估套件说明</td><td>libs/evals/README.md</td></tr><tr><td>评估测试根目录</td><td>libs/evals/tests/evals/</td></tr><tr><td>核心工具</td><td>libs/evals/tests/evals/utils.py (run_agent、TrajectoryScorer 等)</td></tr><tr><td>分类定义</td><td>libs/evals/deepagents_evals/categories.json</td></tr><tr><td>分类漂移测试</td><td>libs/evals/tests/unit_tests/test_category_tagging.py</td></tr><tr><td>目录漂移测试</td><td>libs/evals/tests/unit_tests/test_eval_catalog.py</td></tr><tr><td>评估目录</td><td>libs/evals/EVAL_CATALOG.md (自动生成)</td></tr></table>

## 概述

Deep Agents evals 在 真实 LLM 下端到端运⾏智能体，并对 轨迹（步骤数、⼯具调⽤、最终⽂本、⽂件状态等）断⾔。框架以 LangSmith 记录运⾏；本地/CI 需配置 tracing 与 API Key（详⻅libs/evals/README.md ）。

## 两层断⾔模型：

.success( .) ：必须通过的正确性断⾔（硬失败）。

. .expect( .) ：效率或形状期望（软指标，记录但不导致测试失败）。

## 新建评估用例：五步流程

1. 使⽤ @pytest.mark.langsmith 标记测试函数（与 langsmith.testing 集成，⽤于⽇志与报告）。

2. 通过 fixture 注⼊ model: BaseChatModel 。

3. 使⽤ create_deep_agent(model=model, .) 构造智能体（可按场景附加 tools、middleware、backend 等）。

4. 调⽤ run_agent(agent, model=model, query= ., scorer= .) 执⾏⼀次评估回合。

5. 在 TrajectoryScorer 链上组合 .success( .) 与 .expect( .) 。

## 示例代码

```python
@pytest.mark.langsmith
def test_example(model: BaseChatModel) → None:
    agent = create_deep_agent(model=model)
    run_agent(
    agent,
    model=model,
    query="What is 2 + 2?",
    scorer=(TrajectoryScorer())
    .expect(agent_steps=1)
    .success(final_text_contains("4"))
    ),
    ) 
```

语义判分可结合 tests/evals/llm_judge.py 中的 llm_judge 等（当⼦串匹配不⾜时）。

## 新增评估分类

1. 编辑 deepagents_evals/categories.json 增加分类（若涉及雷达图能⼒维度，同时维护radar_categories 等相关字段）。

2. 在对应测试上标注 @pytest.mark.eval_category("name")

3. 在 tests/unit_tests/test_category_tagging.py 的 EXPECTED_CATEGORY_MODULES 中登记：该分类应对应哪些 eval 模块⽂件，防⽌磁盘上测试与声明脱节。

4. 运⾏ make test （或包内等价命令），让 分类漂移检测 与单元测试捕获遗漏。

## 评估目录（Eval catalog）

EVAL_CATALOG.md ：通过 make eval-catalog ⾃动⽣成，按分类列出各 eval 及链接/路径。

. 漂移防护： tests/unit_tests/test_eval_catalog.py 在 CI 中若发现⽬录 与⽣成结果不⼀致则 失败，强制贡献者更新⽬录。

## 运行评估

在 libs/evals/ 下： make evals 或按 README 使⽤ uv run -group test pytesttests/evals 。

过滤：

. -eval-category ：按分类筛选（可多次传⼊）。

. -model ：指定模型（与 conftest.py 中 CLI 选项⼀致）。

## 模块关系简图

```txt
categories.json → 分类元数据 / 雷达维度
    ▲
    | @pytest.mark.eval_category
    |
    tests/evals/*.py → run_agent + TrajectoryScorer
```

text 

```txt
| 
→ utils.py (核心框架)
test_category_tagging.py → EXPECTED_CATEGORY_MODULES 与磁盘一致性
test_eval_catalog.py → EVAL_CATALOG.md 新鲜度
```

## 设计取舍

成功 vs 期望分离：避免把「步数略多」这类软指标与正确性混为⼀谈，报告仍可看效率⽐率。

分类单源： categories.json 服务雷达、聚合脚本与测试，减少三处各写⼀份的漂移。

⽬录⽣成 + 测试锁死：让⽂档型 EVAL_CATALOG.md 不会悄悄过期。

## 小结

新 eval 遵循 langsmith 标记 → model fixture → create_deep_agent → run_agent → Scorer 固定套路；新分类要改 JSON + marker + EXPECTED_CATEGORY_MODULES； make eval-catalog 维护 EVAL_CATALOG.md ，并由 test_eval_catalog.py 守⻔。

## 文档来源与路径

<table><tr><td>类型</td><td>路径</td></tr><tr><td>示例索引</td><td>examples/README.md</td></tr><tr><td>各示例子目录</td><td>examples/*/ (各自 README.md、pyproject.toml、uv.lock)</td></tr></table>

## 概述

examples/ 收集基于 Deep Agents 可运⾏的应⽤形态：从 深度检索、内容⽣产 到 异步⼦智能体服务、GPU 场景 等。每个示例 独⽴依赖锁⽂件，便于复制到⾃⼰的环境；共同点是以

create_deep_agent() 为核⼼⼊⼝，并按领域挂载 ⾃定义 tools、system prompt、skills / ⼦智能体 或 ⾃定义 backend。

官⽅索引另含 text-to-sql-agent （⾃然语⾔转 SQL）；本书表侧重下列与⽤户指定清单⼀致的项⽬，并在⽂末简要对照索引中的其他示例。

## 示例项目关系图

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/97d1b029-1348-47aa-8a07-cdafd8905b7f/b3fa0079cbe55652879a692d1eebc04f9a164974073b2557ec017f0510259748.jpg)


## 各示例概要

## 1. deep_research/ —深度研究智能体

<table><tr><td>项</td><td>说明</td></tr><tr><td>包布局</td><td>research_agent/ 子包(工具、提示常量等)</td></tr><tr><td>入口</td><td>根目录 agent.py 与 research_agent/ 内模块协同</td></tr><tr><td>能力</td><td>网络检索(如 Tavily)、并行子智能体、反思/策略 等多步研究流程</td></tr><tr><td>模式</td><td>create_deep_agent + 自定义 tools + 领域 prompts(见 research_agent/prompts.py 等)</td></tr></table>

## 2. content-builder-agent/ —内容构建智能体

<table><tr><td>项</td><td>说明</td></tr><tr><td>文档</td><td>自带 AGENTS.md,约定该项目内的 AI/人协作说明</td></tr><tr><td>能力</td><td>博客、LinkedIn、推文等内容形态,结合 memory、skills、subagents(见 subagents.yaml、skills/)</td></tr><tr><td>模式</td><td>展示长内容工作流与多技能组合</td></tr></table>

## 3. async-subagent-server/ —异步⼦智能体服务

<table><tr><td>项</td><td>说明</td></tr><tr><td>关键文件</td><td>server.py、supervisor.py;test_server.py用于测试服务端行为</td></tr><tr><td>能力</td><td>远程异步子智能体 模式:服务端托管 agent,客户端异步交互</td></tr><tr><td>模式</td><td>与「本地单进程 CLI」相对,强调 网络边界上的 agent hosting</td></tr></table>

## 4. nvidia_deep_agent/ — GPU 加速场景

<table><tr><td>项</td><td>说明</td></tr><tr><td>源码</td><td>src/agent.py、src/backend.py、src/prompts.py、src/tools.py</td></tr><tr><td>文档</td><td>src/AGENTS.md 提供 NVIDIA/GPU 相关项目内指引</td></tr><tr><td>能力</td><td>与GPU 计算栈 结合的 deep agent(如 RAPIDS/cuML 等技能说明见skills/)</td></tr><tr><td>模式</td><td>自定义 backend + tools + prompts 三位一体,贴近企业 GPU 流水线</td></tr></table>

## 5. downloading_agents/ —「下载即⽤」智能体

<table><tr><td>项</td><td>说明</td></tr><tr><td>能力</td><td>强调智能体即 文件夹/压缩包:下载、解压、配置后即可运行</td></tr><tr><td>模式</td><td>教学意义:分发与安装体验,而非单一算法技巧</td></tr></table>

## 6. ralph_mode/ — Ralph 模式

<table><tr><td>项</td><td>说明</td></tr><tr><td>入口</td><td>ralph_mode.py</td></tr><tr><td>能力</td><td>自主循环:每轮全新上下文,依赖文件系统持久化状态与产出</td></tr><tr><td>模式</td><td>与「单会话长上下文」对照,突出迭代+外存的代理范式</td></tr></table>

## examples/README.md 的对照

<table><tr><td>README 列表示例</td><td>说明</td></tr><tr><td>text-to-sql-agent/</td><td>自然语言转 SQL、Chinook 演示库、技能化工作流;本书未展开,但结构与 deep_research 同属「领域工具 + planning」一类。</td></tr></table>

## 跨示例的共性模式

1. 独⽴⼯程：各⾃ pyproject.toml + uv.lock ，版本范围常 pin 到 deepagents ⼩版本区间（⻅ README 贡献指南）。

2. 核⼼构造： create_deep_agent() 统⼀创建图/智能体。

3. 扩展点：

. tools= ：领域 API、检索、⽂件、SQL 等。

系统提示 / prompts：把⻆⾊、输出格式、安全约束写死到提示层。

Skills / Subagents（部分示例）：⽤⽂件系统约定（ SKILL.md subagents.yaml ）组织复杂能⼒。

⾃定义 backend（如 NVIDIA 示例）：对接特殊运⾏环境或数据⾯。

## 设计取舍 （架构视角）

. 示例之间不共享⼀个巨型依赖：每个示例锁⾃⼰的 uv.lock ，避免「跑通 A 示例却破坏 B 示例」的依赖地狱。

AGENTS.md 下沉到⼦项⽬：在 monorepo 全局 AGENTS.md 之外，再给 ⾼专⽤度示例（content-builder、nvidia）提供 局部规范，降低⽆关噪⾳。

服务器型示例单独成⽬录： async-subagent-server 与 CLI/脚本式示例分离，读者可按部署模型选型。

## 小结

examples/ 是 Deep Agents 从 API 到产品形态 的桥梁：以 create_deep_agent 为轴，通过tools、prompts、skills、backend、服务化 等组合表达不同场景；阅读时建议 先读该⽬录README.md ，再进⼊各⼦⽬录的 README.md 与 AGENTS.md
````


文档来源与路径


<table><tr><td>类型</td><td>路径</td></tr><tr><td>GitHub 工作流</td><td>.github/workflows/</td></tr><tr><td>脚本与自动化</td><td>.github/scripts/</td></tr><tr><td>发布说明</td><td>.github/RELEASING.md</td></tr><tr><td>Release Please 配置(仓库根)</td><td>release-please-config.json、.release-please-manifest.json</td></tr><tr><td>PR 模板与标签</td><td>.github/PULL_REQUEST_TEMPLATE.md、pr_label.yml、pr-labeler.js、pr-labeler-config.json</td></tr></table>

## 概述

Deep Agents monorepo 使⽤ GitHub Actions 驱动 持续集成（按变更路径选择性跑各包）、⾏为评估（Evals）、Harbor / Terminal Bench 类基准、版本与可选依赖⼀致性检查，以及基于release-please 的 CLI 发布流⽔线。辅助逻辑集中在 .github/scripts/ 。

## CI/CD 工作流图

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/97d1b029-1348-47aa-8a07-cdafd8905b7f/b5c2fa15715ca00f56d5c533a01d25f1c6970fa2474c646f1eeb4bd3cc59a14f.jpg)


## 主要工作流（ .github/workflows/ ）

## CI（ ci.yml 及复⽤⼦⼯作流）

. 触发： pull_request 、 push ⾄ main 、 merge_group 等。、

. ⾏为要点：

通过 paths filter 检测 libs/deepagents libs/cli 、 libs/evals 及各 partnersrepl 等是否变更，仅对受影响包跑 lint / 单元测试；SDK 变更会连带触发 CLI 测试。

与 _lint.yml _test.yml 等复⽤⼯作流配合，完成 ruff / ty / pytest 等质量⻔禁。

并发：同⼀ workflow + ref 分组， cancel-in-progress 取消冗余运⾏。

## Evals（ evals.yml ）

定位：对 真实 LLM 跑 libs/evals 下的⾏为评估（需 LANGSMITH_* 及各⼚商 API Key 等secrets）。

. 模型选择：⼯作流 inputs 提供 预设集合 与 单模型 规格；预设定义可参考libs/evals/MODEL_GROUPS.md 。

矩阵来源：与 .github/scripts/models.py ⽣成的 JSON 矩阵配合（⻅下⽂「模型矩阵」）。

Eval 并发：按 provider 分组的 concurrency，同⼀提供商上的多个 job 串⾏排队，不同提供商并⾏，减轻速率限制与配额冲突（详⻅ libs/evals/README.md 中「CI concurrency」）。

## Harbor（ harbor.yml ）

定位：Terminal Bench 等基准场景的运⾏（与 eval 体系共享模型注册脚本思路，环境变量侧使⽤ HARBOR_MODELS 等）。

## Release / release-please（ release.yml 、 release-please.yml ）

. release-please：根据 Conventional Commits 分析变更，打开/更新 发布 PR，合并后触发PyPI 发布与 GitHub Release（细节以 .github/RELEASING.md 为准）。

## SDK pin 检查（ check_sdk_pin.yml 等）

⽬的：保证 CLI 等对 SDK 的 版本钉选（pin） 与仓库策略⼀致，避免发版时依赖版本漂移。

## 其他质量⻔禁

. check_versions.yml ：配合 check_version_equality.py 。

. check_extras_sync.yml ：配合 check_extras_sync.py 。

. check_lockfiles.yml ：锁⽂件⼀致性。

. pr_lint.yml ：PR 标题等符合约定式提交与 scope。

auto-label-by-package.yml 、 pr_labeler.yml 、 pr_labeler_backfill.yml ：PR ⾃动打标签；脚本实现⻅ .github/scripts/pr-labeler.js 与 pr-labeler-config.json 。

## release-please-config.json 与多包发布

根⽬录 release-please-config.json 声明 changelog 分段、PR 标题模板、tag 规则等。当前仓库中 packages 映射以 libs/cli （ deepagents-cli ）为主：包含 pyproject.toml 与deepagents_cli/_version.py 等 extra-files，由 release-please 统⼀改版本号与CHANGELOG.md 。

说明：配置结构 ⽀持扩展多个路径键（每个 lib ⼀段）；若未来增加更多 PyPI 包，可在同⼀⽂件的 packages 下追加条⽬，并配合 .release-please-manifest.json 维护各路径版本。请以仓库内实际 JSON 为准。

## 版本一致

性： .github/scripts/check_version_equality.py

作⽤：确保 pyproject.toml 中的版本 与 _version.py 等单⼀真源 对 deepagents、cli 等指定包 保持⼀致，防⽌发布物与导⼊版本字符串不⼀致。

## 可选依赖同

步： .github/scripts/check_extras_sync.py

作⽤：校验各包 optional dependency groups / extras 在 monorepo 内 声明同步，避免⽂档或元数据与可安装 extras 漂移。

## 模型矩阵： .github/scripts/models.py

Model 具名元组： spec （如 anthropic:claude-sonnet-4-6 ）+ groups （frozenset，标签含 eval:* harbor:* 等）。

REGISTRY 全量模型清单；预设集合通过 _EVAL_PRESETS _HARBOR_PRESETS （及⽂档中的EVAL_MODELS HARBOR_MODELS 环境变量语义）解析为 并⾏矩阵 JSON，供 Actions 使⽤。

. 调⽤⽅式（脚本注释摘要）：

. python .github/scripts/models.py eval — 读取 EVAL_MODELS

## Eval CI 并发（再述）

同 provider：共享 concurrency group，第⼆个 job 等待第⼀个。

跨 provider：可 并⾏，提⾼吞吐并分散配额⻛险。

## PR 标签与贡献体验

pr-labeler.js + pr-labeler-config.json 按规则为 PR ⾃动加标签，便于筛选与发布说明归类。

PULL_REQUEST_TEMPLATE.md ：引导贡献者填写 AI 辅助声明、测试说明等（与 AGENTS.md 中PR 准则呼应）。

## 设计取舍

. 变更敏感 CI：仅测改动相关包，缩短反馈时间；核⼼ SDK 变更仍拉通 CLI，避免集成断裂。

脚本单源化模型列表： models.py 避免在 YAML 中⼿写冗⻓矩阵，降低 eval 与 harbor 分叉⻛险。

release-please 与版本脚本双保险：⾃动化发版 + CI 版本相等检查，减少⼈为漏改。

## 小结

CI/CD 以 .github/workflows/ 为⼊⼝，脚本层（ check_version_equality.py 、check_extras_sync.py 、 models.py 等） 承担可复⽤策略；发布以 release-please 与.github/RELEASING.md 为权威流程说明。


文档来源与路径


<table><tr><td>类型</td><td>路径</td></tr><tr><td>全局开发指南</td><td>AGENTS.md (仓库根目录)</td></tr><tr><td>各包工具配置</td><td>各 libs/*/pyproject.toml 中的 [tool.ruff]、[tool.ty]、[tool.pytest.ini_options] 等</td></tr></table>

## 概述

AGENTS.md 定义 Deep Agents Python monorepo 的架构认知、⼯具链、提交与 PR 规范、代码质量与安全红线、测试布局 以及 公共 API 稳定性 要求。本⽂档提炼其要点，便于写书或onboarding 时快速对⻬。

## 提交与 PR 规范

## Conventional Commits

PR 标题建议符合 约定式提交，类型与 scope 以 .github/workflows/pr_lint.yml 为准。

. 示例（ AGENTS.md ）：

feat(sdk): add new chat completion feature 

fix(cli): resolve type hinting issue 

. chore(evals): update infrastructure dependencies 

⼤⼩写：除专有名词外，标题倾向 ⼩写。

## AI 辅助贡献

PR 描述中需 声明 AI 如何参与；说明变更动机（「为什么」）与 需重点⼈⼯审查 的区域。


工具链


<table><tr><td>工具</td><td>用途</td></tr><tr><td>uv</td><td>依赖与虚拟环境管理;各 libs/ 包自有 pyproject.toml / uv.lock。</td></tr><tr><td>make</td><td>聚合常用命令(make test、make lint、make format等,以根与各包 Makefile为准)。</td></tr><tr><td>ruff</td><td>Lint + 格式化(替代 flake8、black、isort 等分散工具)。</td></tr><tr><td>ty</td><td>静态类型检查。</td></tr><tr><td>pytest</td><td>测试运行框架。</td></tr></table>

## 抑制 ruff 规则

优先⾏内 # noqa: RULE ：精确到⾏，避免掩盖同⽂件其他问题。

per-file-ignores ：仅⽤于 整类⽂件策略（如 tests/** 不要求 docstring、允许assert ），不为单⾏例外滥⽤。

## Ruff 配置示例

```toml
# pyproject.toml 中的 ruff 配置
[tool.ruff]
target-version = "py310"
line-length = 88
[tool.ruff.lint]
```

toml 

```toml
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "B",    # flake8-bugbear
    "C4",    # flake8-comprehensions
    "UP",    # pyupgrade
    "SIM",    # flake8-simplify
    "TCH",    # flake8-type-checking
    "RUF",    # Ruff-specific rules
]
ignore = [
    "E501",    # line too long (handled by formatter)
    "B008",    # do not perform function calls in argument defaults
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "D", "ANN"]  # 允许 assert, 不要求 docstring
"scripts/**" = ["T20"]  # 允许 print 语句

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

## Ty 类型检查配置

```toml
# pyproject.toml 中的 ty 配置
[tool.ty]
python-version = "3.10"
strict = true
[tool.ty.per-file-ignores]
"tests/**" = ["possibly-undefined", "unused-ignore-comment"]
```

toml 

## 常⽤ Makefile 命令


# 根⽬录 Makefile


```makefile
.PHONY: lint format test type-check 
```


lint:


```batch
@echo "Running ruff linter..."
ruff check .
@echo "Running ty type checker..."
ty check . 
```


format:


```batch
@echo "Formatting code..."
ruff format .
ruff check --fix . 
```


test:


```batch
@echo "Running unit tests..."
pytest tests/unit_tests -v --tb=short
@echo "Running integration tests..."
pytest tests/integration_tests -v --tb=short 
```


type-check:


```txt
@echo "Running type checks..." ty check. 
```

```makefile
all: format lint type-check test 
```

## 代码质量规则

公共 API：完整类型标注与返回值类型。

⽂档字符串：Google ⻛格（含 Args 等）；类型信息放在 签名 中，避免在 docstring 重复默认可从签名读出的默认值。

语⾔：美式英语（如 behavior，⾮ behaviour）。

内联代码格式：禁⽌ Sphinx 双反引号 code ``；在 docstring/注释中使⽤ **单反引号**code` ``。

. API 演进：新增参数宜为 仅限关键字（ *, new_param= . ），利于向后兼容。

## Python 代码规范示例

## 类型标注规范


# 正确：完整类型标注


```python
def process_agent_response(
    response: AgentResponse,
    *, 
    max_tokens: int = 4096,
    temperature: float = 0.7,
) → ProcessedResult:
    """处理智能体响应。

    Args:
    response: 原始响应对象。
    max_tokens: 最大 token 数量。
    temperature: 生成温度。

    Returns:
    处理后的结果对象。
    """
    pass

# 错误：缺少类型标注
def process_agent_response(response, max_tokens=4096, temperature=0.7):
    pass
```

python 

## ⽂档字符串规范


# 正确：Google ⻛格⽂档字符串


```python
def create_deep_agent(
    model: str,
    tools: list[Tool] | None = None,
    *, 
    system_prompt: str | None = None,
) → Agent:
    """创建深度智能体实例。
```

python 

```python
Args:
    model: 模型标识符，如 "anthropic/claude-3-5-sonnet-20241022"。
    tools: 可用工具列表，None 表示使用默认工具集。
    system_prompt: 自定义系统提示，None 使用默认提示。

Returns:
    配置好的智能体实例。

Raises:
    ValueError: 当模型标识符格式错误时。
    AuthenticationError: 当 API 密钥无效时。
    """
    pass

# 错误：Sphinx 风格文档字符串
def create_deep_agent(model, tools=None, system_prompt=None):
    """创建深度智能体实例。

    :param model: 模型标识符
    :param tools: 可用工具列表
    :param system_prompt: 自定义系统提示
    :returns: 配置好的智能体实例
    """
    pass
```

## 命名规范

# 正确：美式英语命名

```python
class FileSystemMiddleware:
    def organize_files(self) → None:
    pass

    def recognize_patterns(self) → list[str]:
    pass 
```

# 错误：英式英语或⾮标准命名

```python
class FileSystemMiddleware:
    def organise_files(self) → None:  # 英式拼写
    pass
```

python 

```python
def recognise_patterns(self) → list[str]: # 英式拼写
    pass
```

## TypeScript 代码规范示例

## 类型定义规范

```typescript
// 正确：明确的接口定义
interface AgentConfig {
    readonly model: string;
    readonly tools?: Tool[];
    readonly systemPrompt?: string;
    readonly maxTokens?: number;
}

// 正确：函数类型标注
async function createAgent(config: AgentConfig): Promise<Agent> {
    // 实现
}

// 错误：any 类型使用
async function createAgent(config: any): Promise<any> {
    // 实现
}
```


typescript


## 导⼊规范


/ 正确：按类型分组导⼊


```typescript
import { Agent, Tool } from './types';
import { createAgent } from './factory';
import { validateConfig } from './utils';
// 错误：混合导入或默认导入
import Agent, { Tool, createAgent, validateConfig } from './module';
```


typescript


## 安全约束

禁⽌对⽤户可控输⼊使⽤ eval exec pickle。

不可信代码须在 沙箱边界 内执⾏（与 SandboxBackendProtocol 、合作伙伴沙箱包的设计⼀致）。

异常处理避免 裸 except: ；错误信息宜使⽤明确变量（如 msg ）。

## 安全实践详细规范

## 输⼊验证


# 正确：严格的输⼊验证



python


```python
from pydantic import BaseModel, validator

class AgentInput(BaseModel):
    prompt: str
    max_tokens: int = 4096

    @validator('prompt')
    def validate_prompt(cls, v):
    if len(v) > 100000:
    raise ValueError('Prompt too long')
    if '<script>' in v.lower():
    raise ValueError('Invalid content detected')
    return v

    @validator('max_tokens')
    def validate_max_tokens(cls, v):
    if v < 1 or v > 100000:
    raise ValueError('max_tokens must be between 1 and 100000')
    return v 
```


# 错误：直接使⽤⽤户输⼊


```python
def process_input(user_input: str):
    result = eval(user_input) # 危险!
    return result
```

## 危险函数使⽤规范

```python
# 错误：使用 eval/exec 处理用户输入
def execute_code(code: str):
    return eval(code)  # 禁止！

# 正确：使用沙箱执行
from deepagents.backends import SandboxBackend

async def execute_code_safely(code: str):
    sandbox = SandboxBackend()
    return await sandbox.execute(code)

# 错误：使用 pickle 反序列化不可信数据
def load_data(data: bytes):
    return pickle.loads(data)  # 禁止！

# 正确：使用安全的序列化格式
import json

def load_data_safely(data: str):
    return json.loads(data)
```

python 

## 异常处理规范

```python
# 错误：裸 except 和不明确的错误信息
try:
    result = risky_operation()
except:  # 禁止裸 except
    return "Error occurred"  # 不明确的错误信息
# 正确：明确的异常处理
try:
    result = risky_operation()
except ValueError as e:
    msg = f"Invalid input: {e}"
    logger.error(msg)
    return {"error": msg}
except ConnectionError as e:
    msg = f"Connection failed: {e}"
```

python 

```python
logger.error(msg)
return {"error": msg}
except Exception as e:
    msg = f"Unexpected error: {type(e).__name__}: {e}"
    logger.exception(msg)
    return {"error": msg} 
```


密钥和敏感信息处理


```python
# 错误：硬编码密钥
API_KEY = "sk-1234567890abcdef" # 禁止！
# 正确：使用环境变量
import os
API_KEY = os.environ.get("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable not set")
# 错误：日志中记录敏感信息
logger.info(f"User password: {password}") # 禁止！
# 正确：脱敏处理
logger.info(f"User login attempt for user_id: {user_id}")
```

## CI 配置示例


GitHub Actions ⼯作流配置


```yaml
# .github/workflows/ci.yml
name: CI

on:
    push:
    branches: [main, develop] 
```

```yaml
pull_request:
    branches: [main]

jobs:
    lint:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python
    uses: actions/setup-python@v5
    with:
    python-version: "3.11"
    - name: Install uv
    uses: astral-sh/setup-uv@v3
    - name: Install dependencies
    run: uv sync
    - name: Run ruff lint
    run: uv run ruff check .
    - name: Run ruff format check
    run: uv run ruff format --check .
    - name: Run ty type check
    run: uv run ty check .
test:
    runs-on: ubuntu-latest
    strategy:
    matrix:
    python-version: ["3.10", "3.11", "3.12"]
steps:
    - uses: actions/checkout@v4
    - name: Set up Python ${{ matrix.python-version }}
    uses: actions/setup-python@v5
    with:
    python-version: ${{ matrix.python-version }} 
```

```yaml
- name: Install uv
    uses: astral-sh/setup-uv@v3

- name: Install dependencies
run: uv sync

- name: Run unit tests
run: uv run pytest tests/unit_tests -v --tb=short --cov=deepagents --cov-report=xml

- name: Run integration tests
if: github.event_name = 'push'
env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
run: uv run pytest tests/integration_tests -v --tb=short

- name: Upload coverage
if: matrix.python-version = "3.11"
uses: codecov/codecov-action@v4
with:
    file: ./coverage.xml

security:
runs-on: ubuntu-latest
steps:
- uses: actions/checkout@v4

- name: Run safety check
uses: pyupio/safety@v2
with:
    api-key: ${{ secrets.SAFETY_API_KEY }}
- name: Run bandit security linter
run: |
    pip install bandit
    bandit -r libs/deepagents/ -ll -ii 
```

## PR Lint 配置

yaml 

```yaml
# .github/workflows/pr_lint.yml
name: PR Lint

on:
    pull_request:
    types: [opened, edited, synchronize]

jobs:
    lint:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Check PR title format
    uses: amannn/action-semantic-pull-request@v5
    env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }} with:
    types: |
    feat
    fix
    docs
    style
    refactor
    perf
    test
    build
    ci
    chore
    revert
    requireScope: false
    subjectPattern:^[a-z].+$
    subjectPatternError: |
    PR title "{subject}" does not match the required pattern.
    PR title must start with a lowercase letter. 
```

## Makefile 集成 CI 命令

```txt
# 本地运行 CI 检查
.PHONY: ci-local

ci-local: format lint type-check test
@echo "All CI checks passed!"
# 生成测试覆盖率报告
.PHONY: coverage

coverage:
    pytest tests/unit_tests --cov=deepagents --cov-report=html --cov-report=term-missing
    @echo "Coverage report generated in htmlcov/" 

# 安全扫描
.PHONY: security-scan

security-scan:
    safety check
    bandit -r libs/deepagents/ -ll -ii
    @echo "Security scan completed"
```


测试布局


<table><tr><td>目录</td><td>约定</td></tr><tr><td>tests/unit_tests/</td><td>快速、禁止网络依赖。</td></tr><tr><td>tests/integration_tests/</td><td>允许网络;可能需要 API Key。</td></tr><tr><td>async</td><td>包内 pyproject.toml 通常设 asyncio_mode = &quot;auto&quot;,不要在单个测试上冗余加 @pytest.mark.asyncio。</td></tr><tr><td>结构</td><td>测试目录 镜像源码结构,便于定位。</td></tr><tr><td>风格</td><td>少 mock,多测真实实现;避免把业务逻辑复制进测试。</td></tr></table>

## 公共接口稳定性

修改前检查符号是否在 _init _.py 导出。

搜索测试与示例中的⽤法；任意签名变动都应视为⾼⻛险并告知维护者。

实验能⼒⽤ docstring 显著标注（如 MkDocs Material 的 !!! warning 类提示）。

## 本地开发：可编辑依赖

monorepo 内常⽤ [tool.uv.sources] 指向 path + editable，使 SDK 与各集成包联调时⽆需反复安装 wheel。

## 设计取舍

ruff ⼀体化：降低配置分散与格式化/检查不⼀致问题。

测试⽬录约定：从路径即可判断能否离线跑，便于 CI 分层。

. keyword-only 新参数：在快速迭代期仍尽量保护下游调⽤⽅。

## 小结

质量保障由 AGENTS.md 规范 + ruff/ty/pytest ⼯具链 + 测试⽬录约定 + 安全清单 共同构成；贡献前应先读 AGENTS.md 全⽂，再对照⽬标包的 pyproject.toml 微调。


文档来源与路径


<table><tr><td>类型</td><td>路径</td></tr><tr><td>评估套件说明</td><td>libs/evals/README.md</td></tr><tr><td>评估测试根目录</td><td>libs/evals/tests/evals/</td></tr><tr><td>核心工具</td><td>libs/evals/tests/evals/utils.py (run_agent、TrajectoryScorer 等)</td></tr><tr><td>分类定义</td><td>libs/evals/deepagents_evals/categories.json</td></tr><tr><td>分类漂移测试</td><td>libs/evals/tests/unit_tests/test_category_tagging.py</td></tr><tr><td>目录漂移测试</td><td>libs/evals/tests/unit_tests/test_eval_catalog.py</td></tr><tr><td>评估目录</td><td>libs/evals/EVAL_CATALOG.md (自动生成)</td></tr></table>

## 概述

Deep Agents evals 在 真实 LLM 下端到端运⾏智能体，并对 轨迹（步骤数、⼯具调⽤、最终⽂本、⽂件状态等）断⾔。框架以 LangSmith 记录运⾏；本地/CI 需配置 tracing 与 API Key（详⻅libs/evals/README.md ）。

## 两层断⾔模型：

.success( .) ：必须通过的正确性断⾔（硬失败）。

. .expect( .) ：效率或形状期望（软指标，记录但不导致测试失败）。

## 新建评估用例：五步流程

1. 使⽤ @pytest.mark.langsmith 标记测试函数（与 langsmith.testing 集成，⽤于⽇志与报告）。

2. 通过 fixture 注⼊ model: BaseChatModel 。

3. 使⽤ create_deep_agent(model=model, .) 构造智能体（可按场景附加 tools、middleware、backend 等）。

4. 调⽤ run_agent(agent, model=model, query= ., scorer= .) 执⾏⼀次评估回合。

5. 在 TrajectoryScorer 链上组合 .success( .) 与 .expect( .) 。

## 示例代码

```python
@pytest.mark.langsmith
def test_example(model: BaseChatModel) → None:
    agent = create_deep_agent(model=model)
    run_agent(
    agent,
    model=model,
    query="What is 2 + 2?",
    scorer=(TrajectoryScorer())
    .expect(agent_steps=1)
    .success(final_text_contains("4"))
    ),
    ) 
```

语义判分可结合 tests/evals/llm_judge.py 中的 llm_judge 等（当⼦串匹配不⾜时）。

## 新增评估分类

1. 编辑 deepagents_evals/categories.json 增加分类（若涉及雷达图能⼒维度，同时维护radar_categories 等相关字段）。

2. 在对应测试上标注 @pytest.mark.eval_category("name")

3. 在 tests/unit_tests/test_category_tagging.py 的 EXPECTED_CATEGORY_MODULES 中登记：该分类应对应哪些 eval 模块⽂件，防⽌磁盘上测试与声明脱节。

4. 运⾏ make test （或包内等价命令），让 分类漂移检测 与单元测试捕获遗漏。

## 评估目录（Eval catalog）

EVAL_CATALOG.md ：通过 make eval-catalog ⾃动⽣成，按分类列出各 eval 及链接/路径。

. 漂移防护： tests/unit_tests/test_eval_catalog.py 在 CI 中若发现⽬录 与⽣成结果不⼀致则 失败，强制贡献者更新⽬录。

## 运行评估

在 libs/evals/ 下： make evals 或按 README 使⽤ uv run -group test pytesttests/evals 。

过滤：

. -eval-category ：按分类筛选（可多次传⼊）。

. -model ：指定模型（与 conftest.py 中 CLI 选项⼀致）。

## 模块关系简图

```txt
categories.json → 分类元数据 / 雷达维度
    ▲
    | @pytest.mark.eval_category
    |
    tests/evals/*.py → run_agent + TrajectoryScorer
```

text 

```txt
| 
→ utils.py (核心框架)
test_category_tagging.py → EXPECTED_CATEGORY_MODULES 与磁盘一致性
test_eval_catalog.py → EVAL_CATALOG.md 新鲜度
```

## 设计取舍

成功 vs 期望分离：避免把「步数略多」这类软指标与正确性混为⼀谈，报告仍可看效率⽐率。

分类单源： categories.json 服务雷达、聚合脚本与测试，减少三处各写⼀份的漂移。

⽬录⽣成 + 测试锁死：让⽂档型 EVAL_CATALOG.md 不会悄悄过期。

## 小结

新 eval 遵循 langsmith 标记 → model fixture → create_deep_agent → run_agent → Scorer 固定套路；新分类要改 JSON + marker + EXPECTED_CATEGORY_MODULES； make eval-catalog 维护 EVAL_CATALOG.md ，并由 test_eval_catalog.py 守⻔。

## 文档来源与路径

<table><tr><td>类型</td><td>路径</td></tr><tr><td>示例索引</td><td>examples/README.md</td></tr><tr><td>各示例子目录</td><td>examples/*/ (各自 README.md、pyproject.toml、uv.lock)</td></tr></table>

## 概述

examples/ 收集基于 Deep Agents 可运⾏的应⽤形态：从 深度检索、内容⽣产 到 异步⼦智能体服务、GPU 场景 等。每个示例 独⽴依赖锁⽂件，便于复制到⾃⼰的环境；共同点是以

create_deep_agent() 为核⼼⼊⼝，并按领域挂载 ⾃定义 tools、system prompt、skills / ⼦智能体 或 ⾃定义 backend。

官⽅索引另含 text-to-sql-agent （⾃然语⾔转 SQL）；本书表侧重下列与⽤户指定清单⼀致的项⽬，并在⽂末简要对照索引中的其他示例。

## 示例项目关系图

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-10/97d1b029-1348-47aa-8a07-cdafd8905b7f/b3fa0079cbe55652879a692d1eebc04f9a164974073b2557ec017f0510259748.jpg)


## 各示例概要

## 1. deep_research/ —深度研究智能体

<table><tr><td>项</td><td>说明</td></tr><tr><td>包布局</td><td>research_agent/ 子包(工具、提示常量等)</td></tr><tr><td>入口</td><td>根目录 agent.py 与 research_agent/ 内模块协同</td></tr><tr><td>能力</td><td>网络检索(如 Tavily)、并行子智能体、反思/策略 等多步研究流程</td></tr><tr><td>模式</td><td>create_deep_agent + 自定义 tools + 领域 prompts(见 research_agent/prompts.py 等)</td></tr></table>

## 2. content-builder-agent/ —内容构建智能体

<table><tr><td>项</td><td>说明</td></tr><tr><td>文档</td><td>自带 AGENTS.md,约定该项目内的 AI/人协作说明</td></tr><tr><td>能力</td><td>博客、LinkedIn、推文等内容形态,结合 memory、skills、subagents(见 subagents.yaml、skills/)</td></tr><tr><td>模式</td><td>展示长内容工作流与多技能组合</td></tr></table>

## 3. async-subagent-server/ —异步⼦智能体服务

<table><tr><td>项</td><td>说明</td></tr><tr><td>关键文件</td><td>server.py、supervisor.py;test_server.py用于测试服务端行为</td></tr><tr><td>能力</td><td>远程异步子智能体 模式:服务端托管 agent,客户端异步交互</td></tr><tr><td>模式</td><td>与「本地单进程 CLI」相对,强调 网络边界上的 agent hosting</td></tr></table>

## 4. nvidia_deep_agent/ — GPU 加速场景

<table><tr><td>项</td><td>说明</td></tr><tr><td>源码</td><td>src/agent.py、src/backend.py、src/prompts.py、src/tools.py</td></tr><tr><td>文档</td><td>src/AGENTS.md 提供 NVIDIA/GPU 相关项目内指引</td></tr><tr><td>能力</td><td>与GPU 计算栈 结合的 deep agent(如 RAPIDS/cuML 等技能说明见skills/)</td></tr><tr><td>模式</td><td>自定义 backend + tools + prompts 三位一体,贴近企业 GPU 流水线</td></tr></table>

## 5. downloading_agents/ —「下载即⽤」智能体

<table><tr><td>项</td><td>说明</td></tr><tr><td>能力</td><td>强调智能体即 文件夹/压缩包:下载、解压、配置后即可运行</td></tr><tr><td>模式</td><td>教学意义:分发与安装体验,而非单一算法技巧</td></tr></table>

## 6. ralph_mode/ — Ralph 模式

<table><tr><td>项</td><td>说明</td></tr><tr><td>入口</td><td>ralph_mode.py</td></tr><tr><td>能力</td><td>自主循环:每轮全新上下文,依赖文件系统持久化状态与产出</td></tr><tr><td>模式</td><td>与「单会话长上下文」对照,突出迭代+外存的代理范式</td></tr></table>

## examples/README.md 的对照

<table><tr><td>README 列表示例</td><td>说明</td></tr><tr><td>text-to-sql-agent/</td><td>自然语言转 SQL、Chinook 演示库、技能化工作流;本书未展开,但结构与 deep_research 同属「领域工具 + planning」一类。</td></tr></table>

## 跨示例的共性模式

1. 独⽴⼯程：各⾃ pyproject.toml + uv.lock ，版本范围常 pin 到 deepagents ⼩版本区间（⻅ README 贡献指南）。

2. 核⼼构造： create_deep_agent() 统⼀创建图/智能体。

3. 扩展点：

. tools= ：领域 API、检索、⽂件、SQL 等。

系统提示 / prompts：把⻆⾊、输出格式、安全约束写死到提示层。

Skills / Subagents（部分示例）：⽤⽂件系统约定（ SKILL.md subagents.yaml ）组织复杂能⼒。

⾃定义 backend（如 NVIDIA 示例）：对接特殊运⾏环境或数据⾯。

## 设计取舍 （架构视角）

. 示例之间不共享⼀个巨型依赖：每个示例锁⾃⼰的 uv.lock ，避免「跑通 A 示例却破坏 B 示例」的依赖地狱。

AGENTS.md 下沉到⼦项⽬：在 monorepo 全局 AGENTS.md 之外，再给 ⾼专⽤度示例（content-builder、nvidia）提供 局部规范，降低⽆关噪⾳。

服务器型示例单独成⽬录： async-subagent-server 与 CLI/脚本式示例分离，读者可按部署模型选型。

## 小结

examples/ 是 Deep Agents 从 API 到产品形态 的桥梁：以 create_deep_agent 为轴，通过tools、prompts、skills、backend、服务化 等组合表达不同场景；阅读时建议 先读该⽬录README.md ，再进⼊各⼦⽬录的 README.md 与 AGENTS.md