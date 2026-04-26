# coding=utf-8
"""
AI analysis module.

This version keeps the existing frontend JSON schema but upgrades the AI input
pipeline in three ways:
1. RSS summaries are preserved and sent to the model.
2. High-value RSS sources can add short article snippets.
3. Prompt assembly is layered by source type while logging token usage.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from trendradar.ai.client import AIClient
from trendradar.ai.prompt_loader import load_prompt_template
from trendradar.ai.rss_enrichment import RSSContentEnricher


@dataclass
class AIAnalysisResult:
    """Structured AI analysis result."""

    core_trends: str = ""
    sentiment_controversy: str = ""
    signals: str = ""
    rss_insights: str = ""
    outlook_strategy: str = ""
    standalone_summaries: Dict[str, str] = field(default_factory=dict)

    raw_response: str = ""
    success: bool = False
    skipped: bool = False
    error: str = ""

    total_news: int = 0
    analyzed_news: int = 0
    max_news_limit: int = 0
    hotlist_count: int = 0
    rss_count: int = 0
    ai_mode: str = ""

    rss_summary_count: int = 0
    rss_enriched_count: int = 0
    prompt_chars: int = 0
    estimated_prompt_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class AIAnalyzer:
    """AI analyzer."""

    def __init__(
        self,
        ai_config: Dict[str, Any],
        analysis_config: Dict[str, Any],
        get_time_func: Callable,
        debug: bool = False,
    ):
        self.ai_config = ai_config
        self.analysis_config = analysis_config
        self.get_time_func = get_time_func
        self.debug = debug

        self.client = AIClient(ai_config)

        valid, error = self.client.validate_config()
        if not valid:
            print(f"[AI] 配置警告: {error}")

        self.max_news = analysis_config.get("MAX_NEWS_FOR_ANALYSIS", 50)
        self.include_rss = analysis_config.get("INCLUDE_RSS", True)
        self.include_rss_summary = analysis_config.get("INCLUDE_RSS_SUMMARY", True)
        self.rss_summary_max_chars = analysis_config.get("RSS_SUMMARY_MAX_CHARS", 180)
        self.include_rank_timeline = analysis_config.get("INCLUDE_RANK_TIMELINE", False)
        self.include_standalone = analysis_config.get("INCLUDE_STANDALONE", False)
        self.language = analysis_config.get("LANGUAGE", "Chinese")

        self.rss_enrichment_config = analysis_config.get("RSS_ENRICHMENT", {})
        self.rss_source_policies = self._build_rss_source_policies(
            self.rss_enrichment_config.get("SOURCES", [])
        )
        self.rss_enricher = RSSContentEnricher(
            source_policies=self.rss_source_policies,
            timeout=self.rss_enrichment_config.get("TIMEOUT", 12),
            debug=debug,
        )

        self.system_prompt, self.user_prompt_template = load_prompt_template(
            analysis_config.get("PROMPT_FILE", "ai_analysis_prompt.txt"),
            label="AI",
        )

    def analyze(
        self,
        stats: List[Dict],
        rss_stats: Optional[List[Dict]] = None,
        report_mode: str = "daily",
        report_type: str = "当日汇总",
        platforms: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        standalone_data: Optional[Dict] = None,
    ) -> AIAnalysisResult:
        """Run AI analysis."""
        model = self.ai_config.get("MODEL", "unknown")
        api_key = self.client.api_key or ""
        api_base = self.ai_config.get("API_BASE", "")
        masked_key = f"{api_key[:5]}******" if len(api_key) >= 5 else "******"
        model_display = model.replace("/", "/\u200b") if model else "unknown"

        print(f"[AI] 模型: {model_display}")
        print(f"[AI] Key : {masked_key}")

        if api_base:
            print("[AI] 接口: 存在自定义 API 端点")

        timeout = self.ai_config.get("TIMEOUT", 120)
        max_tokens = self.ai_config.get("MAX_TOKENS", 5000)
        print(f"[AI] 参数: timeout={timeout}, max_tokens={max_tokens}")

        if not self.client.api_key:
            return AIAnalysisResult(
                success=False,
                error="未配置 AI API Key，请在 config.yaml 或环境变量 AI_API_KEY 中设置。",
            )

        news_content, rss_content, content_meta = self._prepare_news_content(stats, rss_stats)
        hotlist_total = content_meta["hotlist_total"]
        rss_total = content_meta["rss_total"]
        analyzed_count = content_meta["analyzed_count"]
        total_news = hotlist_total + rss_total

        if not news_content and not rss_content:
            return AIAnalysisResult(
                success=False,
                skipped=True,
                error="本轮无可用于 AI 的新闻内容，跳过分析。",
                total_news=total_news,
                hotlist_count=hotlist_total,
                rss_count=rss_total,
                analyzed_news=0,
                max_news_limit=self.max_news,
            )

        current_time = self.get_time_func().strftime("%Y-%m-%d %H:%M:%S")
        if not keywords:
            keywords = [item.get("word", "") for item in stats if item.get("word")] if stats else []

        user_prompt = self.user_prompt_template
        user_prompt = user_prompt.replace("{report_mode}", report_mode)
        user_prompt = user_prompt.replace("{report_type}", report_type)
        user_prompt = user_prompt.replace("{current_time}", current_time)
        user_prompt = user_prompt.replace("{news_count}", str(hotlist_total))
        user_prompt = user_prompt.replace("{rss_count}", str(rss_total))
        user_prompt = user_prompt.replace("{platforms}", ", ".join(platforms) if platforms else "多平台")
        user_prompt = user_prompt.replace("{keywords}", ", ".join(keywords[:20]) if keywords else "无")
        user_prompt = user_prompt.replace("{news_content}", news_content)
        user_prompt = user_prompt.replace("{rss_content}", rss_content)
        user_prompt = user_prompt.replace("{language}", self.language)

        standalone_content = ""
        if self.include_standalone and standalone_data:
            standalone_content = self._prepare_standalone_content(standalone_data)
        user_prompt = user_prompt.replace("{standalone_content}", standalone_content)

        messages = self._build_messages(user_prompt)
        prompt_chars = sum(len(str(message.get("content", ""))) for message in messages)
        estimated_prompt_tokens = self.client.estimate_tokens(messages) or 0

        print(
            "[AI] 输入: "
            f"hotlist_used={content_meta['hotlist_used']} "
            f"rss_used={content_meta['rss_used']} "
            f"rss_summary={content_meta['rss_summary_count']} "
            f"rss_snippet={content_meta['rss_enriched_count']} "
            f"prompt_chars={prompt_chars}"
            + (
                f" est_prompt_tokens={estimated_prompt_tokens}"
                if estimated_prompt_tokens
                else ""
            )
        )

        if self.debug:
            print("\n" + "=" * 80)
            print("[AI Debug] Full prompt sent to model")
            print("=" * 80)
            if self.system_prompt:
                print("\n--- System Prompt ---")
                print(self.system_prompt)
            print("\n--- User Prompt ---")
            print(user_prompt)
            print("=" * 80 + "\n")

        try:
            response = self.client.chat(messages)
            result = self._parse_response(response)

            if result.error and "JSON 解析错误" in result.error:
                print("[AI] JSON 解析失败，尝试修复...")
                retry_result = self._retry_fix_json(response, result.error)
                if retry_result and retry_result.success and not retry_result.error:
                    print("[AI] JSON 修复成功")
                    retry_result.raw_response = response
                    result = retry_result
                else:
                    print("[AI] JSON 修复失败，使用原始文本兜底")

            if not self.include_rss:
                result.rss_insights = ""

            if not self.include_standalone:
                result.standalone_summaries = {}

            result.total_news = total_news
            result.hotlist_count = hotlist_total
            result.rss_count = rss_total
            result.analyzed_news = analyzed_count
            result.max_news_limit = self.max_news
            result.rss_summary_count = content_meta["rss_summary_count"]
            result.rss_enriched_count = content_meta["rss_enriched_count"]
            result.prompt_chars = prompt_chars
            result.estimated_prompt_tokens = estimated_prompt_tokens

            usage = self.client.last_usage or {}
            result.prompt_tokens = usage.get("prompt_tokens", 0)
            result.completion_tokens = usage.get("completion_tokens", 0)
            result.total_tokens = usage.get("total_tokens", 0)

            if usage:
                print(
                    "[AI] Token usage: "
                    f"prompt={result.prompt_tokens} "
                    f"completion={result.completion_tokens} "
                    f"total={result.total_tokens}"
                )
            else:
                print("[AI] Token usage: provider did not return usage")

            return result
        except Exception as exc:
            error_type = type(exc).__name__
            error_msg = str(exc)
            if len(error_msg) > 200:
                error_msg = error_msg[:200] + "..."
            return AIAnalysisResult(
                success=False,
                error=f"AI 分析失败 ({error_type}): {error_msg}",
            )

    def _prepare_news_content(
        self,
        stats: List[Dict],
        rss_stats: Optional[List[Dict]] = None,
    ) -> Tuple[str, str, Dict[str, int]]:
        news_lines: List[str] = []
        rss_lines: List[str] = []
        news_count = 0
        rss_count = 0
        rss_summary_count = 0
        rss_enriched_count = 0

        hotlist_total = sum(len(item.get("titles", [])) for item in stats) if stats else 0
        rss_total = sum(len(item.get("titles", [])) for item in rss_stats) if rss_stats else 0
        enrichment_remaining = self.rss_enrichment_config.get("MAX_ITEMS", 8)

        if stats:
            for stat in stats:
                word = stat.get("word", "")
                titles = stat.get("titles", [])
                if word and titles:
                    news_lines.append(f"\n**{word}** ({len(titles)}条)")
                    for item in titles:
                        if news_count >= self.max_news:
                            break
                        if not isinstance(item, dict):
                            continue

                        title = item.get("title", "")
                        if not title:
                            continue

                        source = item.get("source_name", item.get("source", ""))
                        line = f"- [{source}] {title}" if source else f"- {title}"

                        ranks = item.get("ranks", [])
                        if ranks:
                            min_rank = min(ranks)
                            max_rank = max(ranks)
                            rank_str = f"{min_rank}" if min_rank == max_rank else f"{min_rank}-{max_rank}"
                        else:
                            rank_str = "-"

                        first_time = item.get("first_time", "")
                        last_time = item.get("last_time", "")
                        time_str = self._format_time_range(first_time, last_time)
                        appear_count = item.get("count", 1)
                        line += f" | 排名:{rank_str} | 时间:{time_str} | 出现:{appear_count}次"

                        if self.include_rank_timeline:
                            timeline_str = self._format_rank_timeline(item.get("rank_timeline", []))
                            line += f" | 轨迹:{timeline_str}"

                        news_lines.append(line)
                        news_count += 1
                if news_count >= self.max_news:
                    break

        if self.include_rss and rss_stats:
            remaining = max(self.max_news - news_count, 0)
            for stat in rss_stats:
                if rss_count >= remaining:
                    break

                word = stat.get("word", "")
                titles = stat.get("titles", [])
                if word and titles:
                    rss_lines.append(f"\n**{word}** ({len(titles)}条)")
                    for item in titles:
                        if rss_count >= remaining:
                            break
                        if not isinstance(item, dict):
                            continue

                        title = item.get("title", "")
                        if not title:
                            continue

                        source = item.get("source_name", item.get("feed_name", ""))
                        source_type = self._classify_rss_source(item)
                        category = self._format_rss_category(source_type)
                        line = f"- [{category}][{source}] {title}" if source else f"- [{category}] {title}"

                        time_display = item.get("time_display", "")
                        if time_display:
                            line += f" | {time_display}"
                        rss_lines.append(line)

                        summary = ""
                        if self.include_rss_summary:
                            summary = self._truncate_text(
                                item.get("summary", ""),
                                self.rss_summary_max_chars,
                            )
                        if summary:
                            rss_lines.append(f"  摘要: {summary}")
                            rss_summary_count += 1

                        if enrichment_remaining > 0:
                            snippet = self._get_rss_snippet(item, summary)
                            if snippet:
                                rss_lines.append(f"  正文片段: {snippet}")
                                rss_enriched_count += 1
                                enrichment_remaining -= 1

                        rss_count += 1

        return (
            "\n".join(news_lines) if news_lines else "",
            "\n".join(rss_lines) if rss_lines else "",
            {
                "hotlist_total": hotlist_total,
                "rss_total": rss_total,
                "analyzed_count": news_count + rss_count,
                "hotlist_used": news_count,
                "rss_used": rss_count,
                "rss_summary_count": rss_summary_count,
                "rss_enriched_count": rss_enriched_count,
            },
        )

    def _build_messages(self, user_prompt: str) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        return messages

    def _call_ai(self, user_prompt: str) -> str:
        return self.client.chat(self._build_messages(user_prompt))

    def _build_rss_source_policies(
        self, configured_sources: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        policies: Dict[str, Dict[str, Any]] = {}
        default_chars = self.rss_enrichment_config.get("DEFAULT_SNIPPET_MAX_CHARS", 420)
        default_timeout = self.rss_enrichment_config.get("TIMEOUT", 12)

        for source in configured_sources:
            source_id = source.get("id", "")
            if not source_id:
                continue
            policies[source_id] = {
                "enabled": source.get("enabled", True),
                "type": source.get("type", "general"),
                "snippet_max_chars": int(source.get("snippet_max_chars", default_chars) or default_chars),
                "timeout": int(source.get("timeout", default_timeout) or default_timeout),
            }
        return policies

    def _classify_rss_source(self, item: Dict[str, Any]) -> str:
        return self.rss_enricher.classify_source(item) or "general"

    def _format_rss_category(self, source_type: str) -> str:
        mapping = {
            "macro": "宏观",
            "regulatory": "监管",
            "company": "公司",
            "general": "资讯",
        }
        return mapping.get(source_type, "资讯")

    def _truncate_text(self, text: str, max_chars: int) -> str:
        text = (text or "").strip()
        if not text or max_chars <= 0 or len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip() + "..."

    def _get_rss_snippet(self, item: Dict[str, Any], summary: str) -> str:
        feed_id = item.get("feed_id", "")
        policy = self.rss_source_policies.get(feed_id, {})
        if not policy or not policy.get("enabled", False):
            return ""

        snippet = self.rss_enricher.enrich(item).get("snippet", "")
        snippet = self._truncate_text(
            snippet,
            policy.get(
                "snippet_max_chars",
                self.rss_enrichment_config.get("DEFAULT_SNIPPET_MAX_CHARS", 420),
            ),
        )
        if not snippet:
            return ""
        if summary and (snippet == summary or snippet.startswith(summary)):
            return ""
        return snippet

    def _retry_fix_json(
        self, original_response: str, error_msg: str
    ) -> Optional[AIAnalysisResult]:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个 JSON 修复助手。用户会提供格式有误的 JSON 和错误信息，"
                    "你需要修复 JSON 格式错误并返回正确 JSON。"
                    "只返回纯 JSON，不要包含 Markdown 代码块或额外解释。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"以下 JSON 解析失败。\n\n"
                    f"错误：{error_msg}\n\n"
                    f"原始内容：\n{original_response}\n\n"
                    "请只修复 JSON 格式，不改变原意。"
                ),
            },
        ]

        try:
            response = self.client.chat(messages)
            return self._parse_response(response)
        except Exception as exc:
            print(f"[AI] JSON 修复失败: {type(exc).__name__}: {exc}")
            return None

    def _format_time_range(self, first_time: str, last_time: str) -> str:
        def extract_time(time_str: str) -> str:
            if not time_str:
                return "-"
            if " " in time_str:
                parts = time_str.split(" ")
                if len(parts) >= 2 and ":" in parts[1]:
                    return parts[1][:5]
            if ":" in time_str:
                return time_str[:5]
            result = time_str[:5] if len(time_str) >= 5 else time_str
            if len(result) == 5 and result[2] == "-":
                result = result.replace("-", ":")
            return result

        first = extract_time(first_time)
        last = extract_time(last_time)
        if first == last or last == "-":
            return first
        return f"{first}~{last}"

    def _format_rank_timeline(self, rank_timeline: List[Dict]) -> str:
        if not rank_timeline:
            return "-"

        parts = []
        for item in rank_timeline:
            time_str = item.get("time", "")
            if len(time_str) == 5 and time_str[2] == "-":
                time_str = time_str.replace("-", ":")
            rank = item.get("rank")
            parts.append(f"{0 if rank is None else rank}({time_str})")
        return "->".join(parts)

    def _prepare_standalone_content(self, standalone_data: Dict) -> str:
        lines = []

        for platform in standalone_data.get("platforms", []):
            platform_name = platform.get("name", platform.get("id", ""))
            items = platform.get("items", [])
            if not items:
                continue

            lines.append(f"### [{platform_name}]")
            for item in items:
                title = item.get("title", "")
                if not title:
                    continue

                line = f"- {title}"
                ranks = item.get("ranks", [])
                if ranks:
                    min_rank = min(ranks)
                    max_rank = max(ranks)
                    rank_str = f"{min_rank}" if min_rank == max_rank else f"{min_rank}-{max_rank}"
                    line += f" | 排名:{rank_str}"

                first_time = item.get("first_time", "")
                last_time = item.get("last_time", "")
                if first_time:
                    line += f" | 时间:{self._format_time_range(first_time, last_time)}"

                count = item.get("count", 1)
                if count > 1:
                    line += f" | 出现:{count}次"

                if self.include_rank_timeline:
                    timeline_str = self._format_rank_timeline(item.get("rank_timeline", []))
                    if timeline_str != "-":
                        line += f" | 轨迹:{timeline_str}"

                lines.append(line)
            lines.append("")

        for feed in standalone_data.get("rss_feeds", []):
            feed_name = feed.get("name", feed.get("id", ""))
            items = feed.get("items", [])
            if not items:
                continue

            lines.append(f"### [{feed_name}]")
            for item in items:
                title = item.get("title", "")
                if not title:
                    continue
                line = f"- {title}"
                published_at = item.get("published_at", "")
                if published_at:
                    line += f" | {published_at}"
                lines.append(line)
            lines.append("")

        return "\n".join(lines)

    def _parse_response(self, response: str) -> AIAnalysisResult:
        result = AIAnalysisResult(raw_response=response)

        if not response or not response.strip():
            result.error = "AI 返回空响应"
            return result

        json_str = response
        if "```json" in response:
            parts = response.split("```json", 1)
            code_block = parts[1] if len(parts) > 1 else ""
            end_idx = code_block.find("```")
            json_str = code_block[:end_idx] if end_idx != -1 else code_block
        elif "```" in response:
            parts = response.split("```", 2)
            if len(parts) >= 2:
                json_str = parts[1]

        json_str = json_str.strip()
        if not json_str:
            result.error = "提取的 JSON 为空"
            result.core_trends = response[:500] + "..." if len(response) > 500 else response
            result.success = True
            return result

        data = None
        parse_error = None

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            parse_error = exc

        if data is None:
            try:
                from json_repair import repair_json

                repaired = repair_json(json_str, return_objects=True)
                if isinstance(repaired, dict):
                    data = repaired
                    print("[AI] JSON 本地修复成功")
            except Exception:
                pass

        if data is None:
            if parse_error:
                error_context = json_str[
                    max(0, parse_error.pos - 30): parse_error.pos + 30
                ] if json_str and parse_error.pos else ""
                result.error = f"JSON 解析错误 (位置 {parse_error.pos}): {parse_error.msg}"
                if error_context:
                    result.error += f"，上下文: ...{error_context}..."
            else:
                result.error = "JSON 解析失败"
            result.core_trends = json_str[:500] + "..." if len(json_str) > 500 else json_str
            result.success = True
            return result

        try:
            result.core_trends = data.get("core_trends", "")
            result.sentiment_controversy = data.get("sentiment_controversy", "")
            result.signals = data.get("signals", "")
            result.rss_insights = data.get("rss_insights", "")
            result.outlook_strategy = data.get("outlook_strategy", "")

            summaries = data.get("standalone_summaries", {})
            if isinstance(summaries, dict):
                result.standalone_summaries = {
                    str(key): str(value) for key, value in summaries.items()
                }

            result.success = True
        except (KeyError, TypeError, AttributeError) as exc:
            result.error = f"字段提取错误: {type(exc).__name__}: {exc}"
            result.core_trends = json_str[:500] + "..." if len(json_str) > 500 else json_str
            result.success = True

        return result
