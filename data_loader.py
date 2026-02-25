import pandas as pd
import os
import glob
import random

DATA_DIR = os.path.join(os.path.dirname(__file__), "题目")

UNIT_MAPPING = {
    "force and energy": "Motion, Forces & Energy",
    "thermal effect": "Thermal Physics",
    "wave and sound": "Waves",
    "electricity": "Electricity & Magnetism",
    "Magnet and current": "Electricity & Magnetism",
    "atom and radioactivity": "Nuclear Physics",
    "space physics": "Space Physics",
}

def _load_all_questions():
    all_questions = []
    for folder, unit_name in UNIT_MAPPING.items():
        patterns = [
            os.path.join(DATA_DIR, folder, "*.xlsx"),
            os.path.join(DATA_DIR, folder, "*.xls"),
        ]
        for pattern in patterns:
            files = glob.glob(pattern)
            for filepath in files:
                if "question_bank" in os.path.basename(filepath).lower():
                    df = pd.read_excel(filepath)
                    df = df.rename(columns={
                        'Unit Name': 'unit_name',
                        'Learning Objective': 'topic',
                        'Question': 'question',
                        'Option A': 'option_a',
                        'Option B': 'option_b',
                        'Option C': 'option_c',
                        'Option D': 'option_d',
                        'Answer': 'answer',
                        'Explanation': 'explanation'
                    })
                    df['unit'] = unit_name
                    all_questions.append(df)
                    break
    if not all_questions:
        raise FileNotFoundError("未找到任何题库文件！")
    return pd.concat(all_questions, ignore_index=True)

_QUESTIONS_DF = None

def get_questions_df():
    global _QUESTIONS_DF
    if _QUESTIONS_DF is None:
        _QUESTIONS_DF = _load_all_questions()
    return _QUESTIONS_DF

def get_units():
    df = get_questions_df()
    return sorted(df['unit'].unique().tolist())

def get_topics_for_unit(unit_name):
    df = get_questions_df()
    return df[df['unit'] == unit_name]['topic'].unique().tolist()

def get_quiz_questions(unit_name, num=10, topic_filter=None):
    df = get_questions_df()
    if unit_name:
        df = df[df['unit'] == unit_name]
    if topic_filter:
        df = df[df['topic'].isin(topic_filter)]
    if len(df) < num:
        num = len(df)
    return df.sample(n=num, random_state=None).to_dict('records')

def get_wrong_topic_questions(wrong_topics, num=10):
    df = get_questions_df()
    df = df[df['topic'].isin(wrong_topics)]
    if len(df) == 0:
        return []
    if len(df) < num:
        num = len(df)
    return df.sample(n=num, random_state=None).to_dict('records')
