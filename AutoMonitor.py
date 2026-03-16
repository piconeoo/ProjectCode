import json
import time
import os
from openai import OpenAI
# 直接复用你已经写好的导入类
from JsonImportToDataBase import WordImporter

# ==========================================
# 配置区 (请根据你的实际路径调整)
# ==========================================
JSON_FILE_PATH = "data/data_json.json"  # 服务器不断覆盖的源 JSON 文件
DB_PATH = "E:/Polyu/GraduateDesign/ProjectCode/vocabulary.db"  # 你的数据库绝对路径
LAST_TS_FILE = "last_timestamp.txt"  # 用于记录上次时间戳的缓存小文件

# 初始化阿里百炼客户端
client = OpenAI(
    api_key="sk-698867d6d2d24eefbf53f360b4fa276c",  # 你的 API Key
    base_url="https://dashscope.aliyuncs.com/api/v2/apps/protocols/compatible-mode/v1",
)


def get_word_details(word: str) -> dict:
    """
    调用阿里百炼大模型获取单词详细信息（新增难度评估功能）
    """
    prompt = f"""
    请为英语单词 '{word}' 提供以下详细信息，并用JSON格式返回：

    1. phonetic: 音标（国际音标，如 /ˌser.ənˈdɪp.ə.ti/）
    2. meaning: 中文释义（简洁准确）
    3. example: 英文例句
    4. example_cn: 例句的中文翻译
    5. part_of_speech: 词性（格式如 "n. 名词" 或 "adj. 形容词"）
    6. difficulty: 单词难度等级（请评估该词的难度，返回一个1到5的整数：1为初中/基础词汇，2为高中词汇，3为四六级词汇，4为考研/雅思词汇，5为GRE/托福等生僻难词）

    请确保返回的数据是有效的JSON格式，示例如下：
    {{
        "phonetic": "/ˈmɒn.ɪ.tər/",
        "meaning": "显示器；监视器",
        "example": "I need to buy a new monitor for my computer.",
        "example_cn": "我需要为我的电脑买一个新显示器。",
        "part_of_speech": "n. 名词",
        "difficulty": 2
    }}

    现在请为单词 '{word}' 提供信息：
    """

    try:
        response = client.responses.create(
            model="qwen-flash",
            input=prompt
        )

        result_text = response.output_text.strip()

        import re
        json_match = re.search(r'\{[\s\S]*\}', result_text)

        if json_match:
            json_str = json_match.group()
            word_details = json.loads(json_str)

            # 验证必需字段（把 difficulty 也加进来）
            required_fields = ['phonetic', 'meaning', 'example', 'example_cn', 'part_of_speech']
            for field in required_fields:
                if field not in word_details:
                    word_details[field] = "未知"

            # 单独验证难度字段，如果没有或者格式不对，默认给 1
            if 'difficulty' not in word_details or not isinstance(word_details['difficulty'], int):
                word_details['difficulty'] = 1

            return word_details
        else:
            print(f"警告: 无法从响应中提取JSON格式: {result_text}")
            return {
                "phonetic": "未知", "meaning": "未知", "example": "未知",
                "example_cn": "未知", "part_of_speech": "未知", "difficulty": 1
            }

    except Exception as e:
        print(f"获取单词 '{word}' 信息时出错: {e}")
        return {
            "phonetic": "错误", "meaning": "错误", "example": "错误",
            "example_cn": "错误", "part_of_speech": "错误", "difficulty": 1
        }
def monitor_and_update():
    """核心监控循环"""
    print("🚀 单词实时监控系统已启动...")

    # 1. 读取本地记录的最后一次时间戳
    last_ts = 0
    if os.path.exists(LAST_TS_FILE):
        with open(LAST_TS_FILE, 'r') as f:
            content = f.read().strip()
            last_ts = int(content) if content.isdigit() else 0

    print(f"👀 正在监控: {JSON_FILE_PATH} (当前记忆的时间戳: {last_ts})")

    while True:
        try:
            if os.path.exists(JSON_FILE_PATH):
                with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 提取当前 JSON 的时间戳
                current_ts = data.get('timestamp', 0)

                # 2. 判断是否更新
                if current_ts > last_ts:
                    print(f"\n🔔 [检测到更新] 发现新文件！新时间戳: {current_ts}")

                    words_list = data.get('words', [])
                    english_words = [item.get('english') for item in words_list if item.get('english')]

                    if english_words:
                        all_results = {}
                        for i, word in enumerate(english_words, 1):
                            print(f"   🤖 正在请求大模型 [{i}/{len(english_words)}]: {word}")
                            all_results[word] = get_word_details(word)
                            time.sleep(1)  # 防被封限制

                        # 临时保存为中间 JSON 以供导入
                        temp_json = "words_with_details.json"
                        with open(temp_json, 'w', encoding='utf-8') as f:
                            json.dump(all_results, f, ensure_ascii=False, indent=2)

                        # 3. 自动调用导入工具写入 SQLite
                        print("   💾 正在写入数据库...")
                        importer = WordImporter(db_path=DB_PATH)
                        success, msg = importer.import_json_file(temp_json, update_existing=True)

                        if success:
                            # 4. 一切成功后，更新本地时间戳缓存
                            last_ts = current_ts
                            with open(LAST_TS_FILE, 'w') as f:
                                f.write(str(last_ts))
                            print("✅ 数据库实时更新完成！等待下一次服务器推送...")
                        else:
                            print(f"❌ 数据库导入失败: {msg}")
                    else:
                        print("⚠️ JSON 里没有找到英文单词，跳过处理。")
                        # 依然更新时间戳，防止死循环无限重试
                        last_ts = current_ts
                        with open(LAST_TS_FILE, 'w') as f:
                            f.write(str(last_ts))

        except json.JSONDecodeError:
            print(f"\r⚠️ 等待中：JSON 文件格式错误或正在被服务器写入...", end="")
        except Exception as e:
            print(f"\r⚠️ 监控报错: {e}", end="")

        # 5. 每隔 3 秒检查一次文件
        time.sleep(3)


if __name__ == "__main__":
    monitor_and_update()