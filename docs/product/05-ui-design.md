# ARC UI 设计系统（Claude 暖色编辑风格）

> **版本**：v0.1  
> **参考**：用户提供的 Claude / Anthropic 营销面设计分析（`DESIGN-claude.md`）  
> **适用范围**：日报 HTML、静态站点、周会 HTML 预览；PPTX 尽量对齐色板与层级  
> **实现**：CSS 变量 + Jinja2 模板（见 Tech Spec 渲染主路径）

本系统**采用其审美气质与 token 结构**，不使用 Anthropic 商标字形 / spike-mark。展示字体用开源替代。

---

## 1. 设计意图

ARC 日报应读起来像**温暖的编辑部晨报**，而不是冷灰 SaaS 控制台：

- 画布：暖奶油色，而非纯白 / 冷灰
- 标题：衬线展示体（文学感）+ 正文人文无衬线
- 强调色：暖珊瑚，少而准（CTA、关键决议、头版标记）
- 节奏：奶油页 ↔ 浅奶油卡片 ↔ 深色「产品/证据」面

与产品原则一致：头版克制、证据可折叠、动作清晰；视觉服务可读与决策，不堆卡片噪声。

---

## 2. Token（权威色板）

```yaml
colors:
  primary: "#cc785c"           # 珊瑚 CTA / 头版强调
  primary-active: "#a9583e"
  primary-disabled: "#e6dfd8"
  ink: "#141413"
  body: "#3d3d3a"
  body-strong: "#252523"
  muted: "#6c6a64"
  muted-soft: "#8e8b82"
  hairline: "#e6dfd8"
  hairline-soft: "#ebe6df"
  canvas: "#faf9f5"
  surface-soft: "#f5f0e8"
  surface-card: "#efe9de"
  surface-cream-strong: "#e8e0d2"
  surface-dark: "#181715"      # 证据包 / 代码 / Claim 深色区
  surface-dark-elevated: "#252320"
  surface-dark-soft: "#1f1e1b"
  on-primary: "#ffffff"
  on-dark: "#faf9f5"
  on-dark-soft: "#a09d96"
  accent-teal: "#5db8a6"       # GO / success 点缀（少用）
  accent-amber: "#e8a55a"      # WATCH
  success: "#5db872"
  warning: "#d4a017"
  error: "#c64545"             # NO-GO / 错误
```

CSS 变量命名建议：`--arc-canvas`、`--arc-primary`、`--arc-ink` …（实现时与上表一一对应）。

---

## 3. 字体

| 角色 | 首选（开源替代） | 回退 |
|------|------------------|------|
| Display（h1–h3、头版结论） | **Cormorant Garamond** 400/500 | EB Garamond, Georgia, serif |
| UI / Body | **Inter** 400/500 | system-ui, sans-serif |
| Code / TeX 片段 | **JetBrains Mono** | ui-monospace, monospace |

原则：

- Display **不要用粗体 700**；靠字号与负字距建立层级
- Display letter-spacing 约 `-0.02em`～`-0.04em`
- 正文行高约 `1.55`；日报舒适阅读优先

加载：HTML 模板可用 Google Fonts 或自托管 woff2；离线场景回退系统字体。

---

## 4. 形状与间距

```yaml
rounded:
  sm: 6px
  md: 8px      # 按钮、输入、反馈控件
  lg: 12px     # 内容块、论文卡
  xl: 16px     # 头版主容器
  pill: 9999px # 决议徽章

spacing:
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  section: 64px   # 日报可略紧于营销站 96px，屏上阅读友好
```

深度：**色块优先，少阴影**。默认无 box-shadow；悬停可用极轻 `0 1px 3px rgba(20,20,19,0.08)`。

---

## 5. ARC 组件映射

| ARC 元素 | 视觉处理 |
|----------|----------|
| 页面底 | `canvas` |
| 顶栏（日期 / 频道） | `canvas` + ink；导航用 Inter 14/500 |
| 头版结论区 | 大号 Cormorant；序号可用珊瑚小标记 |
| Research State Changes | `surface-card` 块；无变化时用 muted 文案，勿假警报 |
| 论文精读卡 | `surface-card`；标题 Inter title；决议徽章 pill |
| 证据 / Claim / 附录原始 JSON | `surface-dark` + `on-dark` + Mono（对照 Claude code-window） |
| 动作列表 | 清晰有序列表；主动作按钮 `primary` |
| GO | teal 点或左边线 |
| WATCH | amber |
| NO-GO / 错误 | error 红，保持克制，勿整页红 |
| READ / TRY | ink 或珊瑚描边按钮 |
| 页脚 | `surface-dark` + `on-dark-soft` |

### 决议徽章

```text
READ / TRY / WATCH / ARCHIVE / NO-GO / UPDATE
```

小 pill：浅底 + ink；`NO-GO` 可用浅红底；当日「建议执行」的 TRY 可用珊瑚填充。

### 反馈按钮行

次要按钮：canvas + hairline 边；主反馈（值得精读）用珊瑚。圆角 `md`，高度约 40px。

---

## 6. 日报版式（第一屏）

头版应是**单一构图**，不是仪表盘：

1. 品牌/产品名 **ARC**（展示级，勿被副标题压过）
2. 一行日期与模式（Daily Lite / Deep）
3. 至多三条结论（结论 + 一句为何重要）
4. 一条短支撑（今日有无 State 变化）
5. 主 CTA 组：今日动作（≤3）或「无需行动」

不要在第一屏堆：完整候选表、成本明细、原始评分、多列统计条。这些进附录 / 折叠。

---

## 7. Do / Don’t

**Do**

- 奶油画布打底；珊瑚只用于 CTA 与少量强调
- 深色面承载证据与代码，形成节奏
- 衬线标题 + 无衬线正文

**Don’t**

- 冷灰/纯白底、紫蓝渐变、大面积 glow
- 处处珊瑚或满屏卡片阴影
- 用 Inter/无衬线做头版大标题（会丢掉编辑气质）
- 复制 Anthropic spike-mark 作为 ARC logo

---

## 8. 落地文件（规划）

```text
templates/
  styles/
    tokens.css      # CSS 变量 = 本文件色板
    report.css      # 日报/周报排版
  daily/
    base.html.j2
  weekly/
    base.html.j2
```

PPTX：主题色对齐 `primary` / `ink` / `canvas`；标题可用衬线字体（若系统有）。

---

## 9. 与产品文档关系

| 文档 | 关系 |
|------|------|
| PRD | 阅读时长、头版克制 → 本文件第一屏规则 |
| Architecture §9 | HTML 主路径采用本设计系统 |
| Tech Spec | Jinja2 模板引用 `tokens.css` |
| Acceptance | P1 HTML「可读、可反馈」需符合本色板与第一屏结构 |
