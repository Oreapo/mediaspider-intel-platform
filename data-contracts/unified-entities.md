# Unified Entities

建议将平台输出统一成以下实体：

- `content`
- `comment`
- `creator`
- `product`
- `seller`
- `price_snapshot`

## content

适用于：

- xhs
- dy
- ks
- wb
- zhihu
- bili
- tieba

关键字段：

- `source_platform`
- `content_id`
- `title`
- `body`
- `author_id`
- `author_name`
- `publish_time`
- `like_count`
- `comment_count`
- `share_count`
- `tags`
- `raw_payload`

## product

适用于：

- xianyu

关键字段：

- `source_platform`
- `product_id`
- `title`
- `price`
- `original_price`
- `seller_id`
- `seller_name`
- `region`
- `published_at`
- `want_count`
- `image_urls`
- `raw_payload`

## seller

适用于：

- xianyu

关键字段：

- `seller_id`
- `seller_name`
- `profile_summary`
- `registration_days`
- `rating_summary`
- `raw_payload`

## 分析要求

统一实体不是为了丢失平台差异，而是为了：

- 建立共通分析入口
- 支持跨平台分析
- 允许平台专属字段保留在扩展字段中
