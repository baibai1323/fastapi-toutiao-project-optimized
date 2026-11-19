-- ============================================================
-- v2 迁移脚本：只用于“已经按旧版 database.sql 建过库”的环境。
-- 新环境直接执行 database.sql 即可，不要再执行本文件。
--
-- 执行前务必备份：
--   mysqldump -u root -p news_app > news_app_backup.sql
-- ============================================================

USE news_app;

-- 1) history 去重：保留每个 (user_id, news_id) 最新的一条。
DELETE h1
FROM history h1
INNER JOIN history h2
  ON h1.user_id = h2.user_id
 AND h1.news_id = h2.news_id
 AND h1.view_time < h2.view_time;

DELETE h1
FROM history h1
INNER JOIN history h2
  ON h1.user_id = h2.user_id
 AND h1.news_id = h2.news_id
 AND h1.view_time = h2.view_time
 AND h1.id > h2.id;

-- 2) 补 (user_id, news_id) 唯一约束，支撑 INSERT ... ON DUPLICATE KEY UPDATE。
ALTER TABLE history
  ADD UNIQUE INDEX uniq_history_user_news (user_id ASC, news_id ASC);

-- 3) 历史列表索引：用 (user_id, view_time DESC) 替代单列 user_id 索引。
ALTER TABLE history DROP INDEX fk_history_user_idx;
ALTER TABLE history
  ADD INDEX ix_history_user_view (user_id ASC, view_time DESC);

-- 4) 新闻列表/相关新闻复合索引，消除 filesort。
ALTER TABLE news DROP INDEX fk_news_category_idx;
ALTER TABLE news DROP INDEX idx_publish_time;
ALTER TABLE news
  ADD INDEX ix_news_category_publish (category_id ASC, publish_time DESC, id DESC),
  ADD INDEX ix_news_category_views (category_id ASC, views DESC, publish_time DESC);

-- 5) 收藏列表按时间倒序。
ALTER TABLE favorite DROP INDEX fk_favorite_user_idx;
ALTER TABLE favorite
  ADD INDEX ix_favorite_user_created (user_id ASC, created_at DESC);

-- 6) Token 改为只存 SHA-256（64 字符）；旧 UUID Token 会自然过期。
ALTER TABLE user_token
  MODIFY COLUMN token VARCHAR(64) NOT NULL COMMENT '令牌 SHA-256 摘要';

-- 7) 看一眼执行计划，确认走索引而不是 filesort。
EXPLAIN
SELECT id, title
FROM news
WHERE category_id = 1
ORDER BY publish_time DESC, id DESC
LIMIT 10;
