-- =====================================================================
-- MindEcho (校园 AI 心理委员) - 数据库表结构初始化脚本 (MySQL)
-- =====================================================================

CREATE DATABASE IF NOT EXISTS `mindecho` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `mindecho`;

-- 1. 用户账号鉴权表 (仅存储认证与权限状态)
CREATE TABLE IF NOT EXISTS `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增唯一ID',
    `username` VARCHAR(80) NOT NULL UNIQUE COMMENT '登录账号(学号/工号)',
    `password_hash` VARCHAR(255) NOT NULL COMMENT 'Bcrypt加密密码密文',
    `role` VARCHAR(20) NOT NULL DEFAULT 'student' COMMENT '角色权限: admin(管理员), student(学生/普通用户)',
    `is_active` BOOLEAN NOT NULL DEFAULT TRUE COMMENT '账户是否激活可用',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '账户创建时间',
    INDEX `idx_users_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户登录凭证与权限表';

-- 2. 心理画像与长期记忆表 (存储与敏感咨询关联的数据，与账号1对1物理隔离)
CREATE TABLE IF NOT EXISTS `user_profiles` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增唯一ID',
    `user_id` INT NOT NULL UNIQUE COMMENT '外键关联users表id',
    `nickname` VARCHAR(80) DEFAULT NULL COMMENT '自拟匿名昵称',
    `core_stressors` JSON DEFAULT NULL COMMENT '核心压力源(JSON 数组，如 ["学业压力", "拖延"])',
    `effective_coping_methods` JSON DEFAULT NULL COMMENT '历史验证有效的调节技巧(JSON 数组)',
    `entity_relation_map` JSON DEFAULT NULL COMMENT '重要社会人际关系网络(JSON 键值对)',
    `semantic_history_recall` TEXT DEFAULT NULL COMMENT '历次对话提炼后的增量历史线索',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
    CONSTRAINT `fk_profiles_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户心理特征画像与长期记忆表';

-- 3. 聊天会话主表 (匿名树洞不关联user_id，支持阅后即焚)
CREATE TABLE IF NOT EXISTS `chat_sessions` (
    `id` VARCHAR(36) NOT NULL PRIMARY KEY COMMENT 'UUID唯一标识',
    `user_id` INT DEFAULT NULL COMMENT '外键关联users表id，匿名树洞时为空',
    `title` VARCHAR(255) NOT NULL DEFAULT '新对话' COMMENT '会话名称',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '会话创建时间',
    `summary` TEXT DEFAULT NULL COMMENT '对话完结后大模型提炼的单次摘要',
    `is_anonymous` BOOLEAN NOT NULL DEFAULT FALSE COMMENT '是否为匿名树洞会话(阅后即焚标识)',
    CONSTRAINT `fk_sessions_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会话主表';

-- 4. 聊天消息流水表 (保存历史会话与系统意图识别标签)
CREATE TABLE IF NOT EXISTS `chat_messages` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增唯一ID',
    `session_id` VARCHAR(36) NOT NULL COMMENT '外键关联会话ID',
    `sender` VARCHAR(10) NOT NULL COMMENT '发送方: user(学生), ai(心理委员)',
    `content` TEXT NOT NULL COMMENT '消息文本正文',
    `intent` VARCHAR(50) DEFAULT NULL COMMENT '当期意图分类: CRISIS, KNOWLEDGE, EMOTION, CHITCHAT',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '发送时间',
    CONSTRAINT `fk_messages_session_id` FOREIGN KEY (`session_id`) REFERENCES `chat_sessions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会话消息明细流水表';

-- 5. 知识文档导入任务表 (云原生 RAG 文档存储凭证)
CREATE TABLE IF NOT EXISTS `knowledge_imports` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增唯一ID',
    `file_name` VARCHAR(255) NOT NULL COMMENT '上传的原始文件名',
    `file_hash` VARCHAR(64) NOT NULL UNIQUE COMMENT '文件的SHA-256哈希值',
    `minio_bucket` VARCHAR(64) NOT NULL COMMENT 'MinIO Bucket名称',
    `minio_object_name` VARCHAR(255) NOT NULL COMMENT 'MinIO 物理存放Object对象路径',
    `file_size` INT NOT NULL COMMENT '文件字节大小',
    `status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '处理状态: pending, processing, success, failed',
    `chunk_count` INT DEFAULT 0 COMMENT '被切分出的文本块总量',
    `error_message` TEXT DEFAULT NULL COMMENT '向量化失败时的错误日志',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX `idx_imports_file_name` (`file_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识文档导入任务与云存储记录表';

-- 6. 安全敏感词过滤配置表 (后端支持自动导出同步为 safety_rules.yaml)
CREATE TABLE IF NOT EXISTS `safety_keywords` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增唯一ID',
    `word` VARCHAR(100) NOT NULL UNIQUE COMMENT '拦截词条正文',
    `word_type` VARCHAR(20) NOT NULL COMMENT '词库分类: high_risk(高危自残), violation(谩骂违规)',
    `is_enabled` BOOLEAN NOT NULL DEFAULT TRUE COMMENT '是否启用拦截',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '添加时间',
    INDEX `idx_keywords_word` (`word`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='安全敏感词库过滤配置表';

-- 7. 安全事件与预警日志表 (活动日志数据源)
CREATE TABLE IF NOT EXISTS `security_activity_logs` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增唯一ID',
    `user_id` INT DEFAULT NULL COMMENT '关联的用户ID，匿名聊天时为空',
    `session_id` VARCHAR(36) NOT NULL COMMENT '关联的会话ID',
    `trigger_content` TEXT NOT NULL COMMENT '触发红线拦截的用户原始敏感语句',
    `log_type` VARCHAR(20) NOT NULL COMMENT '拦截严重级别: high_risk(高危), violation(违规)',
    `matched_rule` VARCHAR(255) NOT NULL COMMENT '触发规则描述(如 命中间接词:烧炭 或 语义相似度:0.87)',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '触发时间',
    CONSTRAINT `fk_logs_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_logs_session_id` FOREIGN KEY (`session_id`) REFERENCES `chat_sessions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='安全事件拦截与预警活动日志表';
