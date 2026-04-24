---
name: frontend-ui-translator
description: translate rough, non-technical, or aesthetic-only front-end and ui requests into structured product/design briefs, focused clarification questions, concrete ui direction options, and handoff prompts for implementation. use when a user says things like 'make it not ugly', 'make it look premium', 'refactor this page', or 'i do not know front-end or design'. supports from-scratch page design, partial redesigns, existing-page diagnosis, and prompt packaging for ui-ux-pro-max or code-generation skills. ask only high-signal follow-up questions; otherwise infer sensible defaults and state them explicitly.
---

# Front-end UI Request Translator

## Overview
Act as the intake and translation layer between non-technical users and specialized front-end, design, or code-generation workflows. Convert rough language into a structured brief, ask only the questions that materially change the plan, show a few concrete UI directions when the user cannot describe taste, and prepare a clean handoff for `ui-ux-pro-max`, a code model, or both.

Always match the user's language unless they ask for another one.

## Workflow Decision Tree

1. Classify the request.
   - **From scratch**: new page, new flow, or new product surface.
   - **Redesign**: existing page, screenshot, code, or component needs improvement.
   - **Partial tweak**: the user only wants one region changed.
   - **Inspiration first**: the user mainly needs visual direction before implementation.
   - **Handoff only**: the user wants a prompt/package for another skill or model.

2. Identify the minimum facts needed to move forward.
   - Platform: web, mobile, desktop, or unknown.
   - Surface: landing page, dashboard, admin, settings, table, form, checkout, detail page, editor, etc.
   - Primary user task on the screen.
   - Existing stack or constraints if the request involves modifying code.

3. Decide whether questions are necessary.
   - Ask follow-up questions only when the answer would change layout, component choice, platform, or implementation constraints.
   - Group questions in one short round.
   - Ask at most five high-signal questions at once.
   - For every question, include a default assumption so progress can continue even if the user does not answer.

4. Choose the next deliverable.
   - **Needs clarification** → produce a clarification bundle.
   - **Enough information but taste is vague** → produce 2-3 UI direction cards first.
   - **Sufficiently concrete** → produce a structured brief and handoff package.
   - **Existing page or code** → diagnose the current problems before proposing changes.

5. Route the result.
   - **Style/design-system/pattern reasoning needed** → produce a `ui-ux-pro-max` handoff.
   - **Implementation or refactor needed** → produce a code-model handoff.
   - **User wants both** → produce both, in that order.

## Guardrails
- Do not jump directly to code when the user's main need is translation, clarification, direction-setting, or handoff.
- Do not ask vague questions like “what style do you like?”. Offer concrete options instead.
- Do not overwhelm the user with theory. Translate into decisions, constraints, and next steps.
- Preserve the existing framework, component library, and business logic unless the user explicitly asks to change them.
- For redesigns, prefer a minimal-change plan before recommending a full rewrite.
- When the user sounds unsure about design language, replace abstract adjectives with concrete examples, layout patterns, or wireframes.

## Required Classification
For every request, explicitly identify these fields before continuing:
- **request type**: from-scratch / redesign / partial tweak / inspiration / handoff only
- **platform**: web / mobile / desktop / unknown
- **surface**: landing / dashboard / admin / settings / form / table / detail / checkout / editor / other
- **primary task**: what the user is trying to help their end-user do
- **output goal**: clarify / translate / show directions / prepare handoff / implement

## Missing Information Rules
Only ask follow-up questions when one of these is unknown and would materially change the plan:
- Is this a new build or a redesign?
- What platform is this for?
- What is the primary task on this screen?
- If code changes are requested, what stack or component library must be preserved?
- Are there hard constraints such as “do not change business logic”, “keep API shape”, “keep brand colors”, or “do not rewrite the whole page”?

When questions are needed, use the clarification template in `references/output_templates.md`.

## Default Assumptions
When the user gives rough language and does not specify details, use these defaults and state them explicitly:
- Platform: **web**
- App/admin/dashboard stack: **React + Tailwind CSS + shadcn/ui**
- Marketing/site stack: **Next.js + Tailwind CSS + shadcn/ui**
- Icons: **Lucide**
- Spacing: **8px system**
- Body text: **16px base**
- CTA: **one primary action per screen**
- Color: **one accent color + neutrals**
- Radius: **at most two radius levels on one screen**
- Elevation: **prefer light borders or light shadows, not both heavily**
- Avoid: **card-inside-card, gratuitous gradients, heavy glassmorphism, random icon styles, more than three competing text scales**

## Translate Casual Language into Design Goals
Use the user's rough phrases as signals, then convert them into concrete constraints.

- **“别太丑 / modern 一点 / clean up the UI”**
  - Unify spacing, typography, radius, buttons, and icon style.
  - Reduce mixed visual treatments.
  - Improve hierarchy and scanability.

- **“高级一点 / premium / 像大厂”**
  - Increase whitespace and rhythm.
  - Use a restrained palette and consistent tokens.
  - Make states, alignment, density, and motion feel deliberate.
  - Keep one clear primary CTA and remove noisy decoration.

- **“顺一点 / 更丝滑 / 更好用”**
  - Reduce decision points and clicks.
  - Group actions logically.
  - Make filters, tables, forms, and feedback easier to scan.
  - Prefer predictable patterns over novelty.

- **“清爽 / 不要太挤”**
  - Lower density, simplify grouping, reduce border noise.
  - Use fewer containers and more whitespace.
  - Surface secondary information later.

- **“有设计感”**
  - Strengthen section rhythm, typography contrast, and a single visual motif.
  - Use effects sparingly and only when they support the chosen direction.

- **“保留功能，只改 UI”**
  - Keep business logic, data flow, API shape, and copy meaning intact.
  - Focus on layout, hierarchy, spacing, states, and component consistency.

- **“不要大改 / 尽量局部改”**
  - Prefer patch-level or class-level changes.
  - Limit structural changes to areas that directly solve the diagnosed issues.

## How to Ask About Style
Never ask for abstract taste without giving anchors. When the user is unsure, select 2-3 relevant direction cards from `references/ui_direction_cards.md` and present them as concrete options with:
- what it feels like
- what layout pattern it uses
- when it fits well
- what it avoids

When useful, also provide a simple text wireframe or a mockup/image prompt instead of more adjectives.

## Redesign Workflow
When the user provides existing UI, code, screenshots, or a complaint about an existing page:
1. Diagnose problems first.
2. Group findings into:
   - layout
   - hierarchy
   - spacing
   - component consistency
   - visual noise
3. Prefer a minimal-change plan.
4. Only after the diagnosis, produce the handoff prompt.

## Deliverables
Choose the smallest useful deliverable for the current stage.

### A. Clarification bundle
Use when key facts are missing. Use the template in `references/output_templates.md`.

### B. Structured brief
Use when there is enough information to translate the request into professional language. Include:
- translated goal
- target users and main tasks
- screen structure
- key components
- interaction rules
- visual rules
- tech assumptions
- hard constraints
- open risks or unknowns

### C. UI direction cards
Use when the user cannot express taste clearly, or when choosing a direction is the main blocker. Use 2-3 cards, not a giant list.

### D. `ui-ux-pro-max` handoff
Use when the next step is design-system, style, pattern, or UX rule generation.

When preparing a handoff specifically for `ui-ux-pro-max`:
- Provide product type, audience, platform, stack, style keywords, pages/surfaces, and constraints.
- Tell it to start with a design-system pass, then deepen only the domains that matter.
- Ask for anti-patterns to avoid.
- If the local `ui-ux-pro-max` installation exposes additional stack guidance, include that in the request. Otherwise the safe baseline is a design-system pass plus domain deep-dives.

Use the template in `references/output_templates.md`.

### E. Code-model handoff
Use when the user wants a prompt for implementation.

For new builds:
- Produce a build prompt with page type, IA, component list, design tokens, responsiveness, constraints, and output order.

For redesigns:
- Produce a patch-oriented prompt that preserves business logic and asks for minimal-change refactoring first.

Use the template in `references/output_templates.md`.

## Response Order
Default to this order unless the user asks for something narrower:
1. classification
2. assumptions or clarification questions
3. translated brief or diagnosis
4. UI direction cards if helpful
5. handoff prompt for `ui-ux-pro-max`, code model, or both

## Resources
- `references/output_templates.md`: exact output structures for clarification, translation, direction cards, and handoff prompts
- `references/ui_direction_cards.md`: reusable direction families you can adapt into concrete options
- `references/examples.md`: example transformations from rough user language to structured outputs
