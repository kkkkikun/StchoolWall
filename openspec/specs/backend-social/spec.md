# backend-social Specification

## Purpose
TBD - created by archiving change backend-social-layer. Update Purpose after archive.
## Requirements
### Requirement: 帖子互动计数与状态

帖子列表与详情 MUST 返回 like_count / comment_count / view_count，以及当前登录用户的 is_liked / is_favorited 视角字段。

#### Scenario: 游客浏览信息流

- **WHEN** 未登录用户请求 `/posts`
- **THEN** 返回 like_count/comment_count/view_count，is_liked/is_favorited 为 false

### Requirement: 点赞幂等与计数一致

点赞 MUST 幂等（重复请求不叠加计数），取消赞 MUST 使 like_count 递减且不低于 0。

#### Scenario: 重复点赞

- **WHEN** 同一用户对同一帖子连续两次 POST `/posts/{id}/like`
- **THEN** like_count 只 +1，likes 表只有一条记录

#### Scenario: 计数不越界

- **WHEN** 取消一个未赞的帖子
- **THEN** like_count 保持 0，不为负

### Requirement: 评论权限与删除

发评论 MUST 需已认证；用户 MUST 只能删除自己的评论。

#### Scenario: 删除他人评论

- **WHEN** 用户 A 删除用户 B 的评论
- **THEN** 返回 403，评论保留

### Requirement: 个人统计接口

`/me/stats` MUST 返回当前用户的帖子/评论/收藏/足迹四项计数。

#### Scenario: 查询统计

- **WHEN** 已认证用户请求 `/me/stats`
- **THEN** 返回 posts_count/comments_count/favorites_count/footprints_count，均为真实聚合值

### Requirement: 十大热帖

`/posts/hot` MUST 返回近期按互动热度加权的榜单，不含广告。

#### Scenario: 热帖排序

- **WHEN** 请求 `/posts/hot?limit=10`
- **THEN** 返回近 7 天帖子，按 like_count*3 + comment_count*2 + view_count 降序，post_type=advertisement 被排除

### Requirement: 帖子搜索

`/posts/search` MUST 按关键词匹配帖子正文。

#### Scenario: 关键词命中

- **WHEN** 请求 `/posts/search?q=自习室`
- **THEN** 返回 content 含"自习室"的帖子，分页

### Requirement: 通知生成与未读汇总

点赞/评论/收藏动作 MUST 为帖子作者生成一条通知（不通知自己）；`/notifications/unread-summary` MUST 返回按类型聚合的未读数。

#### Scenario: 不通知自己

- **WHEN** 用户对自己的帖子点赞
- **THEN** 不生成任何通知

#### Scenario: 未读汇总

- **WHEN** 请求 `/notifications/unread-summary`
- **THEN** 返回 {comment, like, group, im} 计数（im 恒为 0，私信未实现）

### Requirement: 组局报名与进度

组局 MUST 支持报名（joined_count+1）与退出，满额自动关闭，进度由 joined/total 计算。

#### Scenario: 满额关闭

- **WHEN** joined_count 达到 total
- **THEN** 组局 status 变为"已满"，新报名被拒

#### Scenario: 重复报名

- **WHEN** 已报名用户再次报名同一组局
- **THEN** 报名被拒（幂等），joined_count 不变

### Requirement: 私信暂不实现

系统 MUST NOT 提供站内私信 IM；消息页私信入口 MUST 显示"暂未开放"。

#### Scenario: 私信入口

- **WHEN** 用户进入消息页私信分类
- **THEN** 展示"暂未开放"提示，无 IM 接口被调用

