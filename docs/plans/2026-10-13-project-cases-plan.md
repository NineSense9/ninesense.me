# 外包项目案例 Implementation Plan

> For agentic workers: implement inline with executing-plans, following the user-approved design. Private preview sources stay outside every website Git checkout.

**Goal:** Publish two truthful, illustrated development case studies and reorganize selected work.

**Architecture:** Static HTML detail pages share CSS and a native-dialog image viewer. Existing homepage receives a project layout stylesheet and a competition section. Screenshots come from isolated local applications and contain built-in demonstration data.

**Tech Stack:** HTML/CSS/JavaScript, Python, Next.js, FastAPI, Playwright.

## Tasks

### 1. Local demonstration evidence

- [x] Extract nested source archives to the dedicated temporary preview directory outside the website repository.
- [x] Create a private Python environment; install both projects and use installed Chrome. Install VeriFlow frontend dependencies with `npm ci`.
- [x] Run VeriFlow API on `127.0.0.1:8410`, frontend on `127.0.0.1:3301`; run GhostQA on `127.0.0.1:8788`.
- [x] Capture workflow failure, rule repair and overview; capture cart exploration, state graph and confirmed report with no model key. Close preview processes at completion.
- [x] Save only six reviewed, compressed screenshots under `site/assets/projects/`.

### 2. Static contracts before implementation

Create `tests/project-pages.test.cjs` using Node's built-in test runner. Check two routes, truthful role text, six local images, native viewer, local-only case links, the new competition section and sitemap entries. Check absent video/download/customer repository links and private addresses.

```powershell
node --test tests/project-pages.test.cjs
```

Expected initially: failed assertions for missing pages and homepage project navigation. Expected after implementation: all assertions pass.

### 3. Detail pages and shared assets

Create `site/projects/{veriflow,ghostqa}/index.html`, `site/projects/projects.css` and `site/projects/projects.js`. Both pages share a warm neutral palette, summary metadata, collaboration strip, three-image case narrative, decision notes and delivery summary. Use semantic headings, visible focus, responsive figures and original-size images.

Viewer contract:

```html
<button class="shot-open" data-full="/assets/projects/veriflow-issue.webp" aria-label="放大缺陷定位截图"><img loading="lazy" alt="内置流程缺少审题门的检查结果"></button>
<dialog id="image-viewer" aria-label="截图预览"><button type="button" data-close>关闭</button><img alt=""><p></p></dialog>
```

- [x] Use `showModal()`; populate image and caption with DOM properties; close with Escape, close button or backdrop; clear source and restore originating focus on close.
- [x] Add independent page title, description, canonical URL and share image.

### 4. Homepage organization

- [x] Replace `#work` with two equal primary project cards and a full-width secondary operations project.
- [x] Move existing competition identity and four award images to `#competitions`; add desktop/mobile competition navigation.
- [x] Add the user's actual KIMI → ChatGPT → Grok collaboration flow to `#build`; identify older tool screenshots as other workflows.
- [x] Add the two canonical project URLs to `site/sitemap.xml`.

### 5. Acceptance and release

- [x] Run project contracts and existing static/deployment contracts.
- [x] Inspect pages at desktop and 390px width, exercise both routes, screenshot dialog, Escape, restored focus and absence of horizontal overflow.
- [x] Review the staged file list and public content for private source/runtime files, customer references, repository/demo links and video resources.
- [ ] Commit, integrate into main, push, publish static files to a new server release and switch the current symlink. Check public page/image HTTP status and deployed content. Keep prior release for rollback.
