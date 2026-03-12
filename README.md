# TrendRadar 金融新闻版

这是我基于 [sansan0/TrendRadar](https://github.com/sansan0/TrendRadar) 维护的金融新闻抓取与展示 fork。
保留了原项目的爬虫、报表、通知、GitHub Actions 和 GitHub Pages 能力，但默认配置已调整为更适合金融新闻、宏观快讯、市场热榜和舆情跟踪的使用方式。

## 1. 仓库定位

- 以金融新闻和宏观快讯为主线，优先抓取市场相关的热榜与快讯源。
- 保留头条、百度、微博、知乎等大众平台，用于观察热点事件的跨平台扩散。
- 默认适配 GitHub Actions + GitHub Pages，适合做自动抓取和静态页面展示。
- 配置上分为“主运行配置”和“金融模板配置”，便于日常运行和按需切换。

## 2. 当前配置概览

### 主运行配置 `config/config.yaml`

这是仓库现在默认使用的配置，也是 GitHub Actions `Get Hot News` 实际使用的配置。

- 默认线上分支：`master`
- 默认部署链路：`Get Hot News` -> `Deploy Pages`
- GitHub Actions 定时抓取（北京时间）：09:00 / 12:00 / 15:00 / 20:00
- 独立展示区默认保留：知乎, 华尔街见闻 最热

当前启用的热榜源：

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
- bilibili 热搜
- 凤凰网
- 贴吧
- 微博
- 抖音
- 知乎

主配置里保留的 RSS 源：

- Hacker News
- 阮一峰的网络日志
- 雅虎财经

这套组合的设计思路是：用金融快讯源提供市场变化，用大众热点源观察事件传播和舆情扩散，最终在一个页面上同时看到市场、宏观、政策和舆情几个维度。

### 金融模板配置 `config/config-finance.yaml`

这是我保留的“更窄更纯的金融版配置模板”，适合你想临时把抓取范围收缩到市场和宏观为主时使用。

模板里的默认热榜源：

- 华尔街见闻 最热
- 华尔街见闻 快讯
- 华尔街见闻 最新
- 财联社热门
- 格隆汇
- 雪球
- 金十数据
- 快讯通
- 百度热搜
- 今日头条
- 知乎
- 微博

模板里的 RSS 源：

- 路透中文-财经
- 路透中文-要闻
- FT 中文网
- WSJ Markets
- 彭博中国财经

适合的场景：

- 只想重点盯盘、盯宏观、盯市场消息时。
- 想降低娱乐和泛热点噪音时。
- 想把 Pages 页面更明显地收束到财经主题时。

### 关键词统计体系 `config/frequency_words.txt`

在原项目关键词体系基础上，我增加了这几组更偏金融的分组：

- `CN Equities`
- `US Equities`
- `Macro Rates`
- `Macro Data`
- `Capital Markets`
- `Sectors`

对应的理解可以简化成：

- `CN Equities`：A 股、港股、主要中资市场指数与板块
- `US Equities`：美股、纳指、标普、道指、中概股
- `Macro Rates`：汇率、利率、加息、降准等宏观利率线索
- `Macro Data`：CPI、PPI、GDP、PMI、货币政策等宏观数据
- `Capital Markets`：IPO、回购、减持、融资融券、南北向资金
- `Sectors`：ETF、半导体、AI 算力、光伏、新能源车、储能等行业主题

## 3. 怎么用

### 本地运行

如果本机已经安装 `uv`，推荐直接这样运行：

```bash
uv sync
uv run python -m trendradar
```

Windows 下也可以直接运行：

```bash
setup-windows.bat
```

运行完成后主要看这几个输出：

- `output/`
- `output/html/latest/current.html`
- `index.html`

### 切换到纯金融模板

如果你想临时切换到更纯的金融抓取范围，可以先备份再覆盖主配置：

```bash
copy config\config.yaml config\config.yaml.bak
copy config\config-finance.yaml config\config.yaml
```

macOS / Linux 下对应命令：

```bash
cp config/config.yaml config/config.yaml.bak
cp config/config-finance.yaml config/config.yaml
```

切换后再执行一次本地运行或手动触发 `Get Hot News`，就能看到更偏财经的页面。

### GitHub Actions / Pages

仓库当前的自动化链路是：

1. `Get Hot News` 定时或手动运行
2. 生成最新的 HTML 、文本和归档结果
3. 提交 `output/` 和 `index.html`
4. `Deploy Pages` 自动发布到 GitHub Pages

如果你想立刻刷新页面，推荐这样做：

1. 到 GitHub Actions 手动运行一次 `Get Hot News`
2. 等待该 workflow 跑完
3. 确认 `Deploy Pages` 自动开始
4. 打开 GitHub Pages 页面验收最新结果

## 4. 标准化维护流程

推荐长期按下面这套流程用这个仓库：

1. 先改 `config/config.yaml` ，决定要抓哪些源
2. 再改 `config/frequency_words.txt` ，决定怎么做金融主题分组
3. 本地执行 `uv run python -m trendradar`
4. 重点检查 `output/html/latest/current.html` 是否正常
5. 确认页面中源名、关键词分组、时间戳都显示正确
6. `git add` / `git commit` / `git push origin master`
7. 观察 `Get Hot News` 和 `Deploy Pages` 是否成功
8. 最后再检查 GitHub Pages 线上页面

这套流程的原则可以概括成：

- 先定数据范围
- 再定分析分组
- 然后做本地验证
- 最后再推到线上

## 5. 仓库结构

```text
TrendRadar/
?? .github/workflows/        # GitHub Actions??????
?? config/                   # ??????????????
?? trendradar/               # ????????????????
?? mcp_server/               # MCP ??????
?? output/                   # ??????????HTML ??
?? index.html                # GitHub Pages ??
?? requirements.txt          # ????
?? pyproject.toml            # ??????????
?? setup-windows.bat         # Windows ??????
?? setup-mac.sh              # macOS ??????
?? start-http.bat            # ????????
?? start-http.sh             # ????????
```

可以这样理解整个仓库的职责分层：

- `config/` 只放配置
- `trendradar/` 只放程序逻辑
- `output/` 只放生成结果
- `index.html` 作为 Pages 入口页

## 6. 后续同步上游

如果原项目继续更新，推荐保留 `upstream` 远程，并按下面的方式同步：

```bash
git fetch upstream
git checkout master
git merge upstream/master
```

同步后优先检查这些文件有没有冲突：

- `config/config.yaml`
- `config/config-finance.yaml`
- `config/frequency_words.txt`
- `.github/workflows/crawler.yml`
- `.github/workflows/deploy-pages.yml`
- `README.md`

这些是这个 fork 里最容易既被上游更新、又被我自己改过的文件。

## 7. 维护原则

- 线上默认只维护一套稳定的 `config/config.yaml`
- 实验性改动先放在 `config/config-finance.yaml` 或单独模板
- 每次改源后都先检查源名是否正常显示
- 每次改关键词后都先看分组是否真的提升分析质量
- 每次同步上游后，优先检查配置文件结构是否有 breaking change

## 8. 适用场景

- 每天固定时间查看金融热点和宏观快讯
- 跟踪市场事件在大众平台上的传播路径
- 做个人公开新闻看板
- 在不自建后端服务的情况下做轻量监控

## 致谢

- 原项目作者：[sansan0/TrendRadar](https://github.com/sansan0/TrendRadar)
- 本仓库在原项目基础上做了金融化配置、工作流和展示维护

如果只想快速理解这个仓库的使用方式，可以记住这五句话：

- `config/config.yaml` 是线上默认版
- `config/config-finance.yaml` 是更纯金融的备用版
- `config/frequency_words.txt` 决定金融主题怎么被统计
- `master` 是线上分支
- GitHub Actions 负责抓取，GitHub Pages 负责展示
