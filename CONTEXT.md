# Team Agents

Team Agents is a Git-backed standards layer that helps employees apply company standards in working repositories while keeping company-private context out of client repositories.

## Language

**Standards Layer**:
The product category for Team Agents: a source of selected company, repo, profile, and user standards for AI tools. It is not an agent runtime, task manager, workflow executor, scheduler, or orchestrator.
_Avoid_: Orchestrator, task runner, automation runtime

**Standard**:
A reusable piece of company, repo, or user guidance that can be selected for a working repo. Team Agents provides built-in standard kinds and examples, but each company owns the meaning, naming, and governance model for its standards.
_Avoid_: Agent, automation, task

**Standard Kind**:
A built-in storage category Team Agents uses to validate, select, and render standards. v1 internal kinds are policy, context, completion_gate, skill, playbook, pack, and profile. Companies may map those storage primitives to their own terminology and governance model; the internal kind names are not a required corporate taxonomy.
_Avoid_: Universal taxonomy, fixed methodology

**Policy Standard**:
A built-in example standard kind for rules or guidelines an agent should follow when working in a repo. A company may use a different name or split this concept more finely.
_Avoid_: Preference, suggestion

**Context Standard**:
Reference context an agent may need to understand a repo, domain, platform, or company convention. This is a built-in example kind for background knowledge, not a claim that every company must organize knowledge this way.
_Avoid_: Policy, requirement

**Completion Gate Standard**:
A built-in example standard kind for completion boundaries, evidence expectations, or definitions of done. Companies decide whether these are called contracts, checks, gates, controls, or something else.
_Avoid_: Tip, checklist when optional

**Skill Standard**:
A built-in example standard kind for reusable agent capabilities or working techniques. Skill standards describe how an agent should perform a kind of work; they do not execute work by themselves.
_Avoid_: Script, job, automation

**Playbook Standard**:
A built-in example standard kind for repeatable playbooks. Playbook standards guide sequencing and decision points; they are not executable workflows.
_Avoid_: Workflow engine, orchestration graph, automation

**Pack**:
A bundle of standards selected together for a baseline, repo group, repo, or work mode. Packs are the preferred way to keep common context coherent without making every standard global.
_Avoid_: Junk drawer, mega profile

**Baseline Pack**:
The small required pack every applicable repo receives for safety, privacy, completion boundaries, and basic orientation. A baseline pack should stay narrow and should not carry role-specific, framework-specific, or task-specific guidance.
_Avoid_: Default everything, global context dump

**Repo-Group Pack**:
A pack shared by a family of repos, such as platform, client, data, or frontend repos. Repo-group packs are the main home for shared context, policies, completion gates, and playbook standards that are too specific for the baseline and too common to repeat per repo.
_Avoid_: Org baseline, copied repo config

**Profile**:
A work mode that selects the standards needed for a specific kind of repo work, such as coding, reviewing, planning, or incident response. Profiles are the main tool for preventing context bloat.
_Avoid_: Persona, agent type, runtime role

**Client Repo**:
A repository owned by or delivered to a client where company-private standards must not be committed. Client repos may receive client-safe generated guidance, but company-private context stays local.
_Avoid_: External repo when privacy is the relevant distinction

**Company-Private Context**:
Company standards or operational knowledge that employees may use locally but must not commit into client repositories. The privacy boundary is a core reason Team Agents exists.
_Avoid_: Internal-only files, secret sauce

**Integration Consumer**:
An external tool that reads Team Agents output to prepare context, enforce its own workflow, or render standards in another runtime. Integration consumers may plug into Team Agents, but Team Agents does not become their runtime, scheduler, orchestrator, permission engine, or task state store.
_Avoid_: Owned runtime, managed workflow, built-in orchestrator

**Activation Selection**:
The resolution step that decides which standards are active, why they are active, and which Pack or Profile selected them. Activation selection owns required-vs-enabled reasoning, Pack expansion, Profile activation, and activation provenance; it does not own runtime execution or Client Repo privacy enforcement.
_Avoid_: Workflow execution, task routing, runtime scheduling

## Example Dialogue

Developer: "Should we add this security checklist to every repo?"

Maintainer: "If it is a required company rule, make it a policy standard in the baseline pack. If it is only needed during PR review, put it in the reviewer profile."

Developer: "Can we add a workflow for incident response?"

Maintainer: "Use a playbook standard for the playbook. Team Agents can select and render the playbook, but the incident tooling or employee still owns execution."
