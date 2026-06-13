# DeepAgents Project Memory

This repository has a source guide at `deepagent指南.md` (v1.0.0, 2026-05-26) that should be treated as the durable reference for DeepAgents work. Use this file as the always-on project memory distilled from that guide.

## Core Mental Model

- Treat DeepAgents as an Agent Harness built on LangChain/LangGraph, not as a separate runtime. Prefer composition through `create_deep_agent(...)`, middleware, backends, skills, memory, and subagents.
- Keep the three layers clear:
  - Backend layer: storage and execution boundary.
  - Middleware layer: tool injection, system-prompt injection, request/message/state transforms.
  - Graph layer: LangChain `create_agent(...)` returns the LangGraph runnable/compiled graph.
- Prefer stable public entry points and exports. Before changing an API, check whether it is exported from package `__init__.py`, used in tests, examples, CLI, evals, or partner packages.

## `create_deep_agent(...)`

- Use `create_deep_agent(...)` as the main assembly function. Describe capabilities through parameters instead of deep inheritance.
- If no backend is supplied, the default is `StateBackend()`: files live in LangGraph state, persist within a thread/checkpoint, and are not real disk files.
- `system_prompt` is appended with the built-in base prompt. Preserve that baseline behavior unless a task explicitly requires lower-level changes.
- Default middleware order matters:
  1. `TodoListMiddleware`
  2. optional `SkillsMiddleware`
  3. `FilesystemMiddleware`
  4. `SubAgentMiddleware`
  5. `SummarizationMiddleware`
  6. `PatchToolCallsMiddleware`
  7. optional `AsyncSubAgentMiddleware`
  8. user middleware
  9. `AnthropicPromptCachingMiddleware`
  10. optional `MemoryMiddleware`
  11. optional `HumanInTheLoopMiddleware`
- Keep `AnthropicPromptCachingMiddleware` before `MemoryMiddleware` so memory changes do not destabilize Anthropic prompt-cache prefixes.
- `create_deep_agent(...)` raises the graph recursion limit to a large value; avoid adding artificial low step limits for complex tasks unless testing that behavior.

## Backends And Execution

- `BackendProtocol` owns file-like operations: `ls`, `read`, `write`, `edit`, `grep`, `glob`, upload, and download.
- `SandboxBackendProtocol` adds `execute`/`aexecute` and a stable `id`. Only expose real shell execution when the backend implements this protocol.
- Choose backends deliberately:
  - `StateBackend`: default isolated working files in graph state.
  - `FilesystemBackend`: real local disk, useful for trusted local workflows, not a security sandbox.
  - `StoreBackend`: long-lived store-backed memory/knowledge.
  - `CompositeBackend`: route virtual path prefixes to different backends.
  - `LocalShellBackend`: local disk plus local shell; powerful but not isolated.
  - Sandbox implementations: preferred for untrusted code or hosted execution.
- `CompositeBackend` routes file paths by prefix, but command execution goes through the default backend only.
- Do not treat `virtual_mode` or path checks as process isolation. Untrusted code must run inside a real sandbox boundary.

## Middleware Versus Tools

- Use middleware when behavior must run before every model call, inject or change system prompts, filter tools, transform messages, or maintain cross-turn state.
- Use ordinary tools for self-contained business actions that the model should call explicitly.
- Keep middleware responsibilities narrow. Avoid slow network work inside `wrap_model_call` unless it is cached or explicitly required.
- Preserve async variants when adding middleware behavior.

## Filesystem Middleware

- The standard tool surface is `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`, and conditional `execute`.
- `execute` is filtered from the request when the current backend does not implement `SandboxBackendProtocol`.
- Large tool results and large human messages may be evicted/offloaded to the backend. Preserve this pattern rather than pushing large payloads into model context.
- Read files in paged/targeted ways. Prefer search and focused reads over dumping huge files.

## Subagents

- Synchronous subagents are reached through the `task` tool. Declarative `SubAgent` specs receive the default DeepAgents middleware stack before user-provided middleware.
- If no synchronous `general-purpose` subagent is provided, DeepAgents injects one by default. Override it by explicitly defining a subagent with that name.
- `CompiledSubAgent` does not automatically inherit top-level human-in-the-loop behavior; configure it in the runnable.
- `AsyncSubAgent` specs contain `graph_id` and are handled by `AsyncSubAgentMiddleware`; they are for remote/background jobs and should return task IDs rather than blocking.

## Summarization, Memory, And Skills

- Automatic summarization should protect long-running work from context overflow. With model profile data, the default shape is roughly trigger at 85% of context and keep 10% recent context.
- Summarized conversation history is offloaded to backend files, commonly under `/conversation_history/{thread_id}.md`.
- `MemoryMiddleware` is for always-present durable project/user context such as `AGENTS.md`; multiple memory sources are concatenated in order.
- `SkillsMiddleware` is for reusable procedural capability. Each skill is a directory with `SKILL.md` frontmatter plus Markdown body; multiple skill sources are layered by skill name, with later sources winning.
- Use progressive disclosure for skills: list metadata in prompt context, read the full `SKILL.md` only when the skill is relevant.

## CLI And Integration Patterns

- CLI code should converge on the SDK `create_deep_agent(...)` path rather than reimplementing the harness.
- Use delayed imports for heavy CLI dependencies so help/version/config paths stay fast.
- CLI configuration is layered through settings, TOML, dotenv, and `DEEPAGENTS_CLI_*` environment variables. Register new CLI env vars in the central env-var module rather than scattering string literals.
- For local CLI mode, isolate large tool results and conversation history with `CompositeBackend` prefix routes where appropriate.
- Shell allow-list policy belongs in middleware so policy, UI approval, and tracing remain predictable.

## Models

- Prefer model strings or `BaseChatModel` instances accepted by `resolve_model(...)`.
- OpenAI model strings prefixed with `openai:` should use the Responses API path.
- OpenRouter model strings prefixed with `openrouter:` need the minimum supported package version and app attribution behavior, while respecting user env overrides.
- When switching models at runtime, remove provider-specific message fields that are incompatible with the new provider.

## Evals And Tests

- Keep correctness and efficiency separate:
  - `.success(...)` is a hard correctness assertion.
  - `.expect(...)` records trajectory shape/efficiency and should not fail the test by itself.
- New eval flow:
  1. mark with `@pytest.mark.langsmith`;
  2. inject `model: BaseChatModel`;
  3. build with `create_deep_agent(model=model, ...)`;
  4. run with `run_agent(..., scorer=...)`;
  5. combine `TrajectoryScorer().success(...).expect(...)`.
- For new eval categories, update `categories.json`, add the marker, update category drift tests, and regenerate/check the eval catalog if present.
- Test layout convention:
  - unit tests are fast and offline;
  - integration/eval tests may need network or API keys;
  - test paths should mirror source paths;
  - prefer testing real behavior over duplicating implementation logic in mocks.

## Code Quality And Safety

- Use the repository's existing toolchain and package-local configuration first: `uv`, `make`, `ruff`, `ty`, and `pytest`.
- Public Python APIs need complete type annotations, including return types.
- Prefer Google-style docstrings. Put type information in signatures, not repeated prose.
- Use American English spellings in code identifiers.
- Add new function parameters as keyword-only when that protects compatibility.
- Use targeted `# noqa: RULE` for single-line lint suppressions; reserve per-file ignores for deliberate file-class policies.
- Never use `eval`, `exec`, or `pickle` with untrusted input.
- Do not hardcode secrets or log sensitive values. Prefer environment variables and redaction.
- Avoid bare `except:`; catch specific errors and produce useful diagnostic messages.

## Examples Pattern

- Example projects should be independently runnable, usually with their own `pyproject.toml` and lock file.
- The common extension points are `tools=`, domain prompts/system prompts, skills, subagents, custom backends, and service hosting.
- Put local, high-specificity guidance in subproject `AGENTS.md` files when a subproject needs rules beyond this root memory.
