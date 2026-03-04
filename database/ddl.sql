-- ================================================================
-- 安全情报分析智能体 — 数据库 DDL
-- 版本：v1.0
-- 作者：alex (unix_sec@163.com)
-- 日期：2026-03-04
-- 数据库名：intel_system
-- 字符集：utf8mb4
-- ================================================================

CREATE DATABASE IF NOT EXISTS intel_system
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE intel_system;

-- ----------------------------------------------------------------
-- 1. 情报源配置表
-- ----------------------------------------------------------------
CREATE TABLE intel_sources (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  source_type     ENUM('rss','wechat','website','search_keyword') NOT NULL
                    COMMENT '情报源类型',
  name            VARCHAR(200) NOT NULL COMMENT '情报源名称',
  url             VARCHAR(2000) DEFAULT NULL COMMENT '链接地址',
  category        VARCHAR(50) NOT NULL DEFAULT 'general_security'
                    COMMENT '分类标签',
  language        ENUM('zh','en','other') NOT NULL DEFAULT 'zh',
  priority        ENUM('high','medium','low') NOT NULL DEFAULT 'medium',
  status          ENUM('active','paused','error') NOT NULL DEFAULT 'active',
  health_score    TINYINT UNSIGNED NOT NULL DEFAULT 100
                    COMMENT '健康分数 0-100',
  last_success_at DATETIME DEFAULT NULL COMMENT '最近成功采集时间',
  fail_count      SMALLINT UNSIGNED NOT NULL DEFAULT 0
                    COMMENT '连续失败次数',
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,
  created_by      VARCHAR(100) DEFAULT NULL,
  notes           TEXT DEFAULT NULL,
  INDEX idx_type_status (source_type, status),
  INDEX idx_category (category),
  INDEX idx_health (health_score)
) ENGINE=InnoDB COMMENT='情报源配置表';

-- ----------------------------------------------------------------
-- 2. 搜索关键词表
-- ----------------------------------------------------------------
CREATE TABLE search_keywords (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  keyword         VARCHAR(200) NOT NULL COMMENT '关键词',
  category        ENUM('general_security','enterprise_it','automotive',
                       'compliance','supply_chain') NOT NULL
                    COMMENT '分类',
  language        ENUM('zh','en') NOT NULL DEFAULT 'zh',
  status          ENUM('active','paused') NOT NULL DEFAULT 'active',
  daily_quota     SMALLINT UNSIGNED NOT NULL DEFAULT 10
                    COMMENT '每日搜索配额',
  last_used_at    DATETIME DEFAULT NULL,
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_category_status (category, status)
) ENGINE=InnoDB COMMENT='搜索关键词表';

-- ----------------------------------------------------------------
-- 3. 原始情报表
-- ----------------------------------------------------------------
CREATE TABLE raw_intel (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  source_id       BIGINT DEFAULT NULL COMMENT '关联 intel_sources.id',
  source_name     VARCHAR(200) NOT NULL COMMENT '来源名称',
  source_url      VARCHAR(2000) DEFAULT NULL COMMENT '原始链接',
  title           VARCHAR(500) NOT NULL COMMENT '情报标题',
  content         MEDIUMTEXT DEFAULT NULL COMMENT '原始内容',
  summary         TEXT DEFAULT NULL COMMENT '原始摘要',
  language        ENUM('zh','en','other') NOT NULL DEFAULT 'zh',
  collected_at    DATETIME NOT NULL COMMENT '采集时间',
  published_at    DATETIME DEFAULT NULL COMMENT '原始发布时间',
  content_hash    VARCHAR(64) NOT NULL COMMENT '内容哈希(SHA256)去重',
  status          ENUM('pending','processing','analyzed','duplicate',
                       'error') NOT NULL DEFAULT 'pending',
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE INDEX uk_content_hash (content_hash),
  INDEX idx_status (status),
  INDEX idx_collected (collected_at),
  INDEX idx_source (source_id)
) ENGINE=InnoDB COMMENT='原始情报表';

-- ----------------------------------------------------------------
-- 4. 已评分情报表（AI 分析结果）
-- ----------------------------------------------------------------
CREATE TABLE scored_intel (
  id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
  raw_intel_id        BIGINT NOT NULL COMMENT '关联 raw_intel.id',
  title               VARCHAR(500) NOT NULL,
  intel_type          ENUM('vulnerability','attack','regulation','data_breach',
                           'opinion','trend','technology','industry')
                        NOT NULL COMMENT '情报类型',
  severity            ENUM('high','medium','low') NOT NULL,
  summary_zh          TEXT NOT NULL COMMENT '中文摘要',
  -- 五维评分
  score_threat        TINYINT UNSIGNED NOT NULL COMMENT '威胁可能性 0-100',
  score_business      TINYINT UNSIGNED NOT NULL COMMENT '业务影响度 0-100',
  score_compliance    TINYINT UNSIGNED NOT NULL COMMENT '合规影响度 0-100',
  score_urgency       TINYINT UNSIGNED NOT NULL COMMENT '时效紧迫性 0-100',
  score_quality       TINYINT UNSIGNED NOT NULL COMMENT '情报质量 0-100',
  total_score         DECIMAL(5,2) NOT NULL COMMENT '综合价值分',
  p_level             ENUM('P0','P1','P2') NOT NULL DEFAULT 'P2',
  asset_domain        VARCHAR(100) DEFAULT NULL COMMENT '关联资产域',
  affected_markets    JSON DEFAULT NULL COMMENT '影响市场',
  -- 技术细节
  cve_id              VARCHAR(50) DEFAULT NULL,
  cvss_score          DECIMAL(3,1) DEFAULT NULL,
  poc_status          ENUM('none','public','in_wild') DEFAULT NULL,
  attack_vector       VARCHAR(100) DEFAULT NULL,
  affected_components TEXT DEFAULT NULL,
  -- AI 生成内容
  impact_analysis     TEXT DEFAULT NULL COMMENT 'LLM 影响分析',
  recommendations     JSON DEFAULT NULL COMMENT 'LLM 建议措施',
  ai_commentary       TEXT DEFAULT NULL COMMENT 'LLM 专业点评',
  -- 事件追踪
  event_track_id      BIGINT DEFAULT NULL COMMENT '关联事件主线 ID',
  -- 状态
  is_pushed           BOOLEAN NOT NULL DEFAULT FALSE,
  push_report_type    VARCHAR(20) DEFAULT NULL COMMENT '首次推送的报告类型',
  scored_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  scoring_model_ver   VARCHAR(20) NOT NULL DEFAULT '1.0',
  INDEX idx_total_score (total_score DESC),
  INDEX idx_p_level (p_level),
  INDEX idx_scored_at (scored_at),
  INDEX idx_intel_type (intel_type),
  INDEX idx_event_track (event_track_id),
  FOREIGN KEY (raw_intel_id) REFERENCES raw_intel(id)
) ENGINE=InnoDB COMMENT='已评分情报表';

-- ----------------------------------------------------------------
-- 5. 事件追踪主线表
-- ----------------------------------------------------------------
CREATE TABLE event_tracks (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  event_name      VARCHAR(300) NOT NULL COMMENT '事件名称',
  event_summary   TEXT DEFAULT NULL COMMENT '事件主线摘要',
  start_date      DATE NOT NULL COMMENT '事件起始日期',
  status          ENUM('evolving','cooling','concluded')
                    NOT NULL DEFAULT 'evolving',
  latest_update   TEXT DEFAULT NULL COMMENT '最新进展',
  updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_status (status)
) ENGINE=InnoDB COMMENT='事件追踪主线表';

-- ----------------------------------------------------------------
-- 6. 报告记录表
-- ----------------------------------------------------------------
CREATE TABLE reports (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  report_type     ENUM('daily','weekly','monthly','semi_annual','annual')
                    NOT NULL,
  report_code     VARCHAR(50) NOT NULL COMMENT '报告编号',
  report_version  ENUM('executive','security_ops') NOT NULL
                    COMMENT '高管版/运营版',
  period_start    DATETIME NOT NULL COMMENT '覆盖起始时间',
  period_end      DATETIME NOT NULL COMMENT '覆盖结束时间',
  content         LONGTEXT DEFAULT NULL COMMENT '报告完整内容',
  intel_ids       JSON DEFAULT NULL COMMENT '入选情报 ID 列表',
  ai_insight      TEXT DEFAULT NULL COMMENT 'LLM 洞察文本',
  status          ENUM('generating','ready','pushed','error')
                    NOT NULL DEFAULT 'generating',
  generated_at    DATETIME DEFAULT NULL,
  pushed_at       DATETIME DEFAULT NULL,
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE INDEX uk_report_code (report_code, report_version),
  INDEX idx_type_period (report_type, period_end)
) ENGINE=InnoDB COMMENT='报告记录表';

-- ----------------------------------------------------------------
-- 7. 推送日志表
-- ----------------------------------------------------------------
CREATE TABLE push_logs (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  push_type       ENUM('report','p0_alert','p1_alert') NOT NULL,
  channel         ENUM('wecom','email','sms') NOT NULL,
  report_id       BIGINT DEFAULT NULL,
  scored_intel_id BIGINT DEFAULT NULL COMMENT '紧急情报关联',
  recipients      JSON NOT NULL COMMENT '接收者列表',
  status          ENUM('sent','failed','retrying') NOT NULL,
  error_message   TEXT DEFAULT NULL,
  pushed_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_push_type (push_type, pushed_at)
) ENGINE=InnoDB COMMENT='推送日志表';

-- ----------------------------------------------------------------
-- 8. 读者反馈表
-- ----------------------------------------------------------------
CREATE TABLE feedbacks (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  scored_intel_id BIGINT DEFAULT NULL COMMENT '对单条情报的反馈',
  report_id       BIGINT DEFAULT NULL COMMENT '对整份报告的反馈',
  user_id         VARCHAR(100) NOT NULL COMMENT '反馈用户标识',
  rating          ENUM('valuable','not_valuable') NOT NULL,
  comment         TEXT DEFAULT NULL,
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_intel (scored_intel_id),
  INDEX idx_report (report_id),
  INDEX idx_created (created_at)
) ENGINE=InnoDB COMMENT='读者反馈表';

-- ----------------------------------------------------------------
-- 9. 审计日志表
-- ----------------------------------------------------------------
CREATE TABLE audit_logs (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  action          VARCHAR(50) NOT NULL
                    COMMENT 'CREATE/UPDATE/DELETE/IMPORT/EXPORT',
  target_table    VARCHAR(50) NOT NULL COMMENT '操作对象表名',
  target_id       BIGINT DEFAULT NULL COMMENT '操作对象 ID',
  old_value       JSON DEFAULT NULL,
  new_value       JSON DEFAULT NULL,
  operator        VARCHAR(100) NOT NULL,
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_target (target_table, target_id),
  INDEX idx_created (created_at)
) ENGINE=InnoDB COMMENT='审计日志表';

-- ----------------------------------------------------------------
-- 10. 系统配置表（含评分模型版本等可热更新配置）
-- ----------------------------------------------------------------
CREATE TABLE system_configs (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  config_key      VARCHAR(100) NOT NULL UNIQUE,
  config_value    JSON NOT NULL,
  description     VARCHAR(500) DEFAULT NULL,
  updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,
  updated_by      VARCHAR(100) DEFAULT NULL
) ENGINE=InnoDB COMMENT='系统配置表';
