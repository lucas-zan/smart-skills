# Git Orchestrator

`git-orchestrator` 是一个面向 Git / GitHub 交付流程的 skill，目标不是替代 git，而是把“建分支、校验、提交、推送、开 PR、检查状态、触发 workflow、直接 share-and-land”这些容易出错的步骤固化成可重复流程。

它适合这些场景：

- 让 agent 帮你提交代码
- 为当前改动创建远端可见分支
- 自动生成 commit message 或 PR 描述
- 查询 PR / workflow 状态
- 在人工确认后，把 share branch 合回当前基线分支

这个 workflow 默认使用分支，不使用 tag 作为交付中的工作载体。原因很直接：

- tag 更适合标记不可变的发布点或里程碑
- 分支更适合承载可继续修改、可 review、可 rebase、可合并的开发过程

如果长期运行后产生很多 share branch，问题不在“用了分支”，而在“没有清理策略”和“命名不可读”。这个 skill 现在的默认命名会带上来源分支和日期，便于识别，也更适合后续批量清理。

## 作用

这个 skill 主要解决 4 个问题：

1. 把本地不可见的改动尽快推成远端分支，减少多人/多 agent 协作冲突。
2. 在提交前统一执行 requirement / design / test evidence 校验。
3. 用脚本约束交付顺序，避免“先 push 后验证”或“未确认直接合并”这类流程错误。
4. 在用户明确要求 release 时，把 release 自动化文件补到当前分支里，再继续合并和发布。

## 能力边界

它能做：

- 创建和切换分支
- 生成 commit subject / body
- 提交并推送
- 生成 PR body
- 通过 GitHub API 创建 PR、查询 PR、查询 workflow、触发 workflow、合并 PR
- 在 merge 成功后按配置自动触发 GitHub release workflow
- 在 release 请求下自动补齐 `.git-orchestrator.json` 和 `.github/workflows/release.yml`
- 执行 direct `share-and-land`

它不能替你判断：

- 改动本身是否合理
- 仓库保护策略是否应该绕过
- 线上发布是否应该执行
- 业务代码应该如何修复

如果 repo policy、远端权限或验证命令不满足，skill 应该停止，而不是继续冒险提交。
这个 skill 的自动补齐能力只用于 release 自动化文件，不应该拿来修业务代码。

## 目录结构

- `SKILL.md`: 给 agent 的触发规则和流程说明
- `scripts/`: 实际执行 git / GitHub 流程的脚本
- `references/`: 补充说明和模板
- `tests/`: 脚本级测试
- `agents/openai.yaml`: UI 元数据

## 主要流程

### 1. PR 流程

适用于：

- 仓库有保护分支
- 需要 review
- 需要 GitHub 检查通过后再 merge

典型步骤：

1. 建 feature branch
2. 校验 requirement / design / test evidence
3. 跑 lint / verify
4. 生成 commit message
5. commit + push
6. 生成 PR body
7. 创建 PR
8. 查询 PR / checks / workflow
9. 在满足仓库规则后 merge

### 2. Share-And-Land 流程

适用于：

- 人已经确认结果
- 仓库允许直接回推基线分支
- 希望先把分支公开，再落回当前基线分支

典型步骤：

1. 从当前基线分支创建 `share/...` 分支
2. 提交改动
3. rebase 到最新远端基线
4. 先 push share branch
5. 跑完整验证
6. 如果基线变化，rebase 后重验
7. 如果 rebase / merge 遇到冲突，且 repo policy 明确允许自动解决，只对允许路径调用受控 resolver 尝试解决
8. 自动解决后必须确认冲突标记已消失，并重新执行必要验证
9. 无法安全解决时停止，交给人工处理
10. 再合回基线分支并 push

如果用户明确要求“直接 release”或“merge 后自动 release”，可以直接走：

```bash
bash scripts/git_share_and_land.sh --confirmed --with-release --slug <slug> --subject "<subject>"
```

`--with-release` 的行为是：

- 如果仓库缺少 release 配置，就先把默认 `.git-orchestrator.json` 补到当前分支
- 如果仓库缺少根目录 `.github/workflows/release.yml`，就先生成它
- 这些文件会和当前分支的其他改动一起提交、合并
- merge 成功后再触发 release workflow

这个自动引导只会创建 release 自动化文件，不会改业务代码。

如果验证失败，流程应停在 share branch，不继续落回基线。

如果冲突自动解决失败、命中了禁止自动解决的路径，或者解决后验证失败，流程也应停止，不继续推送基线分支。

## 前置条件

至少需要：

- 当前目录是 git 仓库
- 存在可写远端，一般是 `origin`
- `uv` 可用

如果需要 GitHub API 或 git 远端网络操作：

- 设置 `CLAW_GITHUB_TOKEN`，或在 `skills/.env` 中提供它
- `CLAW_GITHUB_TOKEN` 可以直接使用 GitHub classic PAT
- `GITHUB_OWNER` / `GITHUB_REPO` 可显式设置，或者能从 `origin` 推断

如果需要 workflow preset 或 repo policy：

- 优先读取仓库根目录 `.git-orchestrator.json`
- 对 skill 集合仓库，也支持回退读取 `git-orchestrator/.git-orchestrator.json`

推荐优先使用：

```bash
export CLAW_GITHUB_TOKEN='your-temporary-token'
```

也可以从模板开始：

```bash
cp skills/.env.example skills/.env
```

如果希望后续 shell 自动带上这个变量，推荐写入启动文件：

```bash
echo "export CLAW_GITHUB_TOKEN='your-token'" >> ~/.zprofile
source ~/.zprofile
```

如果你只把变量 `source` 到当前终端里，但 agent 已经在更早之前启动，agent 仍然看不到这个值。原因是环境变量通常只会在进程启动时继承一次，不会在你后续 `source ~/.zprofile` 后自动同步到已经运行中的 agent。

推荐检查与生效顺序：

1. 先在你自己的终端确认变量已经存在：

```bash
printenv CLAW_GITHUB_TOKEN
```

2. 再重启启动该 agent 的终端、IDE 会话或宿主进程。
3. 让 agent 在新的会话里重新启动后，再执行依赖 GitHub 认证的流程。

对于排查，agent 侧只需要确认变量“是否存在”，不要回显 token 本身。

对于 GitHub 仓库，远端建议统一使用：

```bash
git remote set-url origin https://github.com/<owner>/<repo>.git
```

这样 API 调用和 git push / fetch / pull 都走同一套 HTTPS + 临时 token 认证链路。

## 推荐配置

建议提供一个 `.git-orchestrator.json`。普通业务仓库放在仓库根目录；像当前这种 skill 集合仓库，可以放在 `git-orchestrator/.git-orchestrator.json`。至少定义：

- 默认分支策略
- verification 命令
- evidence 校验规则
- 是否允许 share-and-land
- 哪些分支必须走 PR

最小示例：

```json
{
  "policy": {
    "defaults": {
      "base_branch_strategy": "current-branch",
      "feature_branch_prefix": "agent",
      "share_branch_prefix": "share"
    },
    "verify": {
      "command": "cargo fmt --check && cargo clippy --all-targets --all-features -- -D warnings && cargo test"
    },
    "evidence": {
      "enforce_before_commit": true,
      "require_requirements": true,
      "require_design": true,
      "require_tests": true
    },
    "share_and_land": {
      "allow_direct": true,
      "protected_branches": ["test", "release"],
      "protected_branch_mode": "require-pull-request",
      "reverify_on_base_change": true,
      "max_reverify_attempts": 3,
      "auto_resolve_conflicts": false,
      "auto_resolve_conflicts_command": "",
      "allowed_conflict_paths": [],
      "blocked_conflict_paths": [],
      "max_conflict_resolution_attempts": 3
    }
  }
}
```

冲突自动解决相关字段说明：

- `auto_resolve_conflicts`: 是否允许在 share-and-land 中自动尝试解冲突，默认关闭
- `auto_resolve_conflicts_command`: 实际执行的 resolver 命令。它可以是模型驱动命令，也可以是你自己的自动化脚本
- `allowed_conflict_paths`: 允许自动解决的路径白名单。非空时，只有命中的文件才允许自动解决
- `blocked_conflict_paths`: 禁止自动解决的路径黑名单。命中后必须停下交人工
- `max_conflict_resolution_attempts`: 单次流程里最多尝试多少次自动解冲突

推荐默认保持关闭，只在明确知道风险边界时开启。对于 migration、权限、安全、发布配置这类文件，更适合放进 `blocked_conflict_paths`。

## 快速使用

### 无配置时的默认行为

如果默认位置都没有配置文件，skill 使用内建默认策略：

- 当前分支就是默认基线分支
- `agent/` 是默认 feature branch 前缀
- `share/` 是默认 share branch 前缀
- 默认命名格式是 `<prefix>/<base-branch>-<yyyyMMddHHmmss>-<slug>`
- direct share-and-land 默认允许
- evidence 校验默认开启
- verify 命令默认自动探测项目类型

对 `share-and-land` 来说，默认流程是：

1. 以当前分支作为基线
2. 获取远端最新基线
3. 在可行时先 fast-forward pull 当前基线
4. 创建新的 `share/...` 分支
5. 提交并推送该分支
6. 验证通过后再合回当前开发分支

如果设置了配置文件，就以配置为准。

例如：

- 从 `main` 创建功能分支时，可能生成 `agent/main-20260415010203-fix-login-bug`
- 从 `release` 做 share-and-land 时，可能生成 `share/release-20260415010203-doc-sync`

### Merge 后自动触发 Release

如果希望在合并成功后自动触发 GitHub release 流程，可以在配置文件里增加：

```json
{
  "release": {
    "after_merge": {
      "enabled": true,
      "workflow": "release.yml",
      "platforms": ["macos", "linux"],
      "platform_input": "platforms",
      "inputs": {
        "publish": "true"
      }
    }
  },
  "workflows": {
    "release.yml": {
      "default_ref": "main",
      "required_inputs": ["platforms"],
      "allowed_inputs": ["platforms", "publish", "version"],
      "default_inputs": {
        "publish": "true"
      }
    }
  }
}
```

说明：

- `release.after_merge.enabled`: 开启 merge 后自动发布
- `workflow`: 要 dispatch 的 GitHub Actions workflow
- `platforms`: 需要发布的目标平台列表，默认会拼成逗号分隔字符串
- `platform_input`: workflow 里接收平台列表的 input 名称，默认是 `platforms`
- `inputs`: 额外透传给 workflow 的 inputs，比如 `publish=true`

配置后，`git_share_and_land.sh` 在成功 push 基线分支后会自动触发 release workflow；`github_ops.py merge-pr` 在成功 merge PR 后也会执行相同动作。

skill 目录里可以保存默认 workflow 模板，例如 `git-orchestrator/.github/workflows/release.yml`。如果目标仓库里还没有真正会被 GitHub 执行的 `.github/workflows/release.yml`，现在不需要手写。可以直接运行：

```bash
uv run python git-orchestrator/scripts/scaffold_release_workflow.py
```

这个脚本会根据配置文件生成一个默认的 release workflow，并写到目标仓库根目录的 `.github/workflows/release.yml`，包含：

- `workflow_dispatch` 入口
- `macos` / `linux` 打包矩阵
- 默认的 `.tar.gz` 产物打包
- 使用 `gh release create` / `gh release upload` 发布 GitHub Release

这里有一个硬约束：GitHub 只能调度仓库根目录 `.github/workflows/` 下已经存在的 workflow 文件。所以 skill 目录里的 workflow 只能作为模板保存；真正让 GitHub 使用时，仍然需要在 merge 前生成到仓库根目录并提交上去。

### 建分支

```bash
bash skills/git-orchestrator/scripts/git_start_branch.sh --slug fix-login-bug
```

### 跑验证

```bash
bash skills/git-orchestrator/scripts/verify_repo.sh
```

如果仓库没有默认验证命令，可以临时覆盖：

```bash
VERIFY_CMD='cargo fmt --check && cargo clippy --all-targets --all-features -- -D warnings && cargo test' \
bash skills/git-orchestrator/scripts/verify_repo.sh
```

认证检查已经集成在主流程里：

- `git_start_branch.sh`
- `git_commit_and_push.sh`
- `git_share_and_land.sh`
- `github_ops.py`

这些入口在执行网络操作前，会自动检查：

- 当前 `origin` 是否为 GitHub HTTPS remote
- `CLAW_GITHUB_TOKEN` 是否已在当前 shell 中设置，或者能从 `skills/.env` 读取
- 当前状态是否满足 skill 的认证前提

### 生成 commit message

```bash
uv run python skills/git-orchestrator/scripts/generate_commit_message.py \
  --context "handle empty refresh token before jwt parsing" \
  --json
```

### 提交并推送

```bash
bash skills/git-orchestrator/scripts/git_commit_and_push.sh \
  --subject "fix(auth): handle empty refresh token" \
  --body "Reject empty refresh token values before JWT parsing." \
  --requirement docs/requirements/auth-refresh-token.md \
  --design docs/design/auth-refresh-token.md \
  --test tests/test_auth_refresh_token.py
```

### 创建 PR

```bash
uv run python skills/git-orchestrator/scripts/github_ops.py create-pr \
  --title "fix(auth): handle empty refresh token" \
  --head "agent/main-20260415010203-fix-login-bug" \
  --base "main" \
  --body-file /tmp/pr_body.md
```

### Share-And-Land

```bash
bash skills/git-orchestrator/scripts/git_share_and_land.sh \
  --confirmed \
  --slug auth-refresh-token \
  --subject "fix(auth): handle empty refresh token"
```

`--confirmed` 是强制项，避免 agent 在没有人工确认时直接落地到基线分支。

## 常见卡点

### 1. 远端认证失败

先确认当前仓库使用的是 HTTPS 还是 SSH。

- 这个 skill 现在以 GitHub HTTPS 为标准路径
- 如果 remote 还是 `git@github.com:...`，脚本会要求切换成 HTTPS
- `CLAW_GITHUB_TOKEN` 可以来自环境变量，或来自被忽略的 `skills/.env`
- 现在主流程会自动做认证前置检查，并在失败时直接输出修复建议

### 2. verification 失败

这是正常阻断，不应该绕过。

常见原因：

- `cargo fmt --check` 未通过
- `clippy -D warnings` 未通过
- 测试未通过
- `.git-orchestrator.json` 中的 `verify.command` 过严或过旧

### 3. change basis 校验失败

说明 requirement / design / test evidence 不满足。

可以通过两种方式解决：

- 在仓库里补齐匹配规则的文档和测试
- 显式传入 `--requirement` / `--design` / `--test`

### 4. share branch 已 push，但没有落回主分支

这通常说明：

- 验证失败
- 基线分支在验证期间发生变化
- 基线分支被 policy 标记为必须走 PR

这种行为是预期的安全停止，不是脚本异常。

### 5. 分支越来越多

这是分支工作流的正常副作用，不是命名策略本身的问题。

建议团队额外配一条清理策略：

- share branch 落地后删除远端分支
- 只保留仍在 review、验证或排障中的分支
- 按 `base-branch-yyyyMMddHHmmss-slug` 规则做定期清理

## 当前实现的优点

- 流程边界清晰
- 把 Git 和 GitHub API 的职责分开了
- 有基础测试覆盖
- 支持 repo-local policy
- 支持 direct share-and-land，而不是只支持 PR

## 当前还不够好的地方

- `README.md` 之前和 `SKILL.md` 内容重复偏多，对人类使用者不够聚焦
- git 认证现在可以统一走 `HTTPS + CLAW_GITHUB_TOKEN`
- 缺少更强的“认证诊断”入口，比如自动提示当前是 SSH 还是 HTTPS、当前 token 是否可见
- `.git-orchestrator.json` 还是可选约定，不是强约束，导致不同仓库行为可能不一致

## 建议

- 把 repo policy 视为正式配置，而不是可选项
- 为团队统一 `verify.command`
- 明确哪些分支允许 share-and-land，哪些只能走 PR
- 临时 token 优先使用 `CLAW_GITHUB_TOKEN`，用完即删

## 相关文件

- [SKILL.md](/Users/zhanhd/Documents/products/github/claw-one-rs/skills/git-orchestrator/SKILL.md:1)
- [scripts/github_ops.py](/Users/zhanhd/Documents/products/github/claw-one-rs/skills/git-orchestrator/scripts/github_ops.py:1)
- [scripts/git_share_and_land.sh](/Users/zhanhd/Documents/products/github/claw-one-rs/skills/git-orchestrator/scripts/git_share_and_land.sh:1)
- [references/github_api_guide.md](/Users/zhanhd/Documents/products/github/claw-one-rs/skills/git-orchestrator/references/github_api_guide.md:1)
