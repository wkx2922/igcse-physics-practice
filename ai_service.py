import os
import json
import requests

# DeepSeek API - 从环境变量读取
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
API_URL = "https://api.deepseek.com/v1/chat/completions"

# 禁用日志功能（部署到云端时不需要）
LOG_FILE = None

def log(msg):
    """写入日志到文件"""
    pass  # 云端部署时禁用日志


def call_deepseek(prompt, retry=3):
    """调用 DeepSeek API"""
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are an IGCSE Physics tutor."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 2000
    }
    
    log(f"\n=== DeepSeek API Debug ===")
    log(f"URL: {API_URL}")
    log(f"Prompt length: {len(prompt)} chars")
    
    for attempt in range(retry):
        try:
            log(f"Attempt {attempt+1}/{retry} - Sending request (timeout=120s)...")
            response = requests.post(API_URL, headers=headers, json=data, timeout=120)
            
            log(f"Response status: {response.status_code}")
            log(f"Response text (first 300): {response.text[:300]}")
            
            if response.status_code == 200:
                result = response.json()
                if "choices" in result and result["choices"]:
                    log("✓ API call successful!")
                    return result["choices"][0]["message"]["content"]
                else:
                    log(f"✗ API response error: {result}")
                    raise Exception(f"API response error: {result}")
            elif response.status_code == 401:
                log("✗ Unauthorized - Invalid API key")
                raise Exception("API Error: Invalid API key")
            elif response.status_code == 429:
                log("✗ Rate limited - Too many requests")
                raise Exception("API Error: Rate limited")
            elif response.status_code == 500:
                log("✗ Server Error")
                raise Exception(f"API Server Error: {response.text[:100]}")
            else:
                log(f"✗ Unknown error: {response.status_code}")
                raise Exception(f"API Error {response.status_code}")
                
        except requests.exceptions.Timeout:
            log(f"✗ Attempt {attempt+1} TIMED OUT after 120 seconds")
            if attempt < retry - 1:
                log("Retrying in 5 seconds...")
                import time
                time.sleep(5)
                continue
            raise Exception("API request timed out")
        except requests.exceptions.ConnectionError as e:
            log(f"✗ CONNECTION ERROR: {str(e)[:200]}")
            if attempt < retry - 1:
                log("Retrying in 5 seconds...")
                import time
                time.sleep(5)
                continue
            raise Exception(f"Cannot connect to API server")
        except Exception as e:
            log(f"✗ Exception: {str(e)[:200]}")
            if attempt < retry - 1:
                log("Retrying in 5 seconds...")
                import time
                time.sleep(5)
                continue
            raise Exception(f"API call failed: {str(e)[:100]}")


def generate_report_local(answers, unit_name):
    """本地分析报告（不需要AI）"""
    correct = sum(1 for a in answers if a.get("correct"))
    total = len(answers)
    total_time = sum(a.get("time_spent", 0) for a in answers)
    avg_time = total_time / total if total > 0 else 0
    
    wrong = [a for a in answers if not a.get("correct")]
    slow = [a for a in answers if a.get("time_spent", 0) > avg_time * 1.5]
    
    report = f"""# 📊 Quiz Analysis Report for {unit_name}

## 🎯 Score Summary
- **Score:** {correct}/{total} ({100*correct//total}%)
- **Total Time:** {total_time:.1f}s
- **Average Time per Question:** {avg_time:.1f}s

"""
    
    # Time Analysis
    report += "## ⏱️ Time Analysis\n\n"
    if slow:
        report += "### Questions that took longer than average:\n"
        for i, q in enumerate(slow, 1):
            report += f"- Q{answers.index(q)+1}: {q.get('question', '')[:50]}... ({q.get('time_spent', 0):.1f}s)\n"
    else:
        report += "Great job managing your time well!\n"
    report += "\n"
    
    # Wrong Answers
    if wrong:
        report += f"## ❌ Wrong Answers Analysis ({len(wrong)} questions)\n\n"
        for i, q in enumerate(wrong, 1):
            report += f"### Question {i}\n"
            report += f"**Learning Objective:** {q.get('topic', 'N/A')}\n\n"
            report += f"**Your Answer:** {q.get('user_answer', '')}\n"
            report += f"**Correct Answer:** {q.get('answer', '')}\n\n"
            report += f"**Explanation:** {q.get('explanation', 'No explanation available')}\n\n"
            report += f"**Time Spent:** {q.get('time_spent', 0):.1f}s\n\n"
            report += "---\n\n"
    else:
        report += "## ❌ Wrong Answers\n\nPerfect score! Excellent work! 🎉\n\n"
    
    # Weak Topics
    if wrong:
        topic_stats = {}
        for q in wrong:
            t = q.get("topic", "Unknown")
            topic_stats[t] = topic_stats.get(t, 0) + 1
        
        report += "## 📚 Topics to Review\n\n"
        for topic, count in sorted(topic_stats.items(), key=lambda x: -x[1]):
            report += f"- **{topic}** ({count} mistake{'s' if count > 1 else ''})\n"
        report += "\n"
    
    # Recommendations
    report += "## 💡 Study Recommendations\n\n"
    if wrong:
        report += "1. Review the Learning Objectives listed above\n"
        report += "2. Focus on understanding the key concepts in those topics\n"
        report += "3. Practice more questions on your weak areas\n"
        report += "4. Use the 'Practice Weak Topics' button to focus on difficult concepts\n"
    else:
        report += "1. Keep practicing to maintain your knowledge\n"
        report += "2. Try more challenging questions in each unit\n"
    report += "\n"
    
    report += "## 🌟 Keep Up the Good Work!\n\n"
    report += "Remember: Practice makes perfect! Keep working on your weak areas and you'll continue to improve.\n"
    
    return report


def generate_report_ai(answers, unit_name):
    """AI分析报告 - 优先使用在线AI，失败则用本地"""
    try:
        return generate_report_ai_online(answers, unit_name)
    except Exception as e:
        log(f"AI failed: {e}")
        return generate_report_local(answers, unit_name)


def generate_report_ai_online(answers, unit_name):
    """在线AI分析报告"""
    correct = sum(1 for r in answers if r.get("correct"))
    total = len(answers)
    wrong = [r for r in answers if not r.get("correct")]
    total_time = sum(r.get("time_spent", 0) for r in answers)
    avg_time = total_time / total if total > 0 else 0
    
    # 构建题目详情
    questions_detail = []
    for r in answers:
        questions_detail.append({
            "question": r.get("question", "")[:100],
            "topic": r.get("topic", ""),
            "your_answer": r.get("user_answer", ""),
            "correct_answer": r.get("answer", ""),
            "is_correct": r.get("correct", False),
            "explanation": r.get("explanation", ""),
            "time_spent": round(r.get("time_spent", 0), 1)
        })
    
    prompt = f"""You are an IGCSE Physics tutor. Create a detailed analysis report for a student who just completed a quiz on "{unit_name}".

Quiz Results:
- Score: {correct}/{total} ({100*correct//total}%)
- Total time: {total_time:.1f}s (average {avg_time:.1f}s per question)

Questions:
{json.dumps(questions_detail, indent=2, ensure_ascii=False)}

Please provide a comprehensive analysis with:
1. Score summary
2. Time analysis (which questions were slow/fast)
3. Detailed wrong answer analysis with Learning Objectives
4. Weak topics identification
5. Study recommendations
6. Motivational closing

Use clear headings and be encouraging for a teenage student."""

    return call_deepseek(prompt)


def generate_quiz_ai(unit_name, topics, num=10):
    """使用 AI 生成选择题"""
    topic_list = "\n".join([f"- {t}" for t in topics[:5]])
    prompt = f"""You are an IGCSE Physics examiner. Generate {num} multiple-choice questions for "{unit_name}".

Topics:
{topic_list}

Requirements:
- 4 options (A-D), one correct
- Include explanation
- Return valid JSON array with keys: question, option_a, option_b, option_c, option_d, answer, explanation, topic"""

    try:
        response = call_deepseek(prompt)
        text = response.strip()
        
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        return json.loads(text.strip())
    except Exception as e:
        raise Exception(f"Failed to generate quiz: {str(e)}")


def generate_remedial_questions_ai(wrong_topics, num=5):
    """针对错题知识点生成补充练习"""
    topic_list = ", ".join(wrong_topics[:3])
    prompt = f"""Generate {num} IGCSE Physics questions on: {topic_list}.

Return JSON with: question, option_a, option_b, option_c, option_d, answer, explanation, topic"""

    try:
        response = call_deepseek(prompt)
        text = response.strip()
        
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        return json.loads(text.strip())
    except Exception as e:
        raise Exception(f"Failed to generate remedial questions: {str(e)}")
