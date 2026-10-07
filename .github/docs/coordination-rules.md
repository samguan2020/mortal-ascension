# Agent Coordination Rules

1. **Vertical Delegation**: Leadership agents delegate to department leads, who
   delegate to specialists. Do not skip a tier for complex decisions.
2. **Horizontal Consultation**: Agents at the same tier may consult each other
   but must not make binding decisions outside their domain.
3. **Conflict Resolution**: Escalate design conflicts to `creative-director`
   and technical conflicts to `technical-director`.
4. **Change Propagation**: When a design change affects multiple domains, the
   `producer` coordinates propagation.
5. **No Unilateral Cross-Domain Changes**: An agent must not modify files
   outside its approved scope.

## Copilot Delegation

Use the custom agents installed under `.github/agents/` only when specialized
work needs a separate context. Keep each delegation self-contained with the
project root, objective, input paths, approved write scope and stopping condition.

Do not override a subagent model unless the user explicitly requests one.
Copilot selects the appropriate model through its configured runtime.

**Parallel delegation**: If objectives are independent and cannot write
overlapping files, launch them before waiting for either result.

**Sequential delegation**: If one result determines another agent's input,
collect the first result before launching dependent work.

## Parallel Task Protocol

1. Issue all independent `runSubagent` calls before waiting for results.
2. Collect all results before proceeding to dependent phases.
3. Surface `BLOCKED` or `NEEDS_APPROVAL` immediately.
4. Produce a partial report if only part of a delegated batch succeeds.
