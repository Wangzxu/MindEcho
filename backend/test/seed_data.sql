-- =======================================================
-- MindEcho 测试数据一键导入脚本 (seed_data.sql)
-- =======================================================
-- 用于在 MySQL 中直接执行，初始化导入测试学生账户、画像、会话和审计日志。
-- 密码哈希值通过 bcrypt 加盐计算，默认明文密码为：testpassword123
-- =======================================================

-- 确保使用正确的数据库（如果适用，请取消下面这行的注释并修改为您的数据库名）
-- USE mindecho;

-- -------------------------------------------------------
-- 1. 插入测试用户 (student_test_01, student_test_02, student_test_03)
-- -------------------------------------------------------
INSERT INTO users (id, username, password_hash, role, is_active, created_at) VALUES
(1001, 'student_test_01', '$2b$12$hBJzvVBIilhiGTqJ1WQdA.3lvheIGhNLyKWgZLGv0Hb0VmP2zUYka', 'student', 1, NOW()),
(1002, 'student_test_02', '$2b$12$hBJzvVBIilhiGTqJ1WQdA.3lvheIGhNLyKWgZLGv0Hb0VmP2zUYka', 'student', 1, NOW()),
(1003, 'student_test_03', '$2b$12$hBJzvVBIilhiGTqJ1WQdA.3lvheIGhNLyKWgZLGv0Hb0VmP2zUYka', 'student', 1, NOW())
ON DUPLICATE KEY UPDATE username=VALUES(username);

-- -------------------------------------------------------
-- 2. 插入学生对应的心理画像特征表
-- -------------------------------------------------------
INSERT INTO user_profiles (user_id, nickname, core_stressors, effective_coping_methods, entity_relation_map, semantic_history_recall, updated_at) VALUES
(1001, '小豚豚测试生', '["期末备考压力大", "睡眠困扰"]', '["温泉呼吸法", "正念引导"]', '{"期末考": "焦虑", "水豚委员": "信任倾听"}', '测试画像：该生由于期末备考压力大，睡眠困扰产生了一定程度的轻度心理压力。豚豚对其进行了同理倾听并提供了自我调节技巧。', NOW()),
(1002, '小黄鸭测试生', '["舍友作息摩擦", "社交适应不良"]', '["非暴力沟通", "界限设立"]', '{"期末考": "焦虑", "水豚委员": "信任倾听"}', '测试画像：该生由于舍友作息摩擦，社交适应不良产生了一定程度的轻度心理压力。豚豚对其进行了同理倾听并提供了自我调节技巧。', NOW()),
(1003, '保研备战生', '["学业保研竞争", "未来规划迷茫"]', '["正向事件记录", "认知重构"]', '{"期末考": "焦虑", "水豚委员": "信任倾听"}', '测试画像：该生由于学业保研竞争，未来规划迷茫产生了一定程度的轻度心理压力。豚豚对其进行了同理倾听并提供了自我调节技巧。', NOW())
ON DUPLICATE KEY UPDATE nickname=VALUES(nickname), core_stressors=VALUES(core_stressors), effective_coping_methods=VALUES(effective_coping_methods), entity_relation_map=VALUES(entity_relation_map), semantic_history_recall=VALUES(semantic_history_recall);

-- -------------------------------------------------------
-- 3. 创建测试聊天会话 (关联普通会话与无痕匿名树洞会话)
-- -------------------------------------------------------
INSERT INTO chat_sessions (id, user_id, title, created_at, summary, is_anonymous) VALUES
('test-session-uuid-0001', 1001, '学业考前情绪倾诉', NOW(), '这是一个关于 学业考前情绪倾诉 的系统测试对话会话。', 0),
('test-session-uuid-0002', 1002, '寝室关系适应讨论', NOW(), '这是一个关于 寝室关系适应讨论 的系统测试对话会话。', 0),
('test-session-uuid-0003', NULL, '无痕匿名情绪发泄树洞', NOW(), '这是一个关于 无痕匿名情绪发泄树洞 的系统测试对话会话。', 1)
ON DUPLICATE KEY UPDATE title=VALUES(title), summary=VALUES(summary);

-- -------------------------------------------------------
-- 4. 批量插入真实拦截警告日志 (高危与违规，支持匿名会话 user_id 为 Null)
-- -------------------------------------------------------
-- 检查以防止重复插入相同的语句
INSERT INTO security_activity_logs (user_id, session_id, trigger_content, log_type, matched_rule, created_at)
SELECT 1001, 'test-session-uuid-0001', '脑子里都是跳楼的画面，活得太累了', 'high_risk', '安全拦截词:跳楼', DATE_SUB(NOW(), INTERVAL 15 MINUTE)
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM security_activity_logs WHERE trigger_content = '脑子里都是跳楼的画面，活得太累了');

INSERT INTO security_activity_logs (user_id, session_id, trigger_content, log_type, matched_rule, created_at)
SELECT 1001, 'test-session-uuid-0001', '真的很想结束这一切，我想吞药解脱自己', 'high_risk', '安全拦截词:吞药', DATE_SUB(NOW(), INTERVAL 15 MINUTE)
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM security_activity_logs WHERE trigger_content = '真的很想结束这一切，我想吞药解脱自己');

INSERT INTO security_activity_logs (user_id, session_id, trigger_content, log_type, matched_rule, created_at)
SELECT 1002, 'test-session-uuid-0002', '那个自私鬼，我要去买把枪杀了他', 'violation', '安全拦截词:杀人', DATE_SUB(NOW(), INTERVAL 15 MINUTE)
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM security_activity_logs WHERE trigger_content = '那个自私鬼，我要去买把枪杀了他');

INSERT INTO security_activity_logs (user_id, session_id, trigger_content, log_type, matched_rule, created_at)
SELECT 1002, 'test-session-uuid-0002', '你真是一个智障的垃圾AI，滚吧', 'violation', '安全过滤词:垃圾', DATE_SUB(NOW(), INTERVAL 15 MINUTE)
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM security_activity_logs WHERE trigger_content = '你真是一个智障的垃圾AI，滚吧');

INSERT INTO security_activity_logs (user_id, session_id, trigger_content, log_type, matched_rule, created_at)
SELECT NULL, 'test-session-uuid-0003', '买好了安眠药准备今晚割腕自残', 'high_risk', '安全过滤词:割腕', DATE_SUB(NOW(), INTERVAL 15 MINUTE)
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM security_activity_logs WHERE trigger_content = '买好了安眠药准备今晚割腕自残');

INSERT INTO security_activity_logs (user_id, session_id, trigger_content, log_type, matched_rule, created_at)
SELECT NULL, 'test-session-uuid-0003', '买点化学制剂去报复制药的那帮人', 'violation', '预警语义匹配: 0.87 (制毒暴力倾向)', DATE_SUB(NOW(), INTERVAL 15 MINUTE)
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM security_activity_logs WHERE trigger_content = '买点化学制剂去报复制药的那帮人');
