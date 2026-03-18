import streamlit as st
import json
from openai import OpenAI
import re
import streamlit.components.v1 as components

# 初始化大模型客户端
client = OpenAI(
    api_key="sk-698867d6d2d24eefbf53f360b4fa276c",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)


def generate_scenario_vocab(scenario):
    """调用大模型生成场景地道表达 (10个词组 + 10个句子)"""
    prompt = f"""
    你是一个资深的英语母语外教。用户当前需要去应对的场景是：“{scenario}”。
    请提供该场景下最地道、最实用的内容，具体要求严格如下：

    1. 必须提供正好 10 个该场景下的【高频词汇/词组】（例如餐厅场景的 private room 包间, outside wine 自带酒水等，专治“不知道怎么地道表达”的词汇）。
    2. 必须提供正好 10 个该场景下的【实用短句】（要求：必须是用户作为顾客/访客/主动发起方自己开口说的话）。
    3. 坚决避免传统的“中式英语 (Chinglish)”或书本上繁琐僵硬的表达，使用 Native speaker 日常生活真正使用的“懒人”表达。

    请严格以 JSON 对象格式返回，包含 "words" 和 "sentences" 两个数组，格式如下：
    {{
        "words": [
            {{"english": "private room", "chinese": "包间", "tips": "预订餐厅时的常用实用词"}},
            // ... 必须给满 10 个
        ],
        "sentences": [
            {{"english": "A table for four, please.", "chinese": "我要订四人桌", "tips": "日常口语中直接说人数即可，比make a reservation更自然"}},
            // ... 必须给满 10 个
        ]
    }}
    不要输出任何其他解释性文字，只输出合法的 JSON 对象。
    """
    try:
        response = client.chat.completions.create(
            model="qwen-plus",
            messages=[{"role": "user", "content": prompt}]
        )
        result = response.choices[0].message.content.strip()
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            return json.loads(json_match.group())
        return {"words": [], "sentences": []}
    except Exception as e:
        st.error(f"生成失败，请重试: {e}")
        return {"words": [], "sentences": []}


def render_voice_call_room(scenario, vocab_dict):
    """
    核心黑科技：嵌入式 Web 语音通话舱
    利用原生 JS 实现真正的“无限循环实时语音通话”，自带断线重连和身份锁。
    """
    all_items = vocab_dict.get('words', []) + vocab_dict.get('sentences', [])
    vocab_str = ", ".join([v['english'] for v in all_items])

    safe_scenario = scenario.replace("'", "\\'").replace('"', '\\"')
    safe_vocab = vocab_str.replace("'", "\\'").replace('"', '\\"')
    api_key = "sk-698867d6d2d24eefbf53f360b4fa276c"

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0e1117; color: #fafafa; padding: 10px; }}
        .controls {{ text-align: center; margin-bottom: 20px; }}
        .btn {{ padding: 15px 40px; font-size: 20px; font-weight: bold; border-radius: 50px; border: none; cursor: pointer; color: white; transition: 0.3s; box-shadow: 0 4px 15px rgba(0,0,0,0.3); margin: 0 10px; }}

        .btn-start {{ background: linear-gradient(45deg, #2ecc71, #27ae60); }}
        .btn-start:hover {{ transform: scale(1.05); }}

        .btn-end {{ background: linear-gradient(45deg, #e74c3c, #c0392b); display: none; }}
        .btn-end:hover {{ transform: scale(1.05); }}

        .btn-retry {{ background: linear-gradient(45deg, #f39c12, #d35400); display: none; }}
        .btn-retry:hover {{ transform: scale(1.05); }}

        #status-box {{ text-align: center; margin-bottom: 15px; }}
        #status-text {{ font-size: 18px; color: #f39c12; font-weight: bold; padding: 10px 20px; background: rgba(243, 156, 18, 0.1); border-radius: 20px; display: inline-block; }}

        #chat-history {{ height: 400px; overflow-y: auto; background: #1a1c23; padding: 20px; border-radius: 15px; border: 1px solid #333; }}
        .msg {{ margin-bottom: 15px; padding: 12px 18px; border-radius: 15px; max-width: 80%; line-height: 1.6; font-size: 16px; }}
        .msg.ai {{ background-color: #2c3e50; color: #ecf0f1; float: left; border-bottom-left-radius: 2px; clear: both; }}
        .msg.user {{ background-color: #2980b9; color: white; float: right; border-bottom-right-radius: 2px; clear: both; }}
        .msg.system {{ background-color: #1e272e; color: #d2dae2; float: left; width: 95%; clear: both; border: 2px solid #f39c12; box-shadow: 0 0 15px rgba(243, 156, 18, 0.2); border-radius: 10px; }}
        .msg.system b {{ color: #f1c40f; }} 
    </style>
    </head>
    <body>

    <div class="controls">
        <button id="startBtn" class="btn btn-start">📞 接入外教，开始对话</button>
        <button id="endBtn" class="btn btn-end">☎️ 结束通话并获取总结</button>
        <button id="retryBtn" class="btn btn-retry">🔄 网络出错，点击重试</button>
    </div>

    <div id="status-box">
        <span id="status-text">点击上方按钮开始实时模拟通话</span>
    </div>

    <div id="chat-history"></div>

    <script>
        const API_KEY = '{api_key}';
        const SCENARIO = '{safe_scenario}';
        const VOCAB = '{safe_vocab}';

        let isCallActive = false;
        let isAIProcessing = false;
        let currentAction = ''; 

        // 【核心修改】：重写底层身份锁 Prompt，彻底防止 AI 抢戏
        let history = [
            {{"role": "system", "content": `你现在是一名专业的英语口语外教。场景：${{SCENARIO}}。
            【身份锁】：你必须且**只能**扮演该场景下的接待方/服务人员（如餐厅服务员、海关签证官、店员等）。用户是你的**顾客/访客**。

            执行要求：
            1. 每次只说1-2句短语，像真人一样简短自然。
            2. 【核心任务】：你要通过不断地提问或回应，引导顾客（用户）主动说出以下这些词汇和句子：[${{VOCAB}}]。
            3. 【最高红线】：你绝对不可以抢走顾客的台词！上面括号里提供的目标句子是**属于用户的**，你坚决不能在你的回复中直接输出它们（例如：绝不能替用户说“我们迟到了”或“我要点单”等顾客才会说的话）。
            4. 绝对不要在对话中纠正用户的语法或给出建议！即使他用了中式英语，你也要像真的服务员一样顺着剧情聊下去，纠错留在通话结束后。
            5. 回复中禁止使用任何 Emoji 表情。

            现在，请直接用一句符合你“服务人员”身份的英文开场白（如欢迎光临或询问需求）开始对话！`}}
        ];

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        let recognition = new SpeechRecognition();
        recognition.lang = 'en-US';
        recognition.continuous = false; 
        recognition.interimResults = false;

        const startBtn = document.getElementById('startBtn');
        const endBtn = document.getElementById('endBtn');
        const retryBtn = document.getElementById('retryBtn');
        const statusText = document.getElementById('status-text');
        const chatBox = document.getElementById('chat-history');

        function logMsg(role, text) {{
            let div = document.createElement('div');
            div.className = 'msg ' + role;
            let prefix = role === 'user' ? '🧑‍🎓 你' : (role === 'ai' ? '👩‍🏫 外教' : '📋 外教评估单');
            div.innerHTML = `<strong>${{prefix}}:</strong><br><br>${{text}}`;
            chatBox.appendChild(div);
            chatBox.scrollTop = chatBox.scrollHeight;
        }}

        retryBtn.onclick = () => {{
            retryBtn.style.display = 'none'; 
            if (currentAction === 'chat') {{
                statusText.innerText = "⏳ 正在重新连接外教...";
                statusText.style.color = "#f39c12";
                fetchAIResponse();
            }} else if (currentAction === 'summary') {{
                statusText.innerText = "📝 正在重新生成评估报告...";
                statusText.style.color = "#3498db";
                fetchSummary();
            }}
        }};

        startBtn.onclick = () => {{
            isCallActive = true;
            isAIProcessing = true;
            startBtn.style.display = 'none';
            endBtn.style.display = 'inline-block';
            statusText.innerText = "⏳ 外教正在接入中...";
            statusText.style.color = "#f39c12";

            fetchAIResponse();
        }};

        endBtn.onclick = () => {{
            isCallActive = false;
            recognition.stop();
            window.speechSynthesis.cancel();

            endBtn.style.display = 'none';
            retryBtn.style.display = 'none';

            statusText.innerText = "📝 通话已结束，正在为您生成评估报告...";
            statusText.style.color = "#3498db";

            let summaryPrompt = `（挂断电话）。对话已经结束，请切出角色，对我刚才所有的口语表现进行专业的中文总结。请务必严格按照以下三个板块输出，保持排版清晰美观：

🎯 【综合评价】
（请用1-2句话评价我的整体表现和沟通流畅度）

🚨 【纠错与优化】
（请分点列出我在对话中的语法错误、用词不当或中式英语，并给出地道的正确说法）

💡 【学习建议】
（给出1-2个后续练习这条场景口语的具体建议）`;

            history.push({{"role": "user", "content": summaryPrompt }});
            fetchSummary();
        }};

        function fetchAIResponse() {{
            currentAction = 'chat'; 
            fetch('https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions', {{
                method: 'POST',
                headers: {{ 'Authorization': 'Bearer ' + API_KEY, 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ model: 'qwen-plus', messages: history }})
            }})
            .then(r => r.json())
            .then(data => {{
                if(data.error) throw new Error(data.error.message);
                let aiText = data.choices[0].message.content;
                history.push({{"role": "assistant", "content": aiText}});
                logMsg('ai', aiText);
                speakText(aiText);
            }})
            .catch(e => {{ 
                console.error(e);
                statusText.innerText = "❌ 信号中断，请点击重试按钮"; 
                statusText.style.color = "#e74c3c";
                retryBtn.style.display = 'inline-block';
            }});
        }}

        function fetchSummary() {{
            currentAction = 'summary'; 
            fetch('https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions', {{
                method: 'POST',
                headers: {{ 'Authorization': 'Bearer ' + API_KEY, 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ model: 'qwen-plus', messages: history }})
            }})
            .then(r => r.json())
            .then(data => {{
                if(data.error) throw new Error(data.error.message);
                let rawText = data.choices[0].message.content;
                let formattedText = rawText
                    .replace(/\\*\\*(.*?)\\*\\*/g, '<b>$1</b>')
                    .replace(/\\n/g, '<br>');               

                logMsg('system', formattedText);
                statusText.innerText = "✅ 报告已生成，您可以开启新的场景练习了！";
                statusText.style.color = "#2ecc71";
            }})
            .catch(e => {{
                console.error(e);
                statusText.innerText = "❌ 报告生成失败，请重试"; 
                statusText.style.color = "#e74c3c";
                retryBtn.style.display = 'inline-block';
            }});
        }}

        function speakText(text) {{
            if (!isCallActive) return;
            window.speechSynthesis.cancel(); 

            let cleanText = text.replace(/\\p{{Emoji_Presentation}}/gu, '').trim();
            let msg = new SpeechSynthesisUtterance(cleanText);
            msg.lang = 'en-US';

            statusText.innerText = "🔊 外教正在说话...";
            statusText.style.color = "#9b59b6";

            msg.onend = () => {{
                if (isCallActive) {{
                    isAIProcessing = false;
                    statusText.innerText = "🎤 请直接说话 (正在聆听)...";
                    statusText.style.color = "#2ecc71";
                    try {{ recognition.start(); }} catch(e){{}}
                }}
            }};
            window.speechSynthesis.speak(msg);
        }}

        recognition.onresult = (event) => {{
            if (!isCallActive) return;

            let userText = event.results[0][0].transcript;
            if (userText.trim() !== "") {{
                recognition.stop(); 
                isAIProcessing = true; 

                logMsg('user', userText);
                history.push({{"role": "user", "content": userText}});

                statusText.innerText = "⏳ 外教正在思考回复...";
                statusText.style.color = "#e67e22";

                fetchAIResponse();
            }}
        }};

        recognition.onend = () => {{
            if (isCallActive && !isAIProcessing && !window.speechSynthesis.speaking) {{
                try {{ recognition.start(); }} catch(e){{}}
            }}
        }};

        recognition.onerror = (event) => {{
            if (event.error !== 'no-speech') {{
                console.log("Mic Error: ", event.error);
            }}
        }};
    </script>
    </body>
    </html>
    """
    components.html(html_code, height=650, scrolling=True)


def render_page(play_audio_func):
    """渲染主页面"""
    st.title("🗣️ 场景实战 (AI 1v1 私教)")
    st.write("完全沉浸式的英语语境模拟，**不用点击发送，像打电话一样直接交流！**")

    # 状态初始化
    if 'scenario_vocab' not in st.session_state:
        st.session_state['scenario_vocab'] = {}
    if 'current_scenario' not in st.session_state:
        st.session_state['current_scenario'] = ""
    if 'scenario_vocab_index' not in st.session_state:
        st.session_state['scenario_vocab_index'] = 0

    with st.container(border=True):
        scenario_input = st.text_input("📍 请输入你想练习的场景 (例如：在餐厅预订座位、在机场过海关)：")
        if st.button("✨ 生成地道表达", type="primary"):
            if scenario_input:
                with st.spinner("AI 外教正在为你定制独家地道词汇与金句..."):
                    vocab = generate_scenario_vocab(scenario_input)
                    if vocab and (vocab.get('words') or vocab.get('sentences')):
                        st.session_state['scenario_vocab'] = vocab
                        st.session_state['current_scenario'] = scenario_input
                        st.session_state['scenario_vocab_index'] = 0
                        st.rerun()

    if st.session_state['scenario_vocab']:
        vocab_data = st.session_state['scenario_vocab']

        all_items = []
        for w in vocab_data.get('words', []):
            w['type_label'] = '📚 核心词汇'
            all_items.append(w)
        for s in vocab_data.get('sentences', []):
            s['type_label'] = '💬 实用短句'
            all_items.append(s)

        total_items = len(all_items)
        items_per_page = 2
        total_pages = (total_items + items_per_page - 1) // items_per_page
        current_page = st.session_state.get('scenario_vocab_index', 0)

        st.markdown(f"### 💡 【{st.session_state['current_scenario']}】 实用表达包")

        col_prev, col_space, col_next = st.columns([1, 8, 1])
        with col_prev:
            if st.button("⬅️ 上一页"):
                st.session_state['scenario_vocab_index'] = (current_page - 1) if current_page > 0 else (total_pages - 1)
                st.rerun()
        with col_space:
            st.markdown(
                f"<div style='text-align: center; padding-top: 10px; color: #7f8c8d; font-weight: bold;'>第 {current_page + 1} / {total_pages} 页</div>",
                unsafe_allow_html=True)
        with col_next:
            if st.button("下一页 ➡️"):
                st.session_state['scenario_vocab_index'] = (current_page + 1) if current_page < total_pages - 1 else 0
                st.rerun()

        start_idx = current_page * items_per_page
        end_idx = min(start_idx + items_per_page, total_items)
        page_items = all_items[start_idx:end_idx]

        for item in page_items:
            with st.container(border=True):
                st.markdown(f"##### {item['type_label']}")
                col1, col2 = st.columns([10, 1])
                with col1:
                    st.markdown(
                        f"<div style='font-size: 1.8rem; font-weight: bold; color: #2e86c1; margin-bottom: 10px;'>{item['english']}</div>",
                        unsafe_allow_html=True)
                    st.markdown(f"**🎯 释义**: {item['chinese']}")
                    st.markdown(f"**💡 外教提示**: {item['tips']}")
                with col2:
                    play_audio_func(item['english'])

        st.markdown("---")
        st.markdown("### 🎭 实时语音通话舱")
        render_voice_call_room(st.session_state['current_scenario'], st.session_state['scenario_vocab'])