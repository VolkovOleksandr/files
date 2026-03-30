# Enterprise Architecture for AI Developer Helper Distribution

## Goal

Create an enterprise-ready system to author, validate, package, distribute, install, update, and govern AI developer helper assets for VS Code, with a focus on:

- **Agent Skills / instruction files**
- **Prompt files / agent definitions**
- **MCP profiles and configuration**
- **Access to centrally hosted MCP servers**
- **Fast and controlled updates for developers**

This design assumes your organization uses **Bitbucket** for source control and **Jenkins** for CI/CD orchestration. Bitbucket remains the authoring and review system, while Jenkins handles validation, packaging, publishing, and promotion of release artifacts.

---

## High-level architecture

```text
Authors/Platform Team
        |
        v
Bitbucket repositories
  - skills repo
  - MCP profile repo
  - CLI repo
  - MCP server repos
        |
        v
Jenkins
  - validate
  - test
  - package
  - version
  - publish
        |
        v
JFrog Artifactory
  - generic repositories for released bundles
  - release channels: dev / beta / stable
  - immutable versioned artifacts
        |
        v
Developer Helper CLI
  - install
  - update
  - rollback
  - pin channel/version
  - doctor
  - auth
        |
        +--------------------+
        |                    |
        v                    v
Local VS Code/Copilot     MCP configuration
customization files       pointing to central MCP servers
        |                    |
        +---------+----------+
                  |
                  v
            VS Code + Copilot
                  |
                  v
      Centrally hosted MCP servers
      - tools
      - resources
      - prompts
```

---

## Why this architecture is a good fit

### 1. Bitbucket stays the authoring system

Bitbucket should be the place where your team:

- writes and reviews skill files
- manages manifests and metadata
- versions MCP profile templates
- develops the CLI
- builds MCP servers

This keeps authoring in a normal developer workflow with pull requests, history, rollback, and approvals.

### 2. Artifactory becomes the release/distribution system

JFrog Artifactory supports **Generic repositories**, which are suitable for storing arbitrary packaged files such as installers, bundles, manifests, and helper assets. That makes it a good fit for shipping AI helper bundles and CLI releases. citeturn729239search2turn729239search22

### 3. The CLI becomes the installation and lifecycle manager

The CLI gives you:

- a standard way to install/update assets
- compatibility checks
- pinned versions or channels
- rollback support
- local machine state tracking
- editor-agnostic distribution logic

### 4. MCP stays centralized for dynamic capabilities

MCP servers expose **tools, resources, and prompts** to clients. In VS Code, MCP servers can be managed directly and can provide live external capabilities such as APIs, database access, internal docs, and workflow tools. citeturn729239search4turn729239search11turn729239search15turn729239search3

This means:

- **static guidance** should ship as files/bundles
- **dynamic/live functionality** should stay server-side in MCP

---

## Core components

## 1. Source repositories in Bitbucket

Use separate repos or a monorepo depending on team size.

### Recommended repositories

### A. `ai-dev-helper-skills`
Stores reusable VS Code/Copilot customization assets:

- agent skills
- instruction files
- prompt files
- agent definitions
- metadata and manifests
- examples and tests

Suggested structure:

```text
ai-dev-helper-skills/
  skills/
    terraform-aws/
      skill.md
      metadata.yaml
      examples/
    python-backend/
      skill.md
      metadata.yaml
  instructions/
    secure-coding.instructions.md
    code-review.instructions.md
  prompts/
  agents/
  manifests/
  schemas/
  tests/
  Jenkinsfile
```

### B. `ai-dev-helper-cli`
Stores the install/update CLI.

### C. `ai-dev-helper-mcp-profiles`
Stores MCP client-side config templates and environment-specific profiles.

### D. `ai-dev-helper-mcp-*`
One or more repos for actual MCP servers.

---

## 2. Jenkins for CI/CD

Jenkins should run the validation and release workflow for each repository. Bitbucket remains the source-control system for pull requests and code review, while Jenkins acts as the centralized CI engine that builds, tests, packages, publishes, and promotes artifacts across environments and release channels.

### Skills pipeline responsibilities

For the skills repo, the Jenkins pipeline should:

1. validate folder structure
2. validate metadata schema
3. lint markdown and manifests
4. run example-based tests or snapshot checks
5. build versioned bundles
6. publish bundles to Artifactory
7. publish/update release manifest

### CLI pipeline responsibilities

For the CLI repo, the Jenkins pipeline should:

1. run unit/integration tests
2. build platform-specific binaries or package artifacts
3. publish CLI release artifacts to Artifactory
4. promote artifacts across channels if approved

### MCP profile pipeline responsibilities

For the MCP profile repo, the Jenkins pipeline should:

1. validate profile schema
2. validate server endpoint references
3. package profiles by environment/team
4. publish packaged profiles to Artifactory

### MCP server pipeline responsibilities

For each MCP server repo, the Jenkins pipeline should:

1. run tests
2. build deployable container/image
3. deploy to target environment
4. update service version metadata if needed

---

## 3. JFrog Artifactory repositories

Use Artifactory as the release hub.

### Recommended Artifactory layout

```text
artifactory/
  ai-helper-dev-generic/
  ai-helper-beta-generic/
  ai-helper-stable-generic/
  ai-helper-cli-generic/
  ai-helper-manifests-generic/
```

Because generic repositories support arbitrary files, they are appropriate for packaged skill bundles, CLI archives, manifests, and other non-language-specific assets. citeturn729239search2

### What gets published

#### Skill bundle
Example:

```text
skills-bundle-terraform-aws-1.4.2.tgz
```

#### MCP profile bundle
Example:

```text
mcp-profile-platform-team-2.1.0.tgz
```

#### CLI release
Example:

```text
devhelper-cli-darwin-arm64-0.9.0.tar.gz
```

#### Manifest/catalog
Example:

```text
catalog-stable.json
```

### Why channels matter

Use channels such as:

- `dev`
- `beta`
- `stable`

This allows controlled rollout:

- platform team tests in `dev`
- pilot users consume `beta`
- organization consumes `stable`

---

## 4. Release manifest / catalog

A central manifest tells the CLI what exists, what versions are valid, and where to install them.

Example:

```json
{
  "version": "2026-03-30",
  "channels": {
    "stable": {
      "skills": [
        {
          "id": "terraform-aws",
          "version": "1.4.2",
          "artifact": "skills-bundle-terraform-aws-1.4.2.tgz",
          "installTarget": "workspace",
          "compatibility": {
            "vscode": ">=1.100.0",
            "cli": ">=0.9.0"
          }
        }
      ],
      "mcpProfiles": [
        {
          "id": "platform-default",
          "version": "2.1.0",
          "artifact": "mcp-profile-platform-default-2.1.0.tgz"
        }
      ]
    }
  }
}
```

### Manifest responsibilities

The manifest should define:

- package id
- version
- channel
- checksum
- compatible CLI version
- compatible VS Code version
- installation target
- dependencies
- deprecation status
- rollback target if needed

---

## 5. Developer Helper CLI

The CLI is the operational bridge between Artifactory and the developer’s machine.

### Recommended commands

```bash
devhelper auth
devhelper install terraform-aws
devhelper install profile platform-default
devhelper update
devhelper list
devhelper pin stable
devhelper pin terraform-aws@1.4.2
devhelper rollback terraform-aws
devhelper doctor
devhelper sync
```

### CLI responsibilities

The CLI should:

- authenticate to Artifactory
- fetch catalog/manifest
- resolve compatible versions
- download artifacts
- verify checksums/signatures
- unpack files into correct local locations
- write/update MCP client config
- track local installed state
- support rollback and channel pinning
- validate prerequisites with `doctor`

### Local state file

Example:

```json
{
  "channel": "stable",
  "installed": {
    "skills": {
      "terraform-aws": "1.4.2",
      "python-backend": "2.0.1"
    },
    "profiles": {
      "platform-default": "2.1.0"
    }
  }
}
```

---

## 6. Local installation targets in VS Code

VS Code supports AI customization via custom instructions, prompt files, custom agents, agent skills, and MCP servers. It can also discover applicable customizations from workspace and repository hierarchy locations. citeturn729239search0turn729239search8turn729239search12turn729239search16turn729239search4

### Practical installation model

Your CLI should support two main install scopes:

### A. User-level install
For reusable personal/team defaults on a developer machine.

### B. Workspace/repo-level install
For project-specific assets committed into a repository or placed in local workspace config.

### Suggested rule

- install **organization-wide defaults** at user level
- install **project-specific helper assets** at workspace level

This gives you both standardization and flexibility.

---

## 7. MCP profiles vs MCP servers

These should be treated as different things.

### MCP profile
A packaged configuration that tells the client:

- which MCP servers to use
- which environments to point to
- which auth mode to expect
- which tools/resources/prompts are allowed for a team or project

### MCP server
The actual running service that exposes:

- tools
- resources
- prompts

MCP is designed for servers to expose prompts, resources, and tools in a standard way, which is why live enterprise integrations should stay in central services instead of being bundled entirely as local files. citeturn729239search3turn729239search11turn729239search15turn729239search19

### Good examples for central MCP servers

- internal docs search
- coding standards lookup
- architecture decision records
- deployment helper tools
- incident/debug workflows
- ticketing integrations
- service ownership lookup
- runbook retrieval

---

## 8. Security and governance

This is one of the biggest reasons to use Artifactory + CLI + central MCP.

### Recommended controls

#### Release governance
- only CI publishes release artifacts
- no manual file uploads for production bundles
- require approvals for promotion to `stable`

#### Artifact trust
- checksum verification
- optional signing
- immutable versioned bundles

#### Access control
- Artifactory auth via enterprise identity or scoped tokens
- environment-specific MCP endpoints
- role-based access to sensitive MCP tools/resources

#### Observability
- CLI install/update telemetry
- MCP server request logs
- per-version adoption tracking
- deprecation warnings for old bundles

#### Safety controls
- do not embed secrets in skill bundles
- keep sensitive integrations behind authenticated MCP servers
- allow feature flags per team/environment

---

## 9. End-to-end flow

## Flow 1: Authoring and release of a new skill bundle

1. Platform engineer updates a skill in the Bitbucket skills repo.
2. A pull request is reviewed and approved in Bitbucket.
3. Jenkins runs validation and test stages.
4. Jenkins builds a versioned bundle such as `skills-bundle-terraform-aws-1.4.2.tgz`.
5. Jenkins publishes the artifact to the Artifactory `beta` or `stable` generic repo.
6. Jenkins updates or republishes the release manifest/catalog.
7. Developers can now install or update that skill through the CLI.

## Flow 2: Developer installs or updates skills

1. Developer runs `devhelper update`.
2. CLI authenticates to Artifactory.
3. CLI downloads the current catalog for the chosen channel.
4. CLI checks compatibility with local CLI version and VS Code version.
5. CLI downloads new or changed bundles.
6. CLI verifies checksum/signature.
7. CLI installs files into user/workspace target locations.
8. CLI updates local installed-state metadata.
9. VS Code/Copilot picks up the customization files.

## Flow 3: Developer receives dynamic enterprise capabilities through MCP

1. Developer installs an MCP profile with `devhelper install profile platform-default`.
2. CLI writes/updates the local MCP client configuration.
3. VS Code loads the configured MCP server entries.
4. During chat/agent execution, Copilot can access allowed MCP tools/resources/prompts from those central servers.
5. Any server-side updates become available without re-shipping local files, assuming the profile remains compatible.

## Flow 4: Rollback

1. A bad skill bundle is detected in `stable`.
2. Platform team updates the manifest to promote the previous good version.
3. Developers run `devhelper update`, or the CLI notices a rollback target.
4. CLI reinstalls the prior known-good bundle.

---

## 10. Recommended packaging rules

### Skill bundle contents

```text
bundle/
  manifest.json
  skills/
  instructions/
  prompts/
  agents/
  checksums.txt
  CHANGELOG.md
```

### MCP profile bundle contents

```text
bundle/
  manifest.json
  mcp/
    profile.json
    environments/
  checksums.txt
```

### CLI package contents

```text
bundle/
  devhelper
  LICENSE
  README.md
```

---

## 11. Recommended operating model

### Platform team owns

- central standards
- bundle schema
- validation rules
- CLI
- Artifactory publishing
- MCP platform services

### Domain teams own

- team-specific skills
- project-level prompts/instructions
- domain MCP tools/resources where needed

### Developers do

- install approved bundles
- pick channels when allowed
- pin versions for specific repos if needed
- report compatibility issues

---

## 12. Best practices

### Authoring best practices

- keep skills small and focused
- separate generic skills from repo-specific instructions
- test examples and expected behavior
- include version and compatibility metadata

### Distribution best practices

- publish only through CI
- use release channels
- keep manifests explicit and machine-readable
- support rollback from day one

### MCP best practices

- put live or sensitive logic in MCP servers
- keep auth and authorization server-side
- expose only the tools/resources/prompts needed for each profile

### Developer experience best practices

- provide `doctor` for troubleshooting
- make `install` and `update` one-command operations
- support user-level and workspace-level installs
- keep clear local state and logs

---

## 13. Suggested MVP

If you want to start simple without overbuilding, this is a strong MVP:

### MVP scope

- 1 Bitbucket repo for skills
- 1 Bitbucket repo for CLI
- Jenkins builds and publishes artifacts
- 1 Artifactory generic repo for `beta` and `stable`
- 1 JSON catalog
- CLI supports:
  - `auth`
  - `install`
  - `update`
  - `list`
  - `doctor`
- 1 centrally hosted MCP server for internal docs/tools
- 1 MCP profile package

### Why this MVP works

It gives you:

- governed release flow
- repeatable installs
- instant server-side updates for live tools
- a clear path to scale later

---

## 14. Recommended future enhancements

Later, you can add:

- auto-update policies
- team-based feature flags
- usage analytics dashboards
- approval workflows for skill promotion
- CLI self-update
- VS Code extension on top of the CLI for better UX
- multiple MCP profiles by team/environment
- policy checks that block deprecated bundles

---

## Final recommendation

For an enterprise using **Bitbucket**, the best architecture is:

- **Bitbucket** for authoring, reviews, and pull-request governance
- **Jenkins** for validation, packaging, publishing, and promotion
- **JFrog Artifactory** for controlled, versioned distribution of packaged skills, manifests, and CLI releases using generic repositories citeturn729239search2turn729239search22
- **Developer Helper CLI** for install/update/rollback and local machine integration
- **VS Code/Copilot customization files** for static behavior customization citeturn729239search0turn729239search16turn729239search8turn729239search12
- **Central MCP servers** for dynamic enterprise tools, resources, and prompts citeturn729239search4turn729239search3turn729239search11turn729239search15

In short:

**Bitbucket stores and reviews it, Jenkins packages it, Artifactory distributes it, CLI installs it, VS Code consumes it, and MCP powers the live enterprise capabilities.**
