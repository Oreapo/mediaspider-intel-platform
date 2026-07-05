from __future__ import annotations

from ..api.schemas.platform import PlatformFieldOption, PlatformFieldSchema, PlatformTaskModelResponse


class PlatformTaskModelService:
    def list_models(self) -> list[PlatformTaskModelResponse]:
        common_mode_options = [
            PlatformFieldOption(value="search", label="Search"),
            PlatformFieldOption(value="detail", label="Detail"),
            PlatformFieldOption(value="creator", label="Creator"),
        ]
        scenario_options = [
            PlatformFieldOption(value="lead_diversion", label="引流导流"),
            PlatformFieldOption(value="gray_recruitment", label="灰产招募"),
            PlatformFieldOption(value="fraud_promotion", label="欺诈推广"),
            PlatformFieldOption(value="seller_risk", label="卖家风险"),
            PlatformFieldOption(value="product_risk", label="商品风险"),
            PlatformFieldOption(value="topic_watch", label="主题监测"),
        ]
        social_fields = [
            PlatformFieldSchema(key="task_name", label="任务名称", group="base", control="text", required=True),
            PlatformFieldSchema(key="notes", label="任务备注", group="base", control="textarea"),
            PlatformFieldSchema(
                key="scenario_type",
                label="风险场景",
                group="base",
                control="select",
                required=True,
                default="lead_diversion",
                options=scenario_options,
            ),
            PlatformFieldSchema(
                key="task_mode",
                label="任务模式",
                group="base",
                control="select",
                required=True,
                default="search",
                options=common_mode_options,
            ),
            PlatformFieldSchema(
                key="keywords",
                label="关键词",
                group="input",
                control="textarea",
                required=True,
                visible_for_modes=["search"],
            ),
            PlatformFieldSchema(
                key="specified_ids",
                label="详情 ID / URL",
                group="input",
                control="textarea",
                required=True,
                visible_for_modes=["detail"],
            ),
            PlatformFieldSchema(
                key="creator_ids",
                label="创作者 ID / URL",
                group="input",
                control="textarea",
                required=True,
                visible_for_modes=["creator"],
            ),
            PlatformFieldSchema(key="start_page", label="起始页", group="runtime", control="number", default=1),
            PlatformFieldSchema(
                key="login_type",
                label="登录方式",
                group="runtime",
                control="select",
                default="qrcode",
                options=[
                    PlatformFieldOption(value="qrcode", label="二维码"),
                    PlatformFieldOption(value="phone", label="手机号"),
                    PlatformFieldOption(value="cookie", label="Cookie"),
                ],
            ),
            PlatformFieldSchema(
                key="save_option",
                label="保存格式",
                group="runtime",
                control="select",
                default="jsonl",
                options=[
                    PlatformFieldOption(value="jsonl", label="JSONL"),
                    PlatformFieldOption(value="json", label="JSON"),
                    PlatformFieldOption(value="csv", label="CSV"),
                ],
            ),
            PlatformFieldSchema(key="enable_comments", label="抓取评论", group="runtime", control="switch", default=True),
            PlatformFieldSchema(key="enable_sub_comments", label="抓取二级评论", group="runtime", control="switch", default=False),
            PlatformFieldSchema(key="headless", label="无头模式", group="runtime", control="switch", default=False),
            PlatformFieldSchema(key="max_comments_count_singlenotes", label="单条最大评论数", group="runtime", control="number", default=10),
            PlatformFieldSchema(key="max_concurrency_num", label="最大并发数", group="runtime", control="number", default=1),
            PlatformFieldSchema(
                key="signal_extractors",
                label="信号提取器",
                group="analysis",
                control="tags",
                help_text="选择采集完成后要运行的风险信号规则。",
            ),
            PlatformFieldSchema(
                key="analysis_types",
                label="分析类型",
                group="analysis",
                control="tags",
                help_text="选择采集完成后要触发的分析器。",
            ),
        ]
        base_social_extractors = [
            "risk_terms",
            "recruit_pattern",
            "service_offer",
            "traffic_route",
            "contact_points",
            "template_similarity",
            "abnormal_activity",
        ]
        platform_extra_extractors = {
            "xhs": ["xhs_comment_lead_diversion"],
            "dy": ["dy_script_diversion"],
            "wb": ["wb_topic_propagation"],
        }
        social_models = []
        for platform, label, summary, entity_types in [
            ("xhs", "小红书", "图文 / 视频 / 创作者内容采集", ["content", "comment", "creator"]),
            ("dy", "抖音", "短视频与创作者采集", ["content", "comment", "creator"]),
            ("ks", "快手", "短视频与互动数据采集", ["content", "comment", "creator"]),
            ("bili", "哔哩哔哩", "视频内容与创作者采集", ["content", "comment", "creator"]),
            ("wb", "微博", "话题与舆情内容采集", ["content", "comment", "creator"]),
            ("tieba", "百度贴吧", "帖子与吧内互动采集", ["content", "comment", "creator"]),
            ("zhihu", "知乎", "问答 / 文章 / 创作者采集", ["content", "comment", "creator"]),
        ]:
            social_models.append(
                PlatformTaskModelResponse(
                    platform=platform,
                    label=label,
                    summary=summary,
                    supported_entity_types=entity_types,
                    supported_modes=["search", "detail", "creator"],
                    supported_signal_extractors=base_social_extractors + platform_extra_extractors.get(platform, []),
                    supported_analysis_types=[
                        "signal_summary",
                        "entity_candidates",
                        "timeline",
                    ],
                    task_fields=social_fields,
                )
            )
        xianyu_fields = social_fields + [
            PlatformFieldSchema(key="min_price", label="最低价格", group="filters", control="number", visible_for_modes=["search"]),
            PlatformFieldSchema(key="max_price", label="最高价格", group="filters", control="number", visible_for_modes=["search"]),
            PlatformFieldSchema(key="region", label="地区", group="filters", control="text", visible_for_modes=["search"]),
            PlatformFieldSchema(key="free_shipping", label="仅看包邮", group="filters", control="switch", default=True, visible_for_modes=["search"]),
            PlatformFieldSchema(key="personal_only", label="仅看个人闲置", group="filters", control="switch", default=True, visible_for_modes=["search"]),
        ]
        social_models.append(
            PlatformTaskModelResponse(
                platform="xianyu",
                label="闲鱼",
                summary="商品、卖家、价格带和上新行为采集",
                supported_entity_types=["product", "seller", "price_snapshot"],
                supported_modes=["search", "detail"],
                supported_signal_extractors=[
                    "risk_terms",
                    "seller_template_reuse",
                    "abnormal_price_band",
                    "contact_points",
                ],
                supported_analysis_types=[
                    "seller_risk_profile",
                    "product_risk_band",
                    "listing_similarity",
                ],
                task_fields=xianyu_fields,
            )
        )
        return social_models


platform_task_model_service = PlatformTaskModelService()
