# word_importer.py
import json
import os
import sys
import sqlite3
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WordImporter:
    def __init__(self, db_path="vocabulary.db"):
        self.db_path = db_path
        self.conn = None

    def connect(self):
        """连接到数据库"""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            return True
        except Exception as e:
            print(f"❌ 数据库连接失败: {e}")
            return False

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()

    def import_json_file(self, json_path, update_existing=True):
        """
        导入JSON文件到数据库

        Args:
            json_path: JSON文件路径
            update_existing: 是否更新已存在的单词
        """
        print("=" * 60)
        print("单词学习系统 - 自动导入工具")
        print("=" * 60)

        # 1. 检查文件
        if not self._check_file(json_path):
            return False, "文件检查失败"

        # 2. 连接到数据库
        if not self.connect():
            return False, "数据库连接失败"

        try:
            # 3. 读取JSON文件
            data = self._read_json(json_path)
            if data is None:
                return False, "读取JSON文件失败"

            print(f"✅ 找到 {len(data)} 个单词")

            # 4. 确保数据库表存在
            self._ensure_tables()

            # 5. 导入数据
            result = self._import_data(data, update_existing)

            # 6. 显示统计
            self._show_statistics()

            return result

        except Exception as e:
            print(f"❌ 导入过程中出错: {e}")
            return False, str(e)
        finally:
            self.close()

    def _check_file(self, file_path):
        """检查文件是否存在和可读"""
        if not os.path.exists(file_path):
            print(f"❌ 文件不存在: {file_path}")
            print(f"   当前目录: {os.getcwd()}")
            return False

        if not os.path.isfile(file_path):
            print(f"❌ 不是文件: {file_path}")
            return False

        if not file_path.lower().endswith('.json'):
            print(f"⚠️  警告: 文件扩展名不是 .json")

        print(f"✅ 文件: {file_path}")
        print(f"📁 大小: {os.path.getsize(file_path):,} 字节")
        return True

    def _read_json(self, file_path):
        """读取JSON文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    return json.load(f)
            except:
                pass
        except json.JSONDecodeError as e:
            print(f"❌ JSON格式错误: {e}")
        except Exception as e:
            print(f"❌ 读取文件失败: {e}")

        return None

    def _ensure_tables(self):
        """确保数据库表存在"""
        cursor = self.conn.cursor()

        # 创建words表
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

        # 创建study_history表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS study_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id INTEGER,
            reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (word_id) REFERENCES words (id)
        )
        ''')

        self.conn.commit()

    def _import_data(self, data, update_existing):
        """导入数据到数据库"""
        cursor = self.conn.cursor()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        new_words = 0
        updated_words = 0
        error_words = 0

        print(f"\n🔄 开始导入单词...")
        print("-" * 50)

        for i, (word, details) in enumerate(data.items(), 1):
            try:
                # 检查单词是否已存在
                cursor.execute("SELECT id, occurrence_count FROM words WHERE word = ?", (word,))
                row = cursor.fetchone()

                if row:
                    if update_existing:
                        # 更新
                        new_count = row['occurrence_count'] + 1
                        cursor.execute('''
                        UPDATE words SET 
                            last_seen = ?,
                            occurrence_count = ?,
                            mastered = 0,
                            phonetic = COALESCE(?, phonetic),
                            meaning = COALESCE(?, meaning),
                            example = COALESCE(?, example),
                            example_cn = COALESCE(?, example_cn),
                            part_of_speech = COALESCE(?, part_of_speech),
                            difficulty = COALESCE(?, difficulty)
                        WHERE id = ?
                        ''', (
                            current_time,
                            new_count,
                            details.get('phonetic'),
                            details.get('meaning'),
                            details.get('example'),
                            details.get('example_cn'),
                            details.get('part_of_speech'),
                            details.get('difficulty'),
                            row['id']
                        ))
                        updated_words += 1
                else:
                    # 插入
                    cursor.execute('''
                    INSERT INTO words 
                    (word, phonetic, meaning, example, example_cn, part_of_speech, difficulty, 
                     last_seen, last_reviewed, occurrence_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        word,
                        details.get('phonetic', ''),
                        details.get('meaning', ''),
                        details.get('example', ''),
                        details.get('example_cn', ''),
                        details.get('part_of_speech', ''),
                        details.get('difficulty', 1),
                        current_time,
                        current_time,
                        1
                    ))
                    new_words += 1

                # 显示进度
                if i % 100 == 0 or i == len(data):
                    print(f"进度: {i}/{len(data)} 单词")

            except Exception as e:
                error_words += 1
                if error_words <= 3:
                    print(f"❌ 错误: {word} - {str(e)[:50]}")

        self.conn.commit()

        print("-" * 50)
        print(f"📈 导入完成:")
        print(f"   新增: {new_words} 单词")
        print(f"   更新: {updated_words} 单词")
        print(f"   错误: {error_words} 单词")
        print(f"   总计: {len(data)} 单词")

        return True, f"新增: {new_words}, 更新: {updated_words}, 错误: {error_words}"

    def _show_statistics(self):
        """显示数据库统计"""
        cursor = self.conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM words")
        total_words = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM words WHERE mastered = 1")
        mastered_words = cursor.fetchone()[0]

        cursor.execute("SELECT AVG(occurrence_count) FROM words")
        avg_occurrence = cursor.fetchone()[0] or 0

        print(f"\n📊 数据库统计:")
        print(f"   总单词数: {total_words}")
        print(f"   已掌握: {mastered_words}")
        print(f"   平均出现次数: {avg_occurrence:.1f}")


def main():
    """
    主函数 - 修改下面的路径即可
    """
    # ============================================
    # 请修改这里：设置您的JSON文件路径
    # ============================================
    YOUR_JSON_FILE = "words_with_details.json"  # 改成您的文件路径
    # 示例:
    # YOUR_JSON_FILE = r"C:\Users\YourName\Desktop\words.json"
    # YOUR_JSON_FILE = "/home/user/documents/vocabulary.json"
    # YOUR_JSON_FILE = "data/my_words.json"

    # 是否更新已存在的单词
    UPDATE_EXISTING = True  # True: 更新, False: 跳过

    # ============================================
    # 开始导入
    # ============================================

    importer = WordImporter()
    success, message = importer.import_json_file(YOUR_JSON_FILE, UPDATE_EXISTING)

    if success:
        print(f"\n✅ 导入成功！")
    else:
        print(f"\n❌ 导入失败: {message}")

if __name__ == "__main__":
    main()