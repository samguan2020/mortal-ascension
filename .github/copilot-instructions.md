# Mortal Ascension - GitHub Copilot runtime contract

This standalone game uses 44 custom agents in `agents/` and 73 skills in
`skills/` with GitHub Copilot in VS Code. These are development roles, not
in-game NPCs. The tooling's MIT notice is in
[STUDIO-LICENSE](STUDIO-LICENSE).

Read [shared project instructions](../AGENTS.md). For this Copilot port, the
runtime adaptations here govern how to execute legacy workflow guidance;
shared design standards and user approval requirements remain unchanged.

## Scope and shared context

- The project root is `D:\Repos\mortal-ascension`, an independent Git repository.
  There is no enclosing studio or `Games/` selection step.
- Read this game's instructions, preferences, design and architecture. The
  current client is `web/` with `cloud/`; editable assets live in
  `assets/source/` and offline asset tools in `tools/asset-pipeline/`.
  Do not copy root studio defaults over the game's configured preferences.
- `.github/docs/` is the shared documentation/template store. Read linked
  documents explicitly; `@file` is not a Copilot import mechanism. Workspace
  paths in workflow bodies are project-root-relative.
- Use `.github/agents/<role>.agent.md` and `.github/skills/<skill>/SKILL.md` for
  Copilot.

## Native tools and skills

- Use the tools actually exposed by the current Copilot session. Agent tool sets
  use `read`, `search`, `edit`, `execute`, `web`, and `agent`.
- `runSubagent` is the VS Code delegation tool. Select the custom agent by name
  using its installed tool schema; `agentName` in workflow text names the role.
  Never invent an unsupported `Task` call or report delegation that did not occur.
- For legacy shared docs: Read = read; Glob/Grep = search; Write/Edit = edit;
  Bash = terminal execution; WebSearch/WebFetch = available web tools;
  Task = runSubagent; TodoWrite = the available todo tool.
- Ask one question at a time with `vscode/askQuestions` when available. If a host
  lacks that tool, ask in chat and wait. Never simulate the user's approval.
- Slash commands refer to skills, not shell commands. Load the named skill and
  follow its argument guards. Arguments are the text after the slash command;
  there is no `$ARGUMENTS` substitution or automatic `!command` execution.
- Skill capability budgets are behavioral instructions, not permission
  enforcement. The active agent's tools and Copilot approval settings are the
  actual tool boundary. Report a missing capability instead of bypassing it.
- Model selection is left to Copilot's model picker. Legacy Haiku/Sonnet/Opus
  tiers are advisory complexity labels, not runnable model identifiers here.

## Parent-mediated collaboration

- Preserve Question -> Options -> Decision -> Draft -> Approval. Show a summary
  and affected paths before asking permission to write. No commits, pushes,
  releases, deployments, or destructive Git operations without user instruction.
- Copilot subagents cannot ask the user questions directly in the VS Code Local
  harness. A worker without an approved file list returns a draft, paths, and
  `NEEDS_APPROVAL`. The parent asks the user, then starts a fresh worker with the
  approval, bounded task, and complete context. Do not leave a worker waiting.
- This parent-mediated procedure replaces any legacy instruction asking a worker
  to call a question tool or wait for "yes" itself. Never treat a lead agent's
  recommendation as user authorization.
- Keep each delegation self-contained: selected project root, role, objective,
  input files, approval scope, output shape, and stopping condition.
- Delegate only when specialized work needs separate context. Parallelize only
  independent work without overlapping writes. For dependent work, collect the
  result before proceeding. Surface BLOCKED/NEEDS_APPROVAL and partial results.
- Nested delegation is not required. When a child needs a specialist but cannot
  invoke one, return the proposed handoff to the parent. The parent dispatches it,
  preserving role ownership. Do not enable experimental recursion implicitly.
- A skill's preferred role is guidance, not an automatic agent/tool switch.
  If the role or tool is unavailable, report the limitation and request a manual
  agent switch; do not pretend several independent reviews happened.

## Safety and verification

- Read applicable `instructions/*.instructions.md` rules before editing.
- Keep credentials and local environment files out of prompts, browser bundles,
  logs, and commits. Do not weaken approvals or enable automatic terminal approval.
- A no-terminal role must not delegate shell execution to evade its restriction.
- Preserve worktree changes. Use the host shell: PowerShell on Windows; translate
  POSIX examples rather than assuming Bash exists. Check command failures.
- Run relevant tests/builds and provide evidence. For read-only skills, do not
  create reports or session checkpoints unless the user separately approves
  changing scope.

## Runtime limitations

- Permission rules, status lines, agent memory, `maxTurns`, `isolation: worktree`,
  and shell-injected context are not installed.
- No automatic commit/push guard or session-log hook is claimed.
- Use existing project documents for continuity. Save a checkpoint only when
  allowed by the workflow and approved; start a new chat when context is full.
  `/clear` or `/compact` guidance is not a portable Copilot command.
- Do not create a worktree implicitly. Ask before isolating work in a branch or
  worktree; keep experiments outside production imports.

Open this repository directly in VS Code so its local agents, skills and
instructions can be discovered. See [project instructions](../AGENTS.md) and
the [setup instructions](../README.md). Generated definitions were copied from the
studio's Copilot port; no parent repository or sync script is required at runtime.
