import streamlit as st
import time
import random
import json
import base64
from auth import register, authenticate, validate_session, logout
import sqlite3
import os

# 导入自定义模块
from data_loader import get_units, get_topics_for_unit, get_quiz_questions, get_questions_df
from db import save_quiz_record
from ai_service import generate_report_ai, generate_remedial_questions_ai

st.set_page_config(page_title="IGCSE Physics Practice", page_icon="⚛️", layout="wide")

# JavaScript to handle token in localStorage
st.markdown("""
<script>
function getToken() {
    return localStorage.getItem('igcse_token');
}
function setToken(token) {
    localStorage.setItem('igcse_token', token);
}
function clearToken() {
    localStorage.removeItem('igcse_token');
}
</script>
""", unsafe_allow_html=True)

# 检查 localStorage 中的 token（通过 JavaScript）
def get_token_from_browser():
    """获取浏览器 localStorage 中的 token"""
    return None  # Streamlit 无法直接读取 localStorage，这个功能需要额外处理

# 检查 URL 参数中的 token 并验证
def check_session_from_url():
    """从 URL 参数检查会话和页面状态"""
    try:
        query_params = st.query_params
        if not query_params:
            return False
        
        # 验证 token
        token = query_params.get("token")
        if token:
            # 先设置 token
            st.session_state.token = token
            
            # 验证 token 是否有效
            if not st.session_state.get("logged_in"):
                is_valid, user_id, username = validate_session(token)
                if is_valid:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.user_id = user_id
                    
                    # 恢复页面状态 - 使用 page_status
                    page_status = query_params.get("page_status")
                    if page_status in ["home", "quiz_setup", "quiz", "result"]:
                        st.session_state.page = page_status
                        st.session_state.page_status = page_status
                    else:
                        st.session_state.page = "home"
                        st.session_state.page_status = "home"
                    
                    unit = query_params.get("unit")
                    if unit:
                        st.session_state.selected_unit = unit
                    
                    # 恢复答题结果
                    answers_b64 = query_params.get("answers")
                    if answers_b64:
                        try:
                            answers_json = base64.b64decode(answers_b64.encode()).decode()
                            simplified_answers = json.loads(answers_json)
                            # 还原为完整格式
                            answers = []
                            for a in simplified_answers:
                                answers.append({
                                    "question": a.get("q", ""),
                                    "topic": a.get("t", ""),
                                    "user_answer": a.get("ua", ""),
                                    "answer": a.get("a", ""),
                                    "correct": a.get("c", 0) == 1,
                                    "explanation": a.get("e", ""),
                                    "time_spent": a.get("ts", 0)
                                })
                            st.session_state.answers = answers
                        except:
                            pass
                    
                    # 恢复 start_time
                    start_time = query_params.get("start_time")
                    if start_time:
                        try:
                            st.session_state.start_time = float(start_time)
                        except:
                            pass
                    
                    # 恢复错题知识点
                    wrong_topics_b64 = query_params.get("wrong_topics")
                    if wrong_topics_b64:
                        try:
                            wrong_topics_json = base64.b64decode(wrong_topics_b64.encode()).decode()
                            st.session_state.wrong_topics = json.loads(wrong_topics_json)
                        except:
                            pass
                    
                    return True
                else:
                    st.session_state.token = None
                    st.query_params.clear()
        else:
            st.session_state.page = "home"
            st.session_state.page_status = "home"
    except Exception as e:
        print(f"Error checking session: {e}")
        st.session_state.page = "home"
        st.session_state.page_status = "home"
    return False


def save_state_to_url():
    """将当前状态保存到 URL 参数"""
    params = {}
    
    # 保存登录 token
    if st.session_state.get("token"):
        params["token"] = st.session_state.token
    
    # 保存当前页面状态
    if st.session_state.get("page_status"):
        params["page_status"] = st.session_state.page_status
    elif st.session_state.get("page"):
        params["page_status"] = st.session_state.page
    
    # 保存当前单元
    if st.session_state.get("selected_unit"):
        params["unit"] = st.session_state.selected_unit
    
    # 保存答题结果（如果是在结果页）
    answers = st.session_state.get("answers", [])
    if answers:
        # 只保存关键信息，减小数据量
        simplified_answers = []
        for a in answers:
            simplified_answers.append({
                "q": a.get("question", "")[:100],  # 题目简略
                "t": a.get("topic", ""),
                "ua": a.get("user_answer", ""),
                "a": a.get("answer", ""),
                "c": 1 if a.get("correct") else 0,
                "e": a.get("explanation", "")[:200],  # 解析简略
                "ts": round(a.get("time_spent", 0), 1)
            })
        try:
            answers_json = json.dumps(simplified_answers, ensure_ascii=False)
            answers_b64 = base64.b64encode(answers_json.encode()).decode()
            params["answers"] = answers_b64
        except:
            pass
    
    # 保存 start_time
    if st.session_state.get("start_time"):
        params["start_time"] = str(st.session_state.start_time)
    
    # 保存错题知识点
    wrong_topics = st.session_state.get("wrong_topics", [])
    if wrong_topics:
        params["wrong_topics"] = base64.b64encode(json.dumps(wrong_topics).encode()).decode()
    
    # 更新 URL 参数
    if params:
        try:
            st.query_params.update(params)
        except:
            pass

# 页面状态初始化
def init_session_state():
    if "page" not in st.session_state:
        st.session_state.page = "home"
    if "page_status" not in st.session_state:
        st.session_state.page_status = "home"  # 用于持久化页面状态
    if "previous_page" not in st.session_state:
        st.session_state.previous_page = None
    if "quiz_data" not in st.session_state:
        st.session_state.quiz_data = []
    if "current_q" not in st.session_state:
        st.session_state.current_q = 0
    if "answers" not in st.session_state:
        st.session_state.answers = []
    if "start_time" not in st.session_state:
        st.session_state.start_time = None
    if "q_start_time" not in st.session_state:
        st.session_state.q_start_time = None
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "selected_unit" not in st.session_state:
        st.session_state.selected_unit = None
    if "wrong_topics" not in st.session_state:
        st.session_state.wrong_topics = []
    if "ai_report" not in st.session_state:
        st.session_state.ai_report = None
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "username" not in st.session_state:
        st.session_state.username = ""
    if "token" not in st.session_state:
        st.session_state.token = None

def navigate_to(page_name):
    """导航到指定页面并记录上一页面"""
    st.session_state.previous_page = st.session_state.page
    st.session_state.page = page_name
    st.session_state.page_status = page_name
    # 保存所有状态到 URL
    save_state_to_url()
    st.rerun()

def go_back():
    """返回上一页面"""
    if st.session_state.previous_page:
        st.session_state.page = st.session_state.previous_page
        st.session_state.page_status = st.session_state.previous_page
        st.session_state.previous_page = None
    else:
        st.session_state.page = "home"
        st.session_state.page_status = "home"
    # 保存所有状态到 URL
    save_state_to_url()
    st.rerun()

# 初始化
init_session_state()

# 检查会话（仅在未登录时）
if not st.session_state.logged_in:
    check_session_from_url()

# 颜色配置
UNIT_COLORS = {
    "Motion, Forces & Energy": "#FF6B6B",
    "Thermal Physics": "#FFA94D",
    "Waves": "#2ECC71",
    "Electricity & Magnetism": "#339AF0",
    "Nuclear Physics": "#845EF7",
    "Space Physics": "#F06595",
}
UNIT_ICONS = {
    "Motion, Forces & Energy": "🚀",
    "Thermal Physics": "🔥",
    "Waves": "🌊",
    "Electricity & Magnetism": "⚡",
    "Nuclear Physics": "☢️",
    "Space Physics": "🪐",
}


def get_user_id(username):
    conn = sqlite3.connect("users.db")
    cursor = conn.execute("SELECT id FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def render_home_page():
    """首页 - 单元选择"""
    st.title("⚛️ IGCSE Physics Practice")
    st.markdown(f"Welcome **{st.session_state.username}**! Choose a unit to start:")
    st.divider()
    
    units = get_units()
    available_units = [(UNIT_ICONS.get(u, "📚"), u, UNIT_COLORS.get(u, "#666")) for u in units]
    
    cols = st.columns(3)
    for idx, (icon, name, color) in enumerate(available_units):
        with cols[idx % 3]:
            card_html = f"""
            <div style="
                background: {color};
                border-radius: 16px;
                padding: 24px 12px;
                text-align: center;
                color: white;
                cursor: pointer;
                margin-bottom: 12px;
            ">
                <div style="font-size: 42px; margin-bottom: 8px;">{icon}</div>
                <div style="font-size: 16px; font-weight: 700;">{name}</div>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)
            
            if st.button(f"Select {name}", key=f"unit_{idx}", use_container_width=True):
                st.session_state.selected_unit = name
                navigate_to("quiz_setup")
                st.rerun()


def render_quiz_setup_page():
    """答题设置页面 - 选择知识点"""
    unit = st.session_state.selected_unit
    
    if st.button("⬅️ Back to Unit Selection", key="back_to_units"):
        navigate_to("home")
    
    st.title(f"{UNIT_ICONS.get(unit, '📚')} {unit}")
    st.markdown("Choose topics to practice:")
    
    topics = get_topics_for_unit(unit)
    
    # 全选按钮
    col1, col2 = st.columns([1, 4])
    with col1:
        select_all = st.checkbox("Select All", value=True, key="select_all_topics")
    
    if select_all:
        selected_topics = topics
    else:
        selected_topics = st.multiselect("Select topics:", topics, default=topics[:3])
    
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        num_questions = st.slider("Number of questions", 1, 20, 10)
    with col2:
        st.write(f"Available: {len(topics)} topics, sufficient questions")
    
    if st.button("🎯 Start Quiz", type="primary", use_container_width=True):
        if selected_topics:
            questions = get_quiz_questions(unit, num_questions, selected_topics)
            if questions:
                st.session_state.quiz_data = questions
                st.session_state.current_q = 0
                st.session_state.answers = []
                st.session_state.wrong_topics = []
                st.session_state.start_time = time.time()
                st.session_state.q_start_time = time.time()
                st.session_state.ai_report = None
                navigate_to("quiz")
            else:
                st.error("No questions available for selected topics!")
        else:
            st.error("Please select at least one topic!")


def render_quiz_page():
    """答题页面"""
    questions = st.session_state.quiz_data
    current = st.session_state.current_q
    q = questions[current]
    
    # 进度条
    progress = (current + 1) / len(questions)
    st.progress(progress)
    st.markdown(f"**Question {current + 1} of {len(questions)}**")
    
    # 计时
    elapsed = time.time() - st.session_state.q_start_time
    st.markdown(f"⏱️ Time on this question: {elapsed:.1f}s")
    
    st.divider()
    
    # 题目显示
    st.subheader(q.get("question", ""))
    
    options = {
        "A": q.get("option_a", ""),
        "B": q.get("option_b", ""),
        "C": q.get("option_c", ""),
        "D": q.get("option_d", ""),
    }
    
    # 选项显示
    option_labels = []
    for key, val in options.items():
        option_labels.append(f"**{key}.** {val}")
    
    user_answer = st.radio("Choose your answer:", option_labels, key=f"q_{current}")
    
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⏭️ Next Question", type="primary", use_container_width=True):
            # 记录答案
            selected_key = user_answer.split(".")[0].strip("*").strip()
            is_correct = selected_key == q.get("answer", "").upper()
            
            # 记录到数据库
            user_id = st.session_state.user_id
            if user_id:
                save_quiz_record(
                    user_id, st.session_state.username,
                    st.session_state.selected_unit,
                    q.get("question", ""), q.get("topic", ""),
                    selected_key, q.get("answer", ""), is_correct, elapsed
                )
            
            # 记录答案
            st.session_state.answers.append({
                "question": q.get("question", ""),
                "topic": q.get("topic", ""),
                "user_answer": selected_key,
                "answer": q.get("answer", ""),
                "correct": is_correct,
                "explanation": q.get("explanation", ""),
                "time_spent": elapsed
            })
            
            # 记录错题知识点
            if not is_correct:
                st.session_state.wrong_topics.append(q.get("topic", ""))
            
            # 下一题或结束
            if current + 1 >= len(questions):
                navigate_to("result")
            else:
                st.session_state.current_q += 1
                st.session_state.q_start_time = time.time()
            st.rerun()
    
    with col2:
        if st.button("🏁 End Quiz", use_container_width=True):
            navigate_to("result")


def render_result_page():
    """结果页面"""
    st.title("📊 Quiz Complete!")
    
    # 检查是否有答题数据
    answers = st.session_state.get("answers", [])
    if not answers:
        st.warning("No quiz data found. Please start a new quiz.")
        if st.button("Start New Quiz"):
            navigate_to("home")
        return
    
    correct = sum(1 for a in answers if a.get("correct", False))
    total = len(answers)
    
    # 确保 start_time 不为 None
    if st.session_state.start_time is not None:
        total_time = time.time() - st.session_state.start_time
    else:
        total_time = 0
    
    avg_time = total_time / total if total > 0 else 0
    
    # 统计显示
    score_percent = f"{100*correct//total}%" if total > 0 else "0%"
    st.markdown(f"### 🎯 Score: {correct}/{total} ({score_percent})")
    st.markdown(f"⏱️ Total time: {total_time:.1f}s (avg {avg_time:.1f}s per question)")
    
    st.divider()
    
    # 所有题目的详细解析
    st.subheader("📝 Question Review")
    for i, ans in enumerate(answers, 1):
        is_correct = ans.get("correct", False)
        status = "✅" if is_correct else "❌"
        with st.expander(f"{status} Question {i}: {ans.get('question', '')[:60]}..."):
            st.markdown(f"**📚 Learning Objective:** {ans.get('topic', 'N/A')}")
            st.markdown(f"**Your answer:** {ans.get('user_answer', '')}")
            if not is_correct:
                st.markdown(f"**✅ Correct answer:** {ans.get('answer', '')}")
            st.markdown(f"**📖 Explanation:** {ans.get('explanation', 'No explanation available')}")
            st.markdown(f"**⏱️ Time spent:** {ans.get('time_spent', 0):.1f}s")
    
    st.divider()
    
    # 错题详情（简化版）
    wrong_answers = [a for a in answers if not a.get("correct", False)]
    
    if wrong_answers:
        st.subheader(f"❌ Wrong Answers Summary ({len(wrong_answers)}):")
        for i, wa in enumerate(wrong_answers, 1):
            st.markdown(f"**Q{i}:** {wa.get('question', '')[:80]}...")
            st.markdown(f"   📚 Topic: {wa.get('topic', 'N/A')}")
            st.markdown(f"   ❌ Your answer: {wa.get('user_answer', '')} | ✅ Correct: {wa.get('answer', '')}")
            st.markdown(f"   📖 Explanation: {wa.get('explanation', 'N/A')}")
            st.markdown("---")
    else:
        st.success("🎉 Perfect score! Great job!")
    
    st.divider()
    
    # AI 分析报告
    st.subheader("🤖 Analysis Report")
    
    # 检查是否已有报告
    if st.session_state.get("ai_report"):
        st.markdown(st.session_state.ai_report)
        if st.button("🔄 Regenerate Report"):
            st.session_state.ai_report = None
            st.rerun()
    else:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🤖 Generate AI Analysis", use_container_width=True):
                try:
                    with st.spinner("🤖 Generating AI analysis..."):
                        report = generate_report_ai(answers, st.session_state.selected_unit)
                        st.session_state.ai_report = report
                        st.rerun()
                except Exception as e:
                    st.error(f"AI unavailable: {str(e)[:80]}")
                    # 自动显示本地分析
                    try:
                        from ai_service import generate_report_local
                        report = generate_report_local(answers, st.session_state.selected_unit)
                        st.session_state.ai_report = report
                        st.rerun()
                    except:
                        pass
        
        with col2:
            if st.button("📊 Show Local Analysis", use_container_width=True):
                try:
                    from ai_service import generate_report_local
                    report = generate_report_local(answers, st.session_state.selected_unit)
                    st.session_state.ai_report = report
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")
    
    st.divider()
    
    # 操作按钮
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔄 New Quiz (Same Unit)", use_container_width=True):
            navigate_to("quiz_setup")
    with col2:
        wrong_topics = list(set(st.session_state.wrong_topics))
        if wrong_topics and st.button("🎯 Practice Weak Topics", use_container_width=True):
            # 生成错题知识点练习
            from data_loader import get_wrong_topic_questions
            new_questions = get_wrong_topic_questions(wrong_topics, 10)
            if new_questions:
                st.session_state.quiz_data = new_questions
                st.session_state.current_q = 0
                st.session_state.answers = []
                st.session_state.wrong_topics = []
                st.session_state.start_time = time.time()
                st.session_state.q_start_time = time.time()
                st.session_state.ai_report = None
                navigate_to("quiz")
            else:
                st.error("No more questions for these topics!")
    with col3:
        if st.button("⬅️ Go Back", use_container_width=True):
            go_back()


# ==================== 主程序 ====================

# 侧边栏
with st.sidebar:
    if st.session_state.logged_in:
        st.success(f"Welcome, **{st.session_state.username}** 👋")
        if st.button("Logout", use_container_width=True):
            # 清除服务器端会话
            if st.session_state.get("token"):
                logout(st.session_state.token)
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.user_id = None
            st.session_state.token = None
            st.session_state.page = "home"
            # 清除 URL 参数
            try:
                st.query_params.clear()
            except:
                pass
            st.rerun()
    else:
        st.header("⚛️ IGCSE Physics")
        tab_login, tab_register = st.tabs(["Login", "Register"])
        
        with tab_login:
            login_user = st.text_input("Username", key="login_user")
            login_pass = st.text_input("Password", type="password", key="login_pass")
            if st.button("Login", use_container_width=True):
                ok, msg, token = authenticate(login_user, login_pass)
                if ok:
                    st.session_state.logged_in = True
                    st.session_state.username = login_user
                    st.session_state.user_id = get_user_id(login_user)
                    st.session_state.token = token
                    # 保存登录状态和当前页面到 URL
                    try:
                        st.query_params["token"] = token
                        st.query_params["page_status"] = st.session_state.page_status or st.session_state.page
                        if st.session_state.selected_unit:
                            st.query_params["unit"] = st.session_state.selected_unit
                    except:
                        pass
                    st.rerun()
                else:
                    st.error(msg)
        
        with tab_register:
            reg_user = st.text_input("Username", key="reg_user")
            reg_pass = st.text_input("Password", type="password", key="reg_pass")
            reg_pass2 = st.text_input("Confirm Password", type="password", key="reg_pass2")
            if st.button("Register", use_container_width=True):
                if reg_pass != reg_pass2:
                    st.error("Passwords don't match!")
                else:
                    ok, msg = register(reg_user, reg_pass)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)
                        st.error(msg)

# 主内容
if not st.session_state.logged_in:
    st.title("⚛️ IGCSE Physics Practice")
    st.info("👈 Please **Login** or **Register** from the sidebar to start practicing")
    st.stop()

# 根据页面状态渲染
# 如果是结果页但没有答题数据，跳转到首页
if st.session_state.page == "result" and not st.session_state.get("answers"):
    st.session_state.page = "home"
    st.session_state.page_status = "home"

if st.session_state.page == "home":
    render_home_page()
elif st.session_state.page == "quiz_setup":
    render_quiz_setup_page()
elif st.session_state.page == "quiz":
    render_quiz_page()
elif st.session_state.page == "result":
    render_result_page()
