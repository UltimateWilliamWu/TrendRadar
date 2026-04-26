# TrendRadar 金融研究看板

这是我基于 [sansan0/TrendRadar](https://github.com/sansan0/TrendRadar) 维护的金融新闻版仓库。
目标不是做泛热点聚合，而是围绕宏观、市场、监管、产业链和重点公司，生成可长期运行的个人研究看板。

当前 README 反映的是本仓库 `master` 分支的实际状态，而不是上游默认说明。

## 1. 项目定位

- 以金融新闻、宏观数据、监管口径和市场热榜为核心。
- 默认同时保留一部分大众新闻源，用来观察宏观事件向舆论层扩散的速度。
- 通过 GitHub Actions 定时抓取，通过 GitHub Pages 发布静态页面。
- 在上游项目基础上，额外强化了金融关键词、AI 分析口径、RSS 输入质量和展示结构。

## 2. 当前主分支状态

- 默认运行配置：[config/config.yaml](config/config.yaml)
- 金融模板配置：[config/config-finance.yaml](config/config-finance.yaml)
- 调度预设：`morning_evening`
- GitHub Actions 定时：北京时间 `09:00 / 12:00 / 15:00 / 20:00`
- GitHub Pages 部署入口：根目录 [index.html](index.html)
- 报告展示主模式：`keyword`
- 筛选模式：`keyword`
- RSS 新鲜度过滤：`3` 天

当前主分支为了验证 AI 研究输出，白天和手动运行也允许触发 AI 分析。
如果后续要恢复成“只在晚间做一次 AI 总结”的省 token 模式，只需要回调 [config/timeline.yaml](config/timeline.yaml)。

## 3. 当前默认数据源

### 热榜 / 快讯源

- 今日头条
- 百度热搜
- 华尔街见闻 最热
- 华尔街见闻 快讯
- 华尔街见闻 最新
- 财联社热门
- 格隆汇
- 雪球
- 金十数据
- 快讯通
- 澎湃新闻
- 凤凰网

### RSS 源

当前主配置启用的 RSS 源：

- 雅虎财经
- 美联储货币政策
- SEC 新闻稿
- BLS Latest Numbers
- 美国 CPI
- 美国 PPI
- 中新网财经
- 国家统计局-最新发布
- 国家统计局-数据解读

当前默认禁用的 RSS 源：

- Hacker News
- 阮一峰的网络日志
- 新华网财经

禁用原因很明确：

- `Hacker News` 偏泛科技，不符合当前金融主线。
- `阮一峰` 与项目目标不相关。
- `新华网财经` RSS 长期停留在旧内容，已经不适合继续作为实时源。

## 4. AI 分析链路

当前 AI 分析不是简单的“标题总结”，而是分层喂数：

- 热榜：只保留标题、来源、排名轨迹、出现次数
- 普通 RSS：标题 + 发布时间 + summary
- 高价值 RSS：标题 + summary + 正文片段

当前高价值 RSS 增强源包括：

- 美联储货币政策
- SEC 新闻稿
- BLS Latest Numbers
- 美国 CPI
- 美国 PPI
- 雅虎财经
- 中新网财经

AI 分析相关配置：

- 模型总配置：[config/config.yaml](config/config.yaml) 的 `ai`
- AI 分析配置：[config/config.yaml](config/config.yaml) 的 `ai_analysis`
- 分析提示词：[config/ai_analysis_prompt.txt](config/ai_analysis_prompt.txt)

当前提示词目标是：

- 主线最多 `3` 条
- 明确区分宏观、行业、个股
- 对重要判断尽量标注证据强弱
- `signals` 和 `outlook_strategy` 尽量按 `日内 / 1周 / 1月` 分层

GitHub Actions 日志里会打印 token 信息，便于估算成本：

```text
[AI] 输入: hotlist_used=... rss_used=... rss_summary=... rss_snippet=...
[AI] Token usage: prompt=... completion=... total=...
```

## 5. 快速开始

### 本地运行

推荐使用 `uv`：

```bash
uv sync
uv run python -m trendradar
```

Windows 也可以直接用：

```bash
setup-windows.bat
```

运行后重点看这些产物：

- [output](output)
- [output/html/latest/current.html](output/html/latest/current.html)
- [output/html/latest/daily.html](output/html/latest/daily.html)
- [index.html](index.html)

### GitHub Actions 手动运行

在仓库的 Actions 页面手动运行 `Get Hot News` 即可。
执行链路是：

1. 抓取热榜和 RSS
2. 生成 HTML / 文本 / 按日期归档
3. 自动提交 [output](output) 和 [index.html](index.html)
4. 触发 `Deploy Pages`

### 最小 AI Secrets

如果只想让 AI 分析跑起来，最少需要：

- `AI_API_KEY`
- `AI_MODEL`

当前仓库支持在 GitHub Secrets 中直接覆盖模型。
例如：

```text
AI_MODEL = openai/gpt-5.4-mini
```

## 6. GitHub Pages 与部署逻辑

工作流文件：

- [.github/workflows/crawler.yml](.github/workflows/crawler.yml)
- [.github/workflows/deploy-pages.yml](.github/workflows/deploy-pages.yml)

当前部署逻辑：

- `Get Hot News` 负责抓取、生成、归档、提交产物
- `Deploy Pages` 负责把站点打包到 `_site`
- Pages 主要发布这些内容：
  - [index.html](index.html)
  - [output/index.html](output/index.html)
  - [output/html/latest/current.html](output/html/latest/current.html)
  - [docs](docs)

注意：

- 根首页展示的是仓库根目录的 [index.html](index.html)
- `daily.html` 会在本地产出，但当前 Pages 工作流没有单独把它作为公开入口复制出来

## 7. 关键配置文件说明

- [config/config.yaml](config/config.yaml)
  主运行配置。GitHub Actions 默认就用它。

- [config/config-finance.yaml](config/config-finance.yaml)
  更偏纯金融的模板配置，保留了可选源，适合做窄化实验。

- [config/frequency_words.txt](config/frequency_words.txt)
  关键词分组体系，决定页面顶部板块如何聚合。

- [config/timeline.yaml](config/timeline.yaml)
  调度策略。决定什么时间段抓取、分析、推送，以及用 `current` 还是 `daily`。

- [config/ai_analysis_prompt.txt](config/ai_analysis_prompt.txt)
  当前研究口径提示词。

## 8. 当前仓库结构

```text
TrendRadar/
├─ .github/workflows/      # GitHub Actions 工作流
├─ config/                 # 主配置、金融模板、提示词、时间线
├─ trendradar/             # 抓取、分析、报告生成主程序
├─ mcp_server/             # MCP Server 相关代码
├─ docs/                   # 上游文档和静态资源
├─ output/                 # 生成结果、RSS 存档、HTML 归档
├─ index.html              # Pages 根入口页
├─ pyproject.toml          # Python 项目定义
├─ uv.lock                 # uv 锁文件
├─ requirements.txt        # 兼容安装依赖
├─ setup-windows.bat       # Windows 初始化脚本
├─ setup-mac.sh            # macOS 初始化脚本
├─ start-http.bat          # Windows 本地静态服务
└─ start-http.sh           # macOS / Linux 本地静态服务
```

职责上可以这样理解：

- `config/` 决定抓什么、怎么分组、什么时候分析
- `trendradar/` 决定怎么抓、怎么分析、怎么生成页面
- `output/` 存放所有运行结果
- `index.html` 是线上入口

## 9. 同步上游项目

建议保留 `upstream` 指向原项目：

```bash
git fetch upstream
git checkout master
git merge upstream/master
```

每次同步上游后，优先检查这些文件：

- [config/config.yaml](config/config.yaml)
- [config/config-finance.yaml](config/config-finance.yaml)
- [config/timeline.yaml](config/timeline.yaml)
- [config/ai_analysis_prompt.txt](config/ai_analysis_prompt.txt)
- [.github/workflows/crawler.yml](.github/workflows/crawler.yml)
- [.github/workflows/deploy-pages.yml](.github/workflows/deploy-pages.yml)

这些文件既容易被上游更新，也最容易承载你的本地定制。

## 10. 维护建议

- 主运行配置尽量只维护一套稳定的 [config/config.yaml](config/config.yaml)
- 新源先加到模板或单独分支验证，再进主配置
- 先看数据源质量，再调 prompt；不要用 prompt 去硬补垃圾输入
- AI 成本控制优先靠调度和输入分层，不要只靠缩短输出
- 每次改 AI 逻辑后，先看 GitHub Actions 日志里的 token 使用情况

## 致谢

- 原项目作者：[sansan0/TrendRadar](https://github.com/sansan0/TrendRadar)
- 本仓库在原项目基础上，持续做金融化配置、AI 分析调整、部署维护和上游同步
