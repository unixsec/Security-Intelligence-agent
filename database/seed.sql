-- ================================================================
-- 安全情报分析智能体 — 初始化种子数据
-- 版本：v1.0
-- 作者：alex (unix_sec@163.com)
-- 日期：2026-03-04
-- ================================================================

USE intel_system;

-- ----------------------------------------------------------------
-- 初始化系统配置
-- ----------------------------------------------------------------

-- 评分模型配置（v1.0 风险矩阵驱动模型）
INSERT INTO system_configs (config_key, config_value, description, updated_by) VALUES
('scoring_model', '{
  "version": "1.0",
  "name": "风险矩阵驱动模型",
  "dimensions": [
    {"name": "threat_likelihood", "label": "威胁可能性",   "weight": 0.25},
    {"name": "business_impact",   "label": "业务影响度",   "weight": 0.30},
    {"name": "compliance_impact", "label": "合规影响度",   "weight": 0.20},
    {"name": "time_urgency",      "label": "时效紧迫性",   "weight": 0.15},
    {"name": "source_quality",    "label": "情报质量系数", "weight": 0.10}
  ],
  "p_level_rules": {
    "P0": {"total_score_gte": 85, "threat_likelihood_gte": 80},
    "P1": {"total_score_gte": 75, "or_urgency_gte": 90},
    "P2": {"default": true}
  },
  "threshold": 60,
  "daily_max": 10,
  "periodic_max": 20
}', '情报评分模型配置（可热更新）', 'system');

-- LLM 配置
INSERT INTO system_configs (config_key, config_value, description, updated_by) VALUES
('llm_config', '{
  "provider": "deepseek",
  "api_endpoint": "http://deepseek-server.llm-serving.svc.cluster.local:8000/v1",
  "model_name": "deepseek-chat",
  "timeout": 60,
  "max_retries": 3,
  "max_concurrency": 10,
  "temperature": 0.3
}', 'LLM 模型配置（可热更新，切换模型只需修改此配置）', 'system');

-- 报告推送配置
INSERT INTO system_configs (config_key, config_value, description, updated_by) VALUES
('report_push_config', '{
  "daily": {
    "trigger_time": "06:00",
    "push_time": "08:00",
    "channels": ["wecom", "email"],
    "wecom_groups": ["security_ops", "management"],
    "email_groups": ["security_team"]
  },
  "weekly": {
    "trigger_weekday": 5,
    "trigger_time": "12:00",
    "channels": ["wecom", "email"]
  },
  "monthly": {
    "trigger_day_before_month_end": 1,
    "channels": ["wecom", "email"]
  },
  "p0_alert": {
    "channels": ["wecom", "sms"],
    "recipients": ["ciso", "security_ops_lead"]
  },
  "p1_alert": {
    "sla_hours": 4,
    "channels": ["wecom", "email"],
    "recipients": ["security_ops"]
  }
}', '报告推送渠道和接收人配置', 'system');

-- 密级控制配置
INSERT INTO system_configs (config_key, config_value, description, updated_by) VALUES
('sensitivity_config', '{
  "0day_recipients": ["ciso", "security_ops"],
  "internal_data_desensitize": true,
  "desensitize_patterns": [
    "(?i)\\b(192\\.168|10\\.\\d+|172\\.(1[6-9]|2[0-9]|3[01]))\\.[\\d.]+\\b",
    "(?i)\\b[A-Za-z0-9._%+-]+@(internal|corp)\\.company\\.com\\b"
  ]
}', '情报密级控制和脱敏规则', 'system');

-- ----------------------------------------------------------------
-- 初始化情报源（示例数据，可根据实际情况修改）
-- ----------------------------------------------------------------

INSERT INTO intel_sources
  (source_type, name, url, category, language, priority, status, created_by)
VALUES
  -- 通用安全 RSS
  ('rss', 'FreeBuf 安全资讯',
   'https://www.freebuf.com/feed',
   'general_security', 'zh', 'high', 'active', 'admin'),

  ('rss', '安全客 RSS',
   'https://api.anquanke.com/data/v1/rss',
   'general_security', 'zh', 'high', 'active', 'admin'),

  ('rss', '嘶吼 4hou.com',
   'https://www.4hou.com/feed',
   'general_security', 'zh', 'medium', 'active', 'admin'),

  ('rss', 'CISA Known Exploited Vulnerabilities',
   'https://www.cisa.gov/known-exploited-vulnerabilities.json',
   'general_security', 'en', 'high', 'active', 'admin'),

  ('rss', 'The Hacker News',
   'https://feeds.feedburner.com/TheHackersNews',
   'general_security', 'en', 'high', 'active', 'admin'),

  ('rss', 'Krebs on Security',
   'https://krebsonsecurity.com/feed/',
   'general_security', 'en', 'medium', 'active', 'admin'),

  ('rss', 'Bleeping Computer Security',
   'https://www.bleepingcomputer.com/feed/',
   'general_security', 'en', 'high', 'active', 'admin'),

  ('rss', 'NVD CVE Recent',
   'https://nvd.nist.gov/feeds/xml/cve/misc/nvd-rss-analyzed.xml',
   'general_security', 'en', 'high', 'active', 'admin'),

  -- 车联网/汽车安全
  ('rss', 'AUTO-ISAC 公告',
   'https://www.automotiveisac.com/feed/',
   'automotive', 'en', 'high', 'active', 'admin'),

  ('website', 'ISO/SAE 21434 更新',
   'https://www.iso.org/standard/70918.html',
   'automotive', 'en', 'medium', 'active', 'admin'),

  -- 合规/法规
  ('website', 'GDPR 执法动态',
   'https://edpb.europa.eu/news/news_en',
   'compliance', 'en', 'medium', 'active', 'admin'),

  ('website', '工信部网络安全公告',
   'https://www.miit.gov.cn/jgsj/waj/index.html',
   'compliance', 'zh', 'high', 'active', 'admin');

-- ----------------------------------------------------------------
-- 初始化搜索关键词
-- ----------------------------------------------------------------

INSERT INTO search_keywords (keyword, category, language, status, daily_quota) VALUES
  -- 通用安全
  ('勒索软件', 'general_security', 'zh', 'active', 10),
  ('数据泄露', 'general_security', 'zh', 'active', 10),
  ('APT攻击', 'general_security', 'zh', 'active', 10),
  ('零日漏洞', 'general_security', 'zh', 'active', 10),
  ('供应链攻击', 'supply_chain', 'zh', 'active', 8),
  ('ransomware attack', 'general_security', 'en', 'active', 10),
  ('data breach', 'general_security', 'en', 'active', 10),
  ('zero day vulnerability', 'general_security', 'en', 'active', 10),

  -- 车联网/汽车安全
  ('车联网安全', 'automotive', 'zh', 'active', 8),
  ('自动驾驶安全漏洞', 'automotive', 'zh', 'active', 8),
  ('OTA升级攻击', 'automotive', 'zh', 'active', 5),
  ('智能座舱漏洞', 'automotive', 'zh', 'active', 5),
  ('automotive cybersecurity', 'automotive', 'en', 'active', 8),
  ('vehicle OTA security', 'automotive', 'en', 'active', 5),
  ('connected car hack', 'automotive', 'en', 'active', 8),
  ('UNECE WP.29 R155', 'automotive', 'en', 'active', 3),

  -- 合规
  ('GDPR罚款', 'compliance', 'zh', 'active', 5),
  ('等保2.0', 'compliance', 'zh', 'active', 5),
  ('个人信息保护法', 'compliance', 'zh', 'active', 5),
  ('网络安全法', 'compliance', 'zh', 'active', 5),
  ('数据安全法', 'compliance', 'zh', 'active', 5),

  -- 企业IT
  ('Active Directory漏洞', 'enterprise_it', 'zh', 'active', 8),
  ('云安全漏洞', 'enterprise_it', 'zh', 'active', 8),
  ('VPN漏洞', 'enterprise_it', 'zh', 'active', 8),
  ('Microsoft漏洞补丁', 'enterprise_it', 'zh', 'active', 8);
