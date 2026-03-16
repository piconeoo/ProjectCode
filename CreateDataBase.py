# database.py - 数据库创建和管理
import sqlite3
import json
from pathlib import Path
import threading
from contextlib import contextmanager
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 使用线程锁确保数据库连接安全
_db_lock = threading.Lock()


# 创建数据库连接的上下文管理器
@contextmanager
def get_db_connection():
    """获取数据库连接的上下文管理器，确保线程安全"""
    with _db_lock:
        conn = sqlite3.connect("vocabulary.db", check_same_thread=False)
        conn.row_factory = sqlite3.Row  # 支持字典式访问
        try:
            yield conn
        finally:
            conn.close()


# 初始化数据库
def init_database():
    """初始化SQLite数据库"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 创建单词表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL UNIQUE,
            phonetic TEXT,
            meaning TEXT NOT NULL,
            example TEXT NOT NULL,
            example_cn TEXT,
            part_of_speech TEXT,
            difficulty INTEGER DEFAULT 1,
            mastered BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_reviewed TIMESTAMP,
            last_seen TIMESTAMP,
            occurrence_count INTEGER DEFAULT 1
        )
        ''')

        # 创建学习历史表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS study_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER,
            reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (word_id) REFERENCES words (id)
        )
        ''')
        conn.commit()
        logger.info("数据库初始化完成")
        return True


# 数据库统计函数
def get_database_stats():
    """获取数据库统计信息"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        stats = {}

        # 获取总单词数
        cursor.execute("SELECT COUNT(*) FROM words")
        stats['total_words'] = cursor.fetchone()[0]

        # 获取已掌握单词数
        cursor.execute("SELECT COUNT(*) FROM words WHERE mastered = 1")
        stats['mastered_words'] = cursor.fetchone()[0]

        # 获取今日学习次数
        cursor.execute("SELECT COUNT(*) FROM study_history WHERE DATE(reviewed_at) = DATE('now')")
        stats['today_study'] = cursor.fetchone()[0]

        # 获取总学习次数
        cursor.execute("SELECT COUNT(*) FROM study_history")
        stats['total_study'] = cursor.fetchone()[0]

        # 获取出现次数统计
        cursor.execute(
            "SELECT AVG(occurrence_count) as avg_occurrence, MAX(occurrence_count) as max_occurrence FROM words")
        occurrence_stats = cursor.fetchone()
        stats['avg_occurrence'] = round(occurrence_stats['avg_occurrence'], 2) if occurrence_stats['avg_occurrence'] else 0
        stats['max_occurrence'] = occurrence_stats['max_occurrence'] if occurrence_stats['max_occurrence'] else 0

        return stats


# 获取所有单词
def get_all_words():
    """获取所有单词列表"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, word FROM words ORDER BY id")
        return cursor.fetchall()


# 主函数，用于独立运行数据库初始化
if __name__ == "__main__":
    print("正在初始化数据库...")
    if init_database():
        stats = get_database_stats()
        print(f"数据库初始化成功！")
        print(f"当前单词数: {stats['total_words']}")
        print(f"已掌握单词: {stats['mastered_words']}")
    else:
        print("数据库初始化失败！")