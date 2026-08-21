# -*- coding: utf-8 -*-
import os
import sys

# 将 backend 路径加入系统搜索路径
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(base_dir)

from app.database.mysql import SessionLocal
from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.session import ChatSession
from app.models.security_activity_log import SecurityActivityLog
from app.services.auth_service import auth_service
from datetime import datetime, timedelta

def seed_test_data():
    db = SessionLocal()
    try:
        print("正在插入测试数据...")
        
        # 1. 批量插入多个测试学生账户与心理画像
        students_data = [
            {"username": "student_test_01", "nickname": "小豚豚测试生", "stressors": ["期末备考压力大", "睡眠困扰"], "coping": ["温泉呼吸法", "正念引导"]},
            {"username": "student_test_02", "nickname": "小黄鸭测试生", "stressors": ["舍友作息摩擦", "社交适应不良"], "coping": ["非暴力沟通", "界限设立"]},
            {"username": "student_test_03", "nickname": "保研备战生", "stressors": ["学业保研竞争", "未来规划迷茫"], "coping": ["正向事件记录", "认知重构"]}
        ]
        
        users = []
        for s in students_data:
            existing = db.query(User).filter(User.username == s["username"]).first()
            if existing:
                print(f"用户 {s['username']} 已存在，跳过插入。")
                users.append(existing)
                continue
                
            hashed_pwd = auth_service.hash_password("testpassword123")
            user = User(
                username=s["username"],
                password_hash=hashed_pwd,
                role="student",
                is_active=True
            )
            db.add(user)
            db.flush() # 获取 user.id
            
            profile = UserProfile(
                user_id=user.id,
                nickname=s["nickname"],
                core_stressors=s["stressors"],
                effective_coping_methods=s["coping"],
                entity_relation_map={"期末考": "焦虑", "水豚委员": "信任倾听"},
            )
            db.add(profile)
            users.append(user)
            print(f"成功录入用户: {s['username']}，昵称: {s['nickname']}")
            
        db.commit()
        
        # 2. 批量创建聊天会话 (固定双会话：直接聊天 / 无痕树洞)
        sessions = []
        session_configs = [
            {"user_id": users[0].id, "title": "直接聊天", "is_anonymous": False},
            {"user_id": users[1].id, "title": "直接聊天", "is_anonymous": False},
            {"user_id": None, "title": "无痕树洞", "is_anonymous": True}
        ]
        
        for idx, sc in enumerate(session_configs):
            session = ChatSession(
                user_id=sc["user_id"],
                title=sc["title"],
                is_anonymous=sc["is_anonymous"],
                summary=f"这是一个关于 {sc['title']} 的系统测试对话会话。"
            )
            db.add(session)
            db.flush()
            sessions.append(session)
            print(f"成功录入会话: ID {session.id}，是否匿名: {sc['is_anonymous']}")
            
        db.commit()
        
        # 3. 批量插入警报拦截 (high_risk) 和 违规拦截 (violation) 日志记录
        log_configs = [
            # 高危拦截记录
            {
                "user_id": users[0].id,
                "session_id": sessions[0].id,
                "trigger_content": "脑子里都是跳楼的画面，活得太累了",
                "log_type": "high_risk",
                "matched_rule": "安全拦截词:跳楼"
            },
            {
                "user_id": users[0].id,
                "session_id": sessions[0].id,
                "trigger_content": "真的很想结束这一切，我想吞药解脱自己",
                "log_type": "high_risk",
                "matched_rule": "安全拦截词:吞药"
            },
            # 违规拦截记录
            {
                "user_id": users[1].id,
                "session_id": sessions[1].id,
                "trigger_content": "那个自私鬼，我要去买把枪杀了他",
                "log_type": "violation",
                "matched_rule": "安全拦截词:杀人"
            },
            {
                "user_id": users[1].id,
                "session_id": sessions[1].id,
                "trigger_content": "你真是一个智障的垃圾AI，滚吧",
                "log_type": "violation",
                "matched_rule": "安全过滤词:垃圾"
            },
            # 匿名会话安全日志记录 (user_id 置为 Null，保障隐私)
            {
                "user_id": None,
                "session_id": sessions[2].id,
                "trigger_content": "买好了安眠药准备今晚割腕自残",
                "log_type": "high_risk",
                "matched_rule": "安全过滤词:割腕"
            },
            {
                "user_id": None,
                "session_id": sessions[2].id,
                "trigger_content": "买点化学制剂去报复制药的那帮人",
                "log_type": "violation",
                "matched_rule": "预警语义匹配: 0.87 (制毒暴力倾向)"
            }
        ]
        
        for lc in log_configs:
            # 去重检测
            existing_log = db.query(SecurityActivityLog).filter(
                SecurityActivityLog.trigger_content == lc["trigger_content"]
            ).first()
            if existing_log:
                print(f"日志 '{lc['trigger_content'][:10]}...' 已存在，跳过。")
                continue
                
            log = SecurityActivityLog(
                user_id=lc["user_id"],
                session_id=lc["session_id"],
                trigger_content=lc["trigger_content"],
                log_type=lc["log_type"],
                matched_rule=lc["matched_rule"],
                created_at=datetime.utcnow() - timedelta(minutes=15)
            )
            db.add(log)
            print(f"成功录入安全日志: 类型 {lc['log_type']}，命中 '{lc['matched_rule']}'")
            
        db.commit()
        print("✅ 教师管理后台测试数据插入同步完成！")
        
    except Exception as e:
        db.rollback()
        print(f"❌ 插入测试数据失败: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_test_data()
