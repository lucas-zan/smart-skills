---
name: tdd-workflow
description: >
  测试驱动的开发工作流，支持从单个 bug 修复到整个项目交付的全规模开发任务。
  工作流程：理解需求 → 分析代码 → 判断规模 → 生成含背景、原因、任务拆分、
  逻辑设计、测试设计、验收方式的 docs/todo list → 先按 todo 设计生成测试样例
  → 确认测试可失败 → 按任务顺序实现 → 用测试样例验收 → 更新 todo 状态，
  直到全部任务验证成功后才能交付。
  触发场景：(1) 用户要求开发新功能 (2) 用户要求修复 bug (3) 用户要求重构或改造代码
  (4) 用户要求启动或继续一个项目的开发 (5) 用户说"先写测试"或"测试驱动"
  (6) 用户给出设计文档并要求实施开发。
  不触发：纯研究/探索任务、文档编写、配置修改、简单的单行修改。
---

# TDD 开发工作流

## 核心约束

进入工作流后，先建立任务清单文件，再进入测试驱动开发。todo list 文件必须生成在 `docs/` 目录下，推荐命名为 `docs/todo-<task-slug>.md`。

todo list 不是简单备忘录，而是本轮开发的执行计划和验收合同。它必须先定义为什么要做、当前背景、范围边界、每个小任务、每个任务的逻辑设计、测试样例设计、验证命令、验收标准和停止条件。后续测试、实现、验收都必须以这个文件为准。

todo list 中的每个任务都必须使用以下状态之一：

- `待执行`
- `待测试验证`
- `验证成功`
- `验证失败`

只有当 todo list 中所有任务都达到 `验证成功`，本轮任务才算完成，才能交付给用户。

严格执行顺序：

1. 先分析需求和代码现状
2. 再创建/更新 `docs/todo-<task-slug>.md`
3. 按 todo 中的设计先写测试样例
4. 运行测试并确认新增测试能正确失败，或明确记录为什么无法制造失败态
5. 按 todo 的任务顺序逐项实现
6. 用该任务对应测试和验收命令验证
7. 验证通过后立即更新状态，再进入下一项
8. 全部任务为 `验证成功` 后才能交付

---

## Step 0: 判断任务规模

进入工作流后，首先判断任务属于哪个规模，后续流程会有差异：

| 规模 | 判断标准 | 示例 |
|------|---------|------|
| **S（小功能）** | 改动 1-3 个文件，单一职责 | 修复一个 bug、加一个工具函数、改一个接口字段 |
| **M（大功能）** | 改动 3-10 个文件，涉及多个模块协作 | 新增一个完整接口（controller + service + repo + test） |
| **L（项目级）** | 改动 10+ 文件，跨多个子系统，有设计文档 | 从零实现 QA 检索服务、重构整个认证模块 |

将判断结果告知用户，然后按对应流程执行。

---

## Step 1: 生成 todo list 文件

在编写任何测试样例之前，必须先生成 todo list 文件。

1. 在 `docs/` 目录下创建当前任务的 todo list 文件
2. 将任务拆分为可验证的最小项；S 规模通常 1-3 项，M/L 规模按模块或里程碑拆分
3. todo 文件必须包含完整背景、设计、测试和验收信息
4. 每个任务项必须能独立写测试、实现和验收
5. 新建时所有未开始任务默认标记为 `待执行`
6. 后续每完成一个任务项的测试、实现与验证，就立即回写 todo list 状态

推荐格式：

```md
# Todo: <任务名称>

> Executor instructions: Follow this todo step by step. Generate tests from
> the "Test design" section before implementation. Run each verification command
> and confirm the expected result before moving to the next task. If a STOP
> condition occurs, stop and report instead of improvising.

## Status

- **Priority**: P0/P1/P2/P3
- **Effort**: S/M/L
- **Risk**: LOW/MEDIUM/HIGH
- **Depends on**: none or explicit dependencies
- **Category**: bugfix/feature/refactor/security
- **Planned at**: current branch/commit when available

## Why this matters

**Background**: What user need, bug, refactor pressure, or design requirement triggered this work.

**Current state**: What the code does today, including relevant files, functions, routes, data flow, or observed failures.

**Impact**: What breaks, leaks, blocks, or becomes hard to maintain if this is not done.

**What improves**: What behavior, safety, extensibility, or user outcome improves when done.

## Scope

**In scope**:
- File/module/function changes that are allowed.

**Out of scope**:
- Related but intentionally deferred changes.

## Design

Describe the implementation logic before writing tests:
- Expected inputs, outputs, and constraints
- Core behavior and edge cases
- Boundaries around frameworks, storage, transport, SDKs, or vendors
- Dependency direction and integration points
- Error handling and state/conflict behavior

## Tasks

Use the overview table for scanning and the detailed task sections for execution.
Every task must have exactly one checked status box.

### Task overview

| ID | Task | Acceptance summary | Status |
|----|------|--------------------|--------|
| T1 | Short task name | Observable result or command success | 待执行 |
| T2 | Short task name | Observable result or command success | 待执行 |

### T1: Short task name

**Status**:
- [x] 待执行
- [ ] 待测试验证
- [ ] 验证成功
- [ ] 验证失败

**Why**:
Reason this task exists. Explain the business or technical background, risk, blocked workflow, or maintenance pressure.

**What to do**:
- Concrete file/module/function changes to make.
- Expected behavior after the task is complete.
- Inputs, outputs, constraints, and edge cases this task owns.

**Logic design**:
- How the implementation should work at a high level.
- Which contracts, interfaces, or boundaries should be used.
- How errors, invalid input, state changes, or conflicts should be handled.
- Which dependencies should be mocked, stubbed, or isolated.

**Test design**:
- Tests to write before implementation.
- Expected initial failure mode before implementation.
- Normal behavior cases.
- Edge, invalid input, error, and state/conflict cases when applicable.

**Acceptance**:
- Focused verification command and expected result.
- Relevant suite/build/lint command and expected result.
- Manual or observable check when automated verification is not enough.

**Done criteria**:
- [ ] Tests listed in this task's Test design were written before implementation
- [ ] New tests were run and confirmed to fail for the expected reason before implementation, or the exception is documented here
- [ ] Implementation follows this task's Logic design and stays inside this task's What to do
- [ ] Focused verification command passes
- [ ] Relevant suite/build/lint command passes when applicable
- [ ] Task overview row status matches this task status
- [ ] This task status is updated to `验证成功`

### T2: Short task name

**Status**:
- [x] 待执行
- [ ] 待测试验证
- [ ] 验证成功
- [ ] 验证失败

**Why**:
Reason this task exists.

**What to do**:
- Concrete file/module/function changes to make.

**Logic design**:
- How the implementation should work.

**Test design**:
- Tests to write before implementation.
- Expected initial failure mode before implementation.

**Acceptance**:
- Commands and expected results.

**Done criteria**:
- [ ] Tests listed in this task's Test design were written before implementation
- [ ] New tests were run and confirmed to fail for the expected reason before implementation, or the exception is documented here
- [ ] Implementation follows this task's Logic design and stays inside this task's What to do
- [ ] Focused verification command passes
- [ ] Relevant suite/build/lint command passes when applicable
- [ ] Task overview row status matches this task status
- [ ] This task status is updated to `验证成功`

## Test plan

List the concrete tests to create before implementation:
- Normal behavior tests
- Edge case tests
- Invalid input tests
- Error behavior tests
- State/conflict tests when applicable

## Verification commands

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Focused tests | `<test command>` | exit 0 after implementation; expected failure before implementation |
| Full relevant suite | `<test command>` | exit 0 |
| Format/lint/build | `<command>` | exit 0 |

## Done criteria

Final delivery gate:

- [ ] Every task's own Done criteria checklist is fully checked
- [ ] Every task has exactly one checked Status value, and it is `验证成功`
- [ ] Task overview shows every task as `验证成功`
- [ ] No STOP condition remains unresolved

## STOP conditions

Stop and report if:

- The current code differs materially from the Current state description
- Required test infrastructure is missing and cannot be added safely
- A dependency or external service cannot be isolated by mock/stub
- Verification still fails after the configured fix loop
- Completing the task would require out-of-scope changes
```

Todo 文件可以按项目需要增加 “Current state excerpts”、“Manual testing”、“Maintenance notes” 等小节，但不能删除背景、设计、任务、测试计划、验收命令、完成标准和停止条件。

### 任务拆分要求

每个任务必须满足：

- 有明确的业务/技术原因，不能只有“修改代码”
- 有具体要做的内容，说明要改哪些文件、模块、函数或行为
- 有实现逻辑设计，说明要怎么做，而不是只写结果
- 有测试设计，说明先写哪些测试样例
- 有验收方式，包含命令或可观察结果
- 有四种状态的 checklist，且任意时刻只能勾选一个状态
- 有自己的 Done criteria checklist，不能只依赖全局完成标准
- 能在通过验收后独立更新为 `验证成功`

任务不要拆得过碎。一次状态更新应对应一个可验证行为、接口、模块或风险点。

---

## S 规模：小功能 / Bug 修复

直接走 Phase 1 → 6 的单轮流程，不拆分出独立模块，但仍必须维护 todo list。

### Phase 1: 理解需求 + 分析代码

1. 明确目标：功能目标、输入输出、边界条件
2. 如果需求不清晰，用 AskUserQuestion 确认（不超过 3 个问题）
3. 用 Glob/Grep/Read 定位涉及的文件和现有模式
4. 简短总结：当前状态 + 改动范围

### Phase 2: 设计实现方案

1. 列出需要新增/修改的文件
2. 描述关键变更（函数签名、逻辑变化）
3. 将逻辑设计、测试设计、验收方式写入 todo list
4. 将当前待处理任务在 todo list 中保持为 `待执行`
5. 输出方案给用户；除非用户明确要求等待确认，否则继续执行

### Phase 3: 先写测试

1. 检测项目测试框架和约定
2. 严格根据 todo list 中该任务的 `Test design` 编写测试样例
3. 测试必须覆盖：正常路径、边界条件、非法输入、错误场景；涉及状态或并发冲突时必须覆盖状态/冲突行为
4. 对外部依赖用 mock/stub/fake 隔离
5. 运行新增测试，确认能正确**失败**
6. 如果无法制造失败态，必须在 todo list 中记录原因和替代验证方式
7. 测试样例生成并验证失败态后，将对应任务状态更新为 `待测试验证`

### Phase 4: 实现代码

1. 只实现当前 `待测试验证` 任务
2. 按 todo list 的逻辑设计实现，遵循现有代码风格
3. 不做需求范围外的改动
4. 当前任务未通过验收前，不开始下一项任务

### Phase 5: 验证 + 修复循环

1. 运行 todo list 中该任务的验收命令和相关测试
2. 全部通过：将对应任务状态更新为 `验证成功`
3. 有失败：将对应任务状态更新为 `验证失败`
4. 分析原因 → 修复 → 重新测试（最多 5 轮）
5. 修复后测试通过：将对应任务状态从 `验证失败` 更新为 `验证成功`
6. 5 轮后仍失败：保留 `验证失败`，停下来报告问题，请求用户指导

### Phase 6: 交付前检查

1. 检查 todo list 中是否所有任务均为 `验证成功`
2. 若存在 `待执行`、`待测试验证` 或 `验证失败`，则本轮任务不得交付
3. 全部为 `验证成功` 后，输出总结并交付

---

## M 规模：大功能

与 S 规模流程相同，但在 Phase 2 中增加模块拆分，并将每个模块同步到 todo list。

### Phase 2 补充：模块拆分

1. 将功能拆成 2-5 个可独立测试的模块
2. 确定模块间的依赖顺序
3. 用 TaskCreate 创建每个模块的子任务，用 addBlockedBy 标注依赖关系
4. 在 todo list 中为每个模块创建对应条目，初始状态为 `待执行`
5. 每个模块条目都必须包含 Why、What to do、Logic design、Test design、Acceptance、状态 checklist 和 Done criteria checklist
6. 输出拆分方案给用户；除非用户明确要求等待确认，否则继续执行

### Phase 3-6：按模块逐个执行

按依赖顺序，对每个模块执行：按 todo 设计写测试 → 确认测试失败 → 实现 → 验证 → 更新 todo 状态。

一个模块通过后再开始下一个。每完成一个模块：

1. 用 TaskUpdate 标记 completed
2. 将 todo list 中该模块状态更新为 `验证成功`

若模块验证失败，则立即将其状态更新为 `验证失败`，继续修复直到通过或达到上限。

全部模块完成后，运行一次完整测试套件确认无回归。只有 todo list 所有条目都为 `验证成功` 才能交付。

---

## L 规模：项目级开发

项目级任务需要额外的规划层，但 todo list 仍是强制步骤。

### Phase 0L: 需求与设计文档分析

1. 读取项目中的设计文档（如 `docs/` 目录）
2. 读取 CLAUDE.md 了解项目约定
3. 分析现有代码结构，明确哪些可复用
4. 总结：项目目标、技术约束、与现有代码的关系

### Phase 1L: 制定开发计划

1. 将项目拆分为多个**里程碑**（milestone），每个里程碑产出一个可独立验证的交付物
2. 每个里程碑再拆为具体的开发任务
3. 用 TaskCreate 创建所有任务，用 addBlockedBy 标注依赖
4. 在 todo list 中同步创建所有任务条目，初始状态为 `待执行`
5. 每个任务条目都必须包含 Why、What to do、Logic design、Test design、Acceptance、状态 checklist 和 Done criteria checklist
6. 输出完整计划给用户；除非用户明确要求等待确认，否则继续执行

拆分原则：
- 基础设施优先（数据库、配置、工具函数）
- 被依赖的模块先做（repository → service → controller）
- 每个任务都应有明确的验收标准

### Phase 2L: 逐任务执行

按任务顺序，对每个任务走 S/M 规模的 Phase 1-6 流程：

```text
TaskList → 取出下一个未阻塞的任务
  → TaskUpdate(in_progress)
  → todo 状态保持/更新为 待执行
  → 理解 → 补充/确认 todo 设计 → 按设计写测试 → 确认失败 → 实现 → 验证
  → todo 状态更新为 验证成功 或 验证失败
  → TaskUpdate(completed 或 blocked)
  → 回到 TaskList
```

### Phase 3L: 里程碑验收

每完成一个里程碑：

1. 运行该里程碑涉及的全部测试
2. 向用户汇报完成情况：已完成任务数、测试通过情况、已知问题
3. 将通过验收的里程碑任务保持为 `验证成功`
4. 确认是否继续下一个里程碑

### Phase 4L: 项目收尾

全部里程碑完成后：

1. 运行完整测试套件
2. 检查是否有遗漏的需求项
3. 检查 todo list 是否所有任务都为 `验证成功`
4. 若存在非 `验证成功` 项，则继续执行，不得交付
5. 全部通过后，输出项目完成总结：完成了什么、关键决策、已知限制

---

## 通用规则

- **先生成 todo list，再写测试**是新增核心约束。任何规模都不跳过。
- **todo list 必须包含背景、原因、任务拆分、逻辑设计、测试设计和验收方式**。缺少这些内容时不得开始写测试。
- **测试样例必须来自 todo list 的测试设计**。如果实现过程中发现设计不足，先更新 todo list，再补测试或改实现。
- **先测试后实现**仍然是核心约束。任何规模都不跳过测试。
- **必须确认新增测试的失败态**。若受限于环境或测试类型无法做到，必须在 todo list 中记录原因和替代验收。
- **每完成并验证一个 todo 项，就立即更新状态**，不能在最后一次性回填。
- **每个 todo 项都有自己的 Done criteria checklist**。完成任务时必须逐项勾选该任务自己的验收项，再将该任务状态更新为 `验证成功`。
- **一个任务验证成功后才能进入下一个任务**。不得批量实现多个 `待执行` 项后再统一验收。
- **任务状态只能使用这四种**：`待执行`、`待测试验证`、`验证成功`、`验证失败`。
- **todo list 全部为 `验证成功` 才能交付**。这是最终交付门槛。
- **极小改动例外**：改一个常量、修一个 typo 等，也应补一个最小 todo 项，并在验证后更新状态。
- **用户需求是写测试本身**：仍需先生成 todo list，再进入测试编写；此时跳过实现代码，但不能跳过验证和状态更新。
- **修复循环上限**：单个任务最多 5 轮。超过则暂停请求用户指导。
- **不做范围外改动**：只完成用户要求的内容，不顺手重构、不加未要求的功能。
- **进度追踪**：M/L 规模必须使用 TaskCreate/TaskUpdate 追踪进度，同时维护 docs 下的 todo list 文件。
