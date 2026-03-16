import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import random
import streamlit.components.v1 as components  # 新增：用于渲染语音播放按钮

# ==========================================
# 页面配置
# ==========================================
st.set_page_config(page_title="Personal Vocab Builder", page_icon="📚", layout="wide")


# ==========================================
# 语音播报组件 (Web Speech API)
# ==========================================
def play_audio(text):
    """利用浏览器原生 API 实现语音播报的按钮"""
    # 处理文本中的特殊字符，防止 JS 报错
    safe_text = text.replace("'", "\\'").replace('"', '\\"').replace('\n', ' ')
    html_code = f"""
        <div style="display: flex; align-items: center; justify-content: center; height: 100%; padding-top: 10px;">
            <button onclick="var msg = new SpeechSynthesisUtterance('{safe_text}'); msg.lang='en-US'; window.speechSynthesis.speak(msg);" 
                    style="background: none; border: none; font-size: 1.8rem; cursor: pointer; transition: transform 0.1s;"
                    onmouseover="this.style.transform='scale(1.2)'" 
                    onmouseout="this.style.transform='scale(1)'"
                    title="点击朗读">
                🔊
            </button>
        </div>
    """
    # 渲染高度为 50px 的透明内嵌 HTML
    components.html(html_code, height=60, width=60)


# ==========================================
# 数据库辅助函数
# ==========================================
DB_PATH = "E:/Polyu/GraduateDesign/ProjectCode/vocabulary.db"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def get_db_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    stats = {}

    cursor.execute("SELECT COUNT(*) FROM words")
    stats['total'] = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM words WHERE mastered=1")
    stats['mastered'] = cursor.fetchone()[0] or 0

    today_str = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("SELECT COUNT(*) FROM study_history WHERE date(reviewed_at) = ?", (today_str,))
    stats['today_study'] = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM study_history")
    stats['total_study'] = cursor.fetchone()[0] or 0

    conn.close()
    return stats


def fetch_all_words_dict():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, word, phonetic, meaning, part_of_speech, 
               example, example_cn, difficulty, mastered 
        FROM words ORDER BY id ASC
    """)
    words = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return words


def toggle_word_mastery(word_id, current_status):
    new_status = 0 if current_status == 1 else 1
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE words SET mastered=? WHERE id=?", (new_status, word_id))
    conn.commit()
    conn.close()


def fetch_today_review_words():
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT * FROM words 
        WHERE mastered = 0 
        AND CAST(julianday(date('now', 'localtime')) - julianday(date(last_seen)) AS INTEGER) IN (0, 1, 4, 6)
    """
    cursor.execute(query)
    words = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return words


def fetch_practice_words():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM words WHERE mastered = 0 ORDER BY RANDOM()")
    words = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return words


def record_study_result(word_id, days_diff):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    today_str = datetime.now().strftime('%Y-%m-%d')

    cursor.execute("SELECT COUNT(*) FROM study_history WHERE word_id = ? AND date(reviewed_at) = ?",
                   (word_id, today_str))
    has_studied_today = cursor.fetchone()[0] > 0

    if not has_studied_today:
        cursor.execute("INSERT INTO study_history (word_id, reviewed_at) VALUES (?, ?)", (word_id, now))

    cursor.execute("UPDATE words SET last_reviewed = ? WHERE id = ?", (now, word_id))

    if days_diff >= 6:
        cursor.execute("UPDATE words SET mastered = 1 WHERE id = ?", (word_id,))

    conn.commit()
    conn.close()


def mask_word(word):
    chars = list(word)
    length = len(chars)
    if length <= 1: return "_"
    num_hide = max(1, length // 2)
    hide_indices = random.sample(range(length), num_hide)
    for i in hide_indices:
        if chars[i].isalpha():
            chars[i] = '_'
    return ''.join(chars)


# ==========================================
# 状态管理 (Session State)
# ==========================================
if 'hall_words' not in st.session_state:
    st.session_state['hall_words'] = fetch_all_words_dict()
if 'hall_index' not in st.session_state:
    st.session_state['hall_index'] = 0

if 'today_learn_index' not in st.session_state:
    st.session_state['today_learn_index'] = 0

if 'review_words' not in st.session_state:
    st.session_state['review_words'] = fetch_today_review_words()
if 'current_word_index' not in st.session_state:
    st.session_state['current_word_index'] = 0
if 'masked_current_word' not in st.session_state:
    st.session_state['masked_current_word'] = None
if 'test_completed' not in st.session_state:
    st.session_state['test_completed'] = False

if 'word_passed' not in st.session_state:
    st.session_state['word_passed'] = False
if 'is_practice_mode' not in st.session_state:
    st.session_state['is_practice_mode'] = False
if 'show_correction' not in st.session_state:
    st.session_state['show_correction'] = False

# ==========================================
# 自定义 CSS
# ==========================================
st.markdown("""
<style>
.word-title { font-size: 3.5rem; font-weight: bold; color: #2e86c1; margin-bottom: 5px; }
.word-phonetic { font-size: 1.3rem; color: #7f8c8d; margin-bottom: 15px; }
.info-row { font-size: 1.1rem; margin-bottom: 8px; }
.index-box { background-color: #2874a6; color: white; border-radius: 10px; padding: 30px 20px; text-align: center; height: 100%; display: flex; flex-direction: column; justify-content: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
.index-title { font-size: 1.5rem; font-weight: bold; margin-bottom: 15px; }
.index-number { font-size: 4rem; font-weight: bold; line-height: 1; }
.index-total { font-size: 1.2rem; margin-top: 10px; opacity: 0.8; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 侧边栏导航与控制面板
# ==========================================
st.sidebar.title("📚 导航菜单")
page = st.sidebar.radio("选择功能", ["📅 今日需学", "📖 单词大厅", "🎯 今日测试"])
st.sidebar.markdown("---")

stats = get_db_stats()

if page == "📖 单词大厅" and stats['total'] > 0:
    total_words = stats['total']
    st.sidebar.markdown("### 🎛️ 学习控制")
    current_idx = st.session_state.get('hall_index', 0)
    progress = (current_idx + 1) / total_words
    st.sidebar.progress(progress, text=f"进度: {current_idx + 1} / {total_words}")

    col_jump1, col_jump2 = st.sidebar.columns([2, 1])
    with col_jump1:
        jump_target = st.number_input("跳转到编号", min_value=1, max_value=total_words, value=current_idx + 1,
                                      label_visibility="collapsed")
    with col_jump2:
        if st.button("跳转", use_container_width=True):
            st.session_state['hall_index'] = jump_target - 1
            st.rerun()

    if st.sidebar.button("🎲 随机单词", use_container_width=True):
        st.session_state['hall_index'] = random.randint(0, total_words - 1)
        st.rerun()
    st.sidebar.markdown("---")

elif page == "📅 今日需学":
    today_learn_list = fetch_today_review_words()
    total_words = len(today_learn_list)
    if total_words > 0:
        st.sidebar.markdown("### 🎛️ 学习控制")
        current_idx = st.session_state.get('today_learn_index', 0)
        if current_idx >= total_words:
            current_idx = 0
            st.session_state['today_learn_index'] = 0

        progress = (current_idx + 1) / total_words
        st.sidebar.progress(progress, text=f"进度: {current_idx + 1} / {total_words}")

        col_jump1, col_jump2 = st.sidebar.columns([2, 1])
        with col_jump1:
            jump_target = st.number_input("跳转到编号", min_value=1, max_value=total_words, value=current_idx + 1,
                                          label_visibility="collapsed")
        with col_jump2:
            if st.button("跳转", use_container_width=True):
                st.session_state['today_learn_index'] = jump_target - 1
                st.rerun()

        if st.sidebar.button("🎲 随机单词", use_container_width=True):
            st.session_state['today_learn_index'] = random.randint(0, total_words - 1)
            st.rerun()
        st.sidebar.markdown("---")

st.sidebar.markdown("### 📊 学习统计")
c1, c2 = st.sidebar.columns(2)
c1.metric("总单词数", stats['total'])
c2.metric("已掌握", stats['mastered'])
c3, c4 = st.sidebar.columns(2)
c3.metric("今日学习", stats['today_study'])
c4.metric("总学习", stats['total_study'])
st.sidebar.markdown("---")

if stats['total'] > 0:
    df_export = pd.DataFrame(fetch_all_words_dict())
    if not df_export.empty:
        csv_data = df_export.to_csv(index=False).encode('utf-8-sig')
        st.sidebar.download_button("📥 导出单词库 (CSV)", data=csv_data, file_name="my_words.csv", mime="text/csv",
                                   use_container_width=True)

# ==========================================
# 页面 0: 今日需学
# ==========================================
if page == "📅 今日需学":
    st.title("📅 今日需学")
    st.write("在这里你可以提前预览、朗读并记忆今天【今日测试】中将会出现的所有单词。")

    today_words = fetch_today_review_words()

    if not today_words:
        st.success("🎉 太棒了！今天没有需要学习或复习的单词！你可以去【单词大厅】随便逛逛。")
    else:
        idx = st.session_state.get('today_learn_index', 0)
        if idx >= len(today_words):
            idx = 0
            st.session_state['today_learn_index'] = 0

        word_data = today_words[idx]

        col_prev, col_space, col_next = st.columns([1, 8, 1])
        with col_prev:
            if st.button("⬅️ 上一个") and idx > 0:
                st.session_state['today_learn_index'] -= 1
                st.rerun()
        with col_next:
            if st.button("下一个 ➡️") and idx < len(today_words) - 1:
                st.session_state['today_learn_index'] += 1
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        col_main, col_side = st.columns([3, 1])
        with col_main:
            with st.container(border=True):
                # 利用列布局将单词与语音按钮并排
                c_w, c_sound = st.columns([8, 1])
                with c_w:
                    st.markdown(f'<div class="word-title">{word_data["word"]}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="word-phonetic">{word_data["phonetic"]}</div>', unsafe_allow_html=True)
                with c_sound:
                    play_audio(word_data["word"])

                st.markdown(f'<div class="info-row"><b>词性:</b> {word_data["part_of_speech"]}</div>',
                            unsafe_allow_html=True)
                st.markdown(f'<div class="info-row"><b>中文释义:</b> {word_data["meaning"]}</div>',
                            unsafe_allow_html=True)
                st.markdown(f'<div class="info-row"><b>难度等级:</b> {"⭐" * word_data["difficulty"]}</div>',
                            unsafe_allow_html=True)
                status_icon = "✅ 已掌握" if word_data["mastered"] == 1 else "⏳ 学习中"
                st.markdown(f'<div class="info-row"><b>掌握状态:</b> {status_icon}</div>', unsafe_allow_html=True)
        with col_side:
            st.markdown(f"""
            <div class="index-box">
                <div class="index-title">今日单词</div>
                <div class="index-number">{idx + 1}</div>
                <div class="index-total">/ {len(today_words)}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        is_mastered = word_data["mastered"] == 1
        btn_label = "❌ 取消掌握标记" if is_mastered else "✅ 标记为已掌握 (今日不再测)"
        btn_type = "secondary" if is_mastered else "primary"

        if st.button(btn_label, use_container_width=True, type=btn_type):
            toggle_word_mastery(word_data["id"], word_data["mastered"])
            st.rerun()

        st.markdown("### 📝 例句")
        with st.container(border=True):
            # 例句旁边也加入语音按钮
            c_ex, c_ex_sound = st.columns([12, 1])
            with c_ex:
                st.markdown(f"*{word_data['example']}*")
                if word_data['example_cn']:
                    st.markdown(f"**{word_data['example_cn']}**")
            with c_ex_sound:
                play_audio(word_data['example'])


# ==========================================
# 页面 1: 单词大厅
# ==========================================
elif page == "📖 单词大厅":
    st.title("📖 单词大厅")

    st.session_state['hall_words'] = fetch_all_words_dict()
    all_words = st.session_state.get('hall_words', [])

    if not all_words:
        st.info("数据库中暂时没有单词，请先运行你的 JSON 导入脚本！")
    else:
        idx = st.session_state.get('hall_index', 0)
        if idx >= len(all_words):
            idx = 0
            st.session_state['hall_index'] = 0

        word_data = all_words[idx]
        col_prev, col_space, col_next = st.columns([1, 8, 1])
        with col_prev:
            if st.button("⬅️ 上一个") and idx > 0:
                st.session_state['hall_index'] -= 1
                st.rerun()
        with col_next:
            if st.button("下一个 ➡️") and idx < len(all_words) - 1:
                st.session_state['hall_index'] += 1
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        col_main, col_side = st.columns([3, 1])
        with col_main:
            with st.container(border=True):
                # 单词发音按钮
                c_w, c_sound = st.columns([8, 1])
                with c_w:
                    st.markdown(f'<div class="word-title">{word_data["word"]}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="word-phonetic">{word_data["phonetic"]}</div>', unsafe_allow_html=True)
                with c_sound:
                    play_audio(word_data["word"])

                st.markdown(f'<div class="info-row"><b>词性:</b> {word_data["part_of_speech"]}</div>',
                            unsafe_allow_html=True)
                st.markdown(f'<div class="info-row"><b>中文释义:</b> {word_data["meaning"]}</div>',
                            unsafe_allow_html=True)
                st.markdown(f'<div class="info-row"><b>难度等级:</b> {"⭐" * word_data["difficulty"]}</div>',
                            unsafe_allow_html=True)
                status_icon = "✅ 已掌握" if word_data["mastered"] == 1 else "⏳ 学习中"
                st.markdown(f'<div class="info-row"><b>掌握状态:</b> {status_icon}</div>', unsafe_allow_html=True)
        with col_side:
            st.markdown(f"""
            <div class="index-box">
                <div class="index-title">总词库</div>
                <div class="index-number">{idx + 1}</div>
                <div class="index-total">/ {len(all_words)}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        is_mastered = word_data["mastered"] == 1
        btn_label = "❌ 取消掌握标记" if is_mastered else "✅ 标记为已掌握"
        btn_type = "secondary" if is_mastered else "primary"

        if st.button(btn_label, use_container_width=True, type=btn_type):
            toggle_word_mastery(word_data["id"], word_data["mastered"])
            st.rerun()

        st.markdown("### 📝 例句")
        with st.container(border=True):
            # 例句发音按钮
            c_ex, c_ex_sound = st.columns([12, 1])
            with c_ex:
                st.markdown(f"*{word_data['example']}*")
                if word_data['example_cn']:
                    st.markdown(f"**{word_data['example_cn']}**")
            with c_ex_sound:
                play_audio(word_data['example'])


# ==========================================
# 页面 2: 今日测试
# ==========================================
elif page == "🎯 今日测试":
    st.title("🎯 今日测试")

    words_to_review = st.session_state.get('review_words', [])
    total_words = len(words_to_review)


    def reset_test_states(mode="routine"):
        if mode == "practice":
            st.session_state['review_words'] = fetch_practice_words()
            st.session_state['is_practice_mode'] = True
        else:
            st.session_state['review_words'] = fetch_today_review_words()
            st.session_state['is_practice_mode'] = False

        st.session_state['current_word_index'] = 0
        st.session_state['test_completed'] = False
        st.session_state['masked_current_word'] = None
        st.session_state['word_passed'] = False
        st.session_state['show_correction'] = False


    if total_words == 0 or st.session_state.get('test_completed', False):
        if total_words == 0:
            st.success("🎉 太棒了！今天的艾宾浩斯复习任务已经全部完成，或者今天没有待复习单词！")
        else:
            st.balloons()
            st.success("🏆 恭喜你！完成了当前所有的单词测试！")

        st.markdown("### 接下来你想做什么？")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 检查今日复习任务", use_container_width=True):
                reset_test_states("routine")
                st.rerun()
        with col2:
            if st.button("🚀 开启自由练习 (不限天数)", use_container_width=True, type="primary"):
                reset_test_states("practice")
                st.rerun()

    else:
        current_idx = st.session_state.get('current_word_index', 0)
        progress = current_idx / total_words

        if st.session_state.get('is_practice_mode', False):
            st.progress(progress, text=f"自由练习进度: {current_idx}/{total_words} (今日数据不重复增加)")
        else:
            st.progress(progress, text=f"今日复习进度: {current_idx}/{total_words}")

        current_word_data = words_to_review[current_idx]
        actual_word = current_word_data['word']

        last_seen_date = datetime.strptime(current_word_data['last_seen'], '%Y-%m-%d %H:%M:%S').date()
        today_date = datetime.now().date()
        days_diff = (today_date - last_seen_date).days

        if st.session_state.get('masked_current_word') is None:
            st.session_state['masked_current_word'] = mask_word(actual_word)

        with st.container(border=True):
            st.subheader(f"💡 词义: {current_word_data['meaning']}")
            st.caption(f"词性: {current_word_data['part_of_speech']} | 难度: {'⭐' * current_word_data['difficulty']}")
            st.info(f"复习阶段: 最近遇到后的第 {days_diff + 1} 天")

            if not st.session_state.get('word_passed', False):

                # 答错时的纠错界面
                if st.session_state.get('show_correction', False):
                    st.error("❌ 回答错误！请仔细看正确拼写和例句：")

                    # 纠错页单词发音
                    c_err_w, c_err_sound = st.columns([8, 1])
                    with c_err_w:
                        st.markdown(f"### 正确答案: <span style='color:#e74c3c;'>{actual_word}</span>",
                                    unsafe_allow_html=True)
                    with c_err_sound:
                        play_audio(actual_word)

                    if current_word_data['example']:
                        # 纠错页例句发音
                        c_err_ex, c_err_ex_sound = st.columns([12, 1])
                        with c_err_ex:
                            st.write(f"**例句:** {current_word_data['example']}")
                            if current_word_data['example_cn']:
                                st.write(f"**翻译:** {current_word_data['example_cn']}")
                        with c_err_ex_sound:
                            play_audio(current_word_data['example'])

                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🔄 记住了，再来一次！", type="primary"):
                        st.session_state['show_correction'] = False
                        st.session_state['masked_current_word'] = mask_word(actual_word)
                        st.rerun()

                else:
                    st.markdown(f"### 拼写提示: `{st.session_state['masked_current_word']}`")

                    with st.form(key=f"test_form_{current_idx}"):
                        user_input = st.text_input("补全单词:", key="word_input", autocomplete="off").strip()
                        submit = st.form_submit_button("提交答案")

                        if submit:
                            if user_input == "":
                                st.warning("请输入答案！")
                            else:
                                if user_input.lower() == actual_word.lower():
                                    st.session_state['word_passed'] = True
                                    record_study_result(current_word_data['id'], days_diff)
                                    st.rerun()
                                else:
                                    st.session_state['show_correction'] = True
                                    st.rerun()

            # 答对时的成功界面
            else:
                # 答对页单词发音
                c_succ_w, c_succ_sound = st.columns([8, 1])
                with c_succ_w:
                    st.success(f"✅ 回答正确！就是 **{actual_word}**")
                with c_succ_sound:
                    play_audio(actual_word)

                if current_word_data['example']:
                    # 答对页例句发音
                    c_succ_ex, c_succ_ex_sound = st.columns([12, 1])
                    with c_succ_ex:
                        st.write(f"**例句:** {current_word_data['example']}")
                        if current_word_data['example_cn']:
                            st.write(f"**翻译:** {current_word_data['example_cn']}")
                    with c_succ_ex_sound:
                        play_audio(current_word_data['example'])

                if st.button("➡️ 下一个", type="primary"):
                    if current_idx + 1 < total_words:
                        st.session_state['current_word_index'] += 1
                        st.session_state['masked_current_word'] = None
                        st.session_state['word_passed'] = False
                        st.session_state['show_correction'] = False
                    else:
                        st.session_state['test_completed'] = True
                    st.rerun()