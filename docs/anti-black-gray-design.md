# Anti-Black-Gray Design

## 设计目标

该平台的核心目标是支持对黑灰产公开活动进行：

- 线索采集
- 风险识别
- 关系关联
- 案件沉淀
- 证据导出

## 优先识别对象

### 风险内容

- 招募文案
- 导流文案
- 灰产教程内容
- 虚假宣传内容

### 风险账号

- 批量发布账号
- 矩阵账号
- 高重复内容账号
- 评论区导流账号

### 风险商品 / 卖家

- 价格异常商品
- 模板化商品
- 卖家多号复用
- 引流型商品描述

### 风险联系点

- 手机号
- 微信号
- 社群号
- 跳转口令
- 外链路径

## 优先信号类型

- `risk_term_hit`
- `contact_point_hit`
- `template_similarity_hit`
- `abnormal_activity_hit`
- `cross_platform_alias_hit`
- `seller_product_cluster_hit`

## 核心产品对象

- `Task`
  采集与刷新入口
- `Dataset`
  原始与标准化数据资产
- `Signal`
  规则或模型识别出的风险信号
- `Entity`
  账号 / 卖家 / 商品 / 联系方式等对象
- `Case`
  专题案件容器
- `EvidencePacket`
  可导出的证据集合

## 输出要求

一个完整案件至少应能导出：

- 风险摘要
- 涉及平台
- 关键实体列表
- 关键时间线
- 原始证据引用
- 分析结论
