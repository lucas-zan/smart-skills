# Examples

## Example 1 — rough request for a new admin page

**Input**

> 做个后台列表页，别这么丑，筛选和表格顺一点，重点按钮明显一点。我不懂前端，你帮我转成模型能执行的。

**Good transformation**

- Classify as: from-scratch or redesign of a dashboard/list page (ask if this is a new page or an existing one)
- Default platform: web
- Default stack: React + Tailwind CSS + shadcn/ui
- Translate goals into: improve scan efficiency, make primary action obvious, use a standard header + filter bar + table + detail pattern
- Offer 2-3 direction cards such as Precision SaaS, Commerce Utility, and Calm Content-First
- Then produce:
  1. a structured brief
  2. a `ui-ux-pro-max` handoff for design-system guidance
  3. a patch-oriented or build-oriented code prompt depending on whether this is existing UI

## Example 2 — redesign with constraints

**Input**

> 这个页面太挤了，但不要重写，逻辑和接口都别动，主要整理头部、筛选区和按钮。

**Good transformation**

- Classify as: partial tweak / redesign
- Preserve: business logic, API shape, state management, copy meaning
- Diagnose before solving:
  - layout: crowded header and toolbar grouping
  - hierarchy: too many same-weight actions
  - spacing: cramped vertical rhythm
  - component consistency: mixed button treatments
  - visual noise: too many borders/shadows
- Produce a minimal-change plan and a patch-oriented code prompt
- Only show style direction cards if the user is unsure about the desired feel

## Example 3 — taste is vague, user needs concrete options

**Input**

> 官网首页想要高级一点，但我不会描述。

**Good transformation**

- Classify as: from-scratch or inspiration first
- Avoid asking “what style do you like?”
- Instead present 2-3 concrete options, for example:
  - Premium Product Marketing
  - Premium Minimal
  - Calm Content-First
- For each option, explain what it feels like, when it fits, and what layout pattern it implies
- After the user picks a direction, generate the structured brief and the handoff prompt
