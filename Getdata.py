import json
import time
from openai import OpenAI

# 1. 读取JSON文件获取单词列表
with open('data/data_json.json', 'r', encoding='utf-8') as file:
    data = json.load(file)

# 2. 从数据中提取'words'列表
words_list = data.get('words', [])  # 安全获取，如果'words'不存在则返回空列表

# 3. 提取所有英文单词
english_words = []
for item in words_list:
    english_word = item.get('english')
    if english_word:
        english_words.append(english_word)

print(f"找到 {len(english_words)} 个英语单词:")
for i, word in enumerate(english_words, 1):
    print(f"{i}. {word}")

# 4. 初始化阿里百炼客户端
client = OpenAI(
    api_key="sk-698867d6d2d24eefbf53f360b4fa276c",  # 你的API密钥
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
def process_all_words():
    """
    处理所有单词并保存结果
    """
    all_results = {}

    for i, word in enumerate(english_words, 1):
        print(f"\n[{i}/{len(english_words)}] 正在处理单词: {word}")

        # 调用 API 获取单词详情
        word_details = get_word_details(word)

        # 存储结果
        all_results[word] = word_details

        # 打印当前单词的结果
        print(f"  音标：{word_details.get('phonetic')}")
        print(f"  释义：{word_details.get('meaning')}")
        print(f"  词性：{word_details.get('part_of_speech')}")
        print(f"  难度：{'★' * word_details.get('difficulty', 0)}")

        # 避免请求频率过高，添加延迟
        time.sleep(1)  # 1 秒延迟，避免触发 API 限制

    # 5. 保存结果到新 JSON 文件
    output_file = "words_with_details.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 50}")
    print(f"处理完成！")
    print(f"共处理 {len(english_words)} 个单词")
    print(f"结果已保存到：{output_file}")

    # 6. 可选：打印汇总结果
    print(f"\n汇总结果:")
    for word, details in all_results.items():
        print(f"\n{word}:")
        for key, value in details.items():
            print(f"  {key}: {value}")

    return all_results


# 主程序入口
if __name__ == "__main__":
   process_all_words()

