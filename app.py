import html
import json
import os
import random
import base64
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

import streamlit as st


st.set_page_config(
    page_title="Virtual Agora",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def render_scroll_to_top() -> None:
    """Keep the screen transition hook without injecting a deprecated iframe."""
    return None


def go_to_screen(screen_name: str, **kwargs) -> None:
    previous_screen = st.session_state.get("screen")
    history = st.session_state.get("screen_history", [])
    if previous_screen and previous_screen != screen_name:
        history.append(previous_screen)
        if len(history) > 12:
            history = history[-12:]
    st.session_state.screen_history = history
    st.session_state.screen = screen_name
    for key, value in kwargs.items():
        st.session_state[key] = value
    st.rerun()


def go_back_screen(default_screen: str = "landing") -> None:
    history = st.session_state.get("screen_history", [])
    if history:
        previous_screen = history.pop()
        st.session_state.screen_history = history
        st.session_state.screen = previous_screen
    else:
        st.session_state.screen = default_screen
    st.rerun()


def reset_mentor_state() -> None:
    st.session_state.update(
        {
            "mentor_index": 0,
            "mentor_scores": {axis: 0 for axis in MENTOR_AXES},
            "mentor_answer_history": [],
            "mentor_insight": "",
        }
    )


def go_home(default_screen: str = "landing") -> None:
    st.session_state.screen_history = []
    st.session_state.screen = default_screen
    st.rerun()


def render_topbar() -> None:
    """Render a quiet brand strip without competing navigation controls."""
    st.markdown(
        '<div class="app-topbar"><div class="app-topbar-brand">VIRTUAL AGORA <span>· 질문의 광장</span></div>'
        '<div class="app-topbar-note">과거의 시선으로 오늘을 다시 보기</div></div>',
        unsafe_allow_html=True,
    )


MENTOR_PEOPLE = [
    "이순신",
    "세종대왕",
    "소크라테스",
    "스티브 잡스",
    "공자",
    "예수",
    "부처",
    "니체",
    "나폴레옹",
    "징기스칸",
    "체 게바라",
    "알렉산더 대왕",
    "정약용",
    "아리스토텔레스",
    "조조",
    "에이브러햄 링컨",
    "알베르트 아인슈타인",
    "레오나르도 다빈치",
    "니콜라 테슬라",
    "디오게네스",
    "윈스턴 처칠",
    "노자",
    "장자",
    "아르투어 쇼펜하우어",
    "헬렌 켈러",
    "마하트마 간디",
    "알베르트 슈바이처",
    "테레사 수녀",
    "유비",
    "율리우스 카이사르",
]
PEOPLE = [
    "이순신",
    "세종대왕",
    "소크라테스",
    "스티브 잡스",
    "공자",
    "예수",
    "부처",
    "니체",
    "아르투어 쇼펜하우어",
]

MENTOR_AXES = ("Action", "Reflection", "Innovation", "Order", "Logic", "Empathy", "Mastery", "Acceptance")

MENTOR_QUESTIONS = [
    {
        "prompt": "갑자기 문제가 생기면, 나는 보통 어떻게 대응하나요?",
        "a": ("바로 움직여 해결하려고 한다.", {"Action": 2, "Mastery": 1}),
        "b": ("먼저 상황을 차분히 정리한다.", {"Reflection": 2, "Acceptance": 1}),
    },
    {
        "prompt": "사람을 비판할 때, 나는 보통 어떻게 하나요?",
        "a": ("잘못된 점을 바로잡아야 한다고 본다.", {"Logic": 2, "Order": 1}),
        "b": ("상대의 감정과 맥락부터 이해하려 한다.", {"Empathy": 2, "Acceptance": 1}),
    },
    {
        "prompt": "중요한 선택을 할 때 가장 먼저 고려하는 것은 무엇인가요?",
        "a": ("결과를 더 크게 만들 수 있는가.", {"Innovation": 2, "Action": 1}),
        "b": ("안정적으로 오래 이어 갈 수 있는가.", {"Order": 2, "Acceptance": 1}),
    },
    {
        "prompt": "힘든 일이 생겼을 때, 나는 보통 어떻게 하나요?",
        "a": ("행동에 집중하며 이겨내려 한다.", {"Action": 2, "Mastery": 1}),
        "b": ("잠깐 멈춰 생각을 정리한다.", {"Reflection": 2, "Acceptance": 1}),
    },
    {
        "prompt": "새로운 아이디어가 떠오르면, 나는 보통 어떻게 하나요?",
        "a": ("일단 시도해 보는 편이다.", {"Innovation": 2, "Action": 1}),
        "b": ("원리를 먼저 검토한 뒤 준비한다.", {"Logic": 2, "Order": 1}),
    },
    {
        "prompt": "팀에서 갈등이 생기면, 나는 보통 어떻게 하나요?",
        "a": ("결론을 빠르게 내리고 방향을 정한다.", {"Logic": 2, "Mastery": 1}),
        "b": ("모두가 납득할 수 있도록 조율한다.", {"Empathy": 2, "Order": 1}),
    },
    {
        "prompt": "내가 가장 존경하는 리더는 어떤 사람인가요?",
        "a": ("결단력 있고 목표를 끝까지 추진하는 사람.", {"Action": 2, "Mastery": 1}),
        "b": ("사람을 잘 챙기고 함께 성장시키는 사람.", {"Empathy": 2, "Acceptance": 1}),
    },
    {
        "prompt": "평소 나는 어떤 방식으로 행동하나요?",
        "a": ("한 번 시작하면 끝까지 밀고 간다.", {"Mastery": 2, "Action": 1}),
        "b": ("상황을 보며 유연하게 조율한다.", {"Reflection": 2, "Order": 1}),
    },
    {
        "prompt": "실패를 경험했을 때, 나는 보통 어떻게 하나요?",
        "a": ("무엇을 배웠는지 바로 정리한다.", {"Logic": 2, "Reflection": 1}),
        "b": ("속상해도 다시 일어나는 데 집중한다.", {"Acceptance": 2, "Mastery": 1}),
    },
    {
        "prompt": "내가 삶에서 가장 중요하게 여기는 기준은 무엇인가요?",
        "a": ("성장과 성취.", {"Mastery": 2, "Innovation": 1}),
        "b": ("사람들과의 관계와 유대감.", {"Empathy": 2, "Acceptance": 1}),
    },
    {
        "prompt": "복잡한 문제를 마주하면, 나는 보통 어떻게 접근하나요?",
        "a": ("직관으로 핵심을 찾는다.", {"Innovation": 2, "Logic": 1}),
        "b": ("원리와 논리를 단계별로 나누어 살핀다.", {"Logic": 2, "Order": 1}),
    },
    {
        "prompt": "삶에서 가장 중요한 것은 무엇이라고 생각하나요?",
        "a": ("나만의 길을 만드는 것.", {"Innovation": 2, "Action": 1}),
        "b": ("내가 누구인지 깊이 아는 것.", {"Reflection": 2, "Acceptance": 1}),
    },
]


def _mentor_vector(**values: int) -> dict[str, int]:
    return {axis: values.get(axis, 0) for axis in MENTOR_AXES}


# "잘 모르겠다"는 단순한 비답이 아니라, 판단을 미루고 불확실성을 인정하는 인식적 유연성을 의미합니다.
# 심리학적으로는 인지적 유연성·지식의 한계 인식, 역사적으로는 소크라테스의 무지의 인식,
# 철학적으로는 불교의 중도와 아리스토텔레스의 중용, 유교의 겸손과 반성에 가깝습니다.
NEUTRAL_RESPONSE_WEIGHTS = {
    "Reflection": 2,
    "Acceptance": 2,
    "Logic": 1,
    "Empathy": 1,
}


def apply_question_response(current_scores: dict[str, int], question: dict[str, object], response: str) -> dict[str, int]:
    """Apply a selected answer, including a neutral response that reflects humility and ambiguity tolerance."""
    scores = dict(current_scores)
    if response == "neutral":
        for axis, weight in NEUTRAL_RESPONSE_WEIGHTS.items():
            scores[axis] = scores.get(axis, 0) + weight
        return scores
    if response not in {"a", "b"}:
        return scores
    for axis, weight in question[response][1].items():
        scores[axis] = scores.get(axis, 0) + weight
    return scores


MENTOR_GROUPS = {
    "결단/개척형": ("용기 · 혁신 · 정면승부", ["이순신", "스티브 잡스", "나폴레옹", "징기스칸", "체 게바라", "알렉산더 대왕"], _mentor_vector(Action=10, Reflection=2, Innovation=9, Order=3, Logic=7, Empathy=2, Mastery=9, Acceptance=2)),
    "원칙/시스템형": ("책임 · 질서 · 혜안", ["세종대왕", "공자", "정약용", "아리스토텔레스", "조조", "에이브러햄 링컨"], _mentor_vector(Action=6, Reflection=6, Innovation=5, Order=10, Logic=8, Empathy=7, Mastery=7, Acceptance=4)),
    "통찰/질문형": ("질문 · 비전 · 직관", ["소크라테스", "알베르트 아인슈타인", "레오나르도 다빈치", "니콜라 테슬라", "디오게네스", "니체", "윈스턴 처칠"], _mentor_vector(Action=6, Reflection=8, Innovation=10, Order=4, Logic=10, Empathy=4, Mastery=6, Acceptance=4)),
    "전략/권력형": ("판세 · 설득 · 결단", ["율리우스 카이사르"], _mentor_vector(Action=9, Reflection=4, Innovation=5, Order=6, Logic=10, Empathy=3, Mastery=9, Acceptance=3)),
    "해탈/관조형": ("중도 · 수용 · 내면의 평정", ["노자", "장자", "부처", "아르투어 쇼펜하우어", "헬렌 켈러"], _mentor_vector(Action=3, Reflection=10, Innovation=4, Order=3, Logic=6, Empathy=7, Mastery=5, Acceptance=10)),
    "자비/연대형": ("사랑 · 용서 · 공감", ["예수", "마하트마 간디", "알베르트 슈바이처", "테레사 수녀", "유비"], _mentor_vector(Action=4, Reflection=6, Innovation=3, Order=7, Logic=4, Empathy=10, Mastery=4, Acceptance=9)),
}

PERSONA_SIGNATURES = {
    "이순신": {"Action": 2, "Order": 2, "Mastery": 2},
    "세종대왕": {"Order": 3, "Logic": 2, "Empathy": 2},
    "소크라테스": {"Reflection": 3, "Logic": 2, "Empathy": 1},
    "스티브 잡스": {"Innovation": 3, "Action": 2, "Mastery": 1},
    "공자": {"Order": 2, "Empathy": 2, "Logic": 1},
    "예수": {"Empathy": 3, "Acceptance": 2, "Reflection": 1},
    "부처": {"Reflection": 3, "Acceptance": 3, "Empathy": 1},
    "니체": {"Mastery": 3, "Innovation": 2, "Action": 1},
    "나폴레옹": {"Action": 3, "Mastery": 2, "Logic": 1},
    "징기스칸": {"Action": 2, "Innovation": 2, "Mastery": 2},
    "체 게바라": {"Action": 3, "Empathy": 2, "Innovation": 2},
    "알렉산더 대왕": {"Action": 2, "Innovation": 2, "Mastery": 1},
    "정약용": {"Logic": 3, "Order": 2, "Innovation": 1},
    "아리스토텔레스": {"Logic": 3, "Order": 2, "Reflection": 1},
    "조조": {"Logic": 2, "Order": 2, "Mastery": 2},
    "에이브러햄 링컨": {"Empathy": 2, "Logic": 2, "Acceptance": 1},
    "알베르트 아인슈타인": {"Innovation": 3, "Reflection": 2, "Logic": 1},
    "레오나르도 다빈치": {"Innovation": 3, "Reflection": 2, "Empathy": 1},
    "니콜라 테슬라": {"Innovation": 3, "Logic": 2, "Mastery": 1},
    "디오게네스": {"Logic": 2, "Reflection": 2, "Acceptance": 1},
    "윈스턴 처칠": {"Action": 2, "Order": 2, "Empathy": 1},
    "노자": {"Reflection": 3, "Acceptance": 3, "Order": 1},
    "장자": {"Reflection": 2, "Acceptance": 2, "Innovation": 1},
    "아르투어 쇼펜하우어": {"Reflection": 3, "Logic": 2, "Acceptance": 1},
    "헬렌 켈러": {"Mastery": 2, "Acceptance": 2, "Empathy": 2},
    "마하트마 간디": {"Acceptance": 3, "Empathy": 2, "Action": 1},
    "알베르트 슈바이처": {"Reflection": 2, "Empathy": 2, "Logic": 1},
    "테레사 수녀": {"Empathy": 3, "Acceptance": 2, "Reflection": 1},
    "유비": {"Empathy": 3, "Order": 1, "Acceptance": 1},
    "율리우스 카이사르": {"Action": 2, "Logic": 2, "Mastery": 2},
}


PERSONA_VECTORS = {}
for _, (_, people, base_vector) in MENTOR_GROUPS.items():
    for person in people:
        vector = {axis: value for axis, value in base_vector.items()}
        for axis, delta in PERSONA_SIGNATURES.get(person, {}).items():
            vector[axis] = min(10, max(0, vector.get(axis, 0) + delta))
        PERSONA_VECTORS[person] = vector

MENTOR_DETAILED_PROFILES = {
    "이순신": {"mtype": "ISTJ-리더십", "strengths": ["책임감", "전략적 사고", "절제"], "blind_spot": "완벽주의로 인한 지체", "era": "조선 중기 (1545–1598)", "element": "물"},
    "스티브 잡스": {"mtype": "ENFJ-발명가", "strengths": ["미적 직관", "극단적 집중", "스토리텔링"], "blind_spot": "완벽주의와 내면 갈등", "era": "현대 미국 (1955–2011)", "element": "불"},
    "나폴레옹": {"mtype": "ENTJ-전략가", "strengths": ["전략적 사고", "도시적 리더십", "결단력"], "blind_spot": "야심과 오버플렉스", "era": "프랑스 혁명기 (1769–1821)", "element": "전기"},
    "징기스칸": {"mtype": "ESTP-정복자", "strengths": ["기습적 급진변화", "용기", "속도감"], "blind_spot": "포악함과 불안정", "era": "몽골 제국 건국기 (1162–1227)", "element": "바람"},
    "체 게바라": {"mtype": "ENFJ-투사자", "strengths": ["이상주의적 헌신", " 설득력", " 급진적 실천"], "blind_spot": "극단적 타협과 분노", "era": "쿠바 혁명기 (1928–1967)", "element": "화재"},
    "알렉산더 대왕": {"mtype": "ESTJ-지배자", "strengths": ["통솔력", "문화적 융합", " 용기"], "blind_spot": "지나친 욕심과 불안정", "era": "고대 그리스-막 (356–323 BC)", "element": "철"},
    "세종대왕": {"mtype": "INFJ-사상가", "strengths": ["장기적 비전", " 백성을 위한 사랑", " 체계적 사고"], "blind_spot": "완벽주의로 인한 지체", "era": "조선 중기 (1397–1450)", "element": "물"},
    "공자": {"mtype": "ISTJ-교육자", "strengths": ["윤리적 기준", " 교육적 섬세함", " 관계 중심"], "blind_spot": "보수주의적 사고", "era": "춘추시대 (551–479 BC)", "element": "목"},
    "정약용": {"mtype": "INTJ-발명가", "strengths": ["실용적 사고", " 독립적 통찰", " 제도 개혁"], "blind_spot": "과도한 비판과 냉정함", "era": "조선 후기 (1762–1836)", "element": "토"},
    "아리스토텔레스": {"mtype": "INTJ-철학자", "strengths": ["논리적 체계화", " 관측적 사고", " 윤리적 균형"], "blind_spot": "이성적 냉간화", "era": "고대 그리스 (384–322 BC)", "element": "공기"},
    "조조": {"mtype": "ENTJ-전략가", "strengths": ["실용적 리더십", " 능력 중심", " 위기 극복"], "blind_spot": "인물 사용과 계산적 배신", "era": "후한 말 (181–220)", "element": "총"},
    "에이브러햄 링컨": {"mtype": "INFJ-사상가", "strengths": ["도덕적 용기", " 연민", " 끈끈한 인내"], "blind_spot": "우울과 과도한 책임감", "era": "미국 (1809–1865)", "element": "나무"},
    "소크라테스": {"mtype": "ENFJ-철학자", "strengths": ["질문 기술", " 자기 성찰", " 윤리적 탐구"], "blind_spot": "자기 확신 부족과 회의주의", "era": "고대 아테네 (470–399 BC)", "element": "불"},
    "알베르트 아인슈타인": {"mtype": "INFP-사상가", "strengths": ["상상력", " 독립적 사고", " 물리적 직관"], "blind_spot": "실용성 무시와 관계 어려움", "era": "현대 유럽 (1879–1955)", "element": "별"},
    "레오나르도 다빈치": {"mtype": "ENFP-발명가", "strengths": ["다학문적 통찰", " 호기심", " 예술적 표현"], "blind_spot": "미루기와 완성도 어려움", "era": "르네상스 (1452–1519)", "element": "공기"},
    "니콜라 테슬라": {"mtype": "INTJ-발명가", "strengths": ["미래지향적 사고", " 발명적 창조", " 집중력"], "blind_spot": "현실감 없는 이상주의와 OCD", "era": "현대 미국/유럽 (1856–1943)", "element": "번개"},
    "디오게네스": {"mtype": "ENTP-사상가", "strengths": ["급진적 비판", " 자유로운 사고", " 실용적 해석"], "blind_spot": "지나친 급진주의와 사회 거리두기", "era": "고대 그리스 (412–323 BC)", "element": "불"},
    "윈스턴 처칠": {"mtype": "ESTJ-지도자", "strengths": ["섬세한 언어 사용", " 위기 리더십", " 결단력"], "blind_spot": "과도한 자부심과 고집", "era": "20세기 영국 (1874–1965)", "element": "나무"},
    "노자": {"mtype": "INFP-사상가", "strengths": ["자연스러운 사유", " 물음표", " 비언성"], "blind_spot": "실천 회피와 관용주의", "era": "부적시 (기원전 600년경)", "element": "물"},
    "장자": {"mtype": "INFP-철학자", "strengths": ["변화 수용", " 생명의 유대감", " 유머 감수"], "blind_spot": "지나친 이완과 관용", "era": "전국시대 (기원전 369–286년)", "element": "공기"},
    "부처": {"mtype": "INFP-사상가", "strengths": ["자비와 연민", " 깊은 성찰", " 중도 실천"], "blind_spot": "고독과 관념주의", "era": "기원전 563–483년 (인도)", "element": "부"},
    "아르투어 쇼펜하우어": {"mtype": "INTJ-사상가", "strengths": ["비판적 사고", " 예술적 감수성", " 깊은 성찰"], "blind_spot": "비관주의와 고독", "era": "19세기 독일 (1788–1860)", "element": "어둠"},
    "율리우스 카이사르": {"mtype": "ENTJ-전략가", "strengths": ["전략적 판단", "대중 설득", "결단력"], "blind_spot": "권력 집중과 과신", "era": "로마 공화정 말기 (기원전 100–44년)", "element": "태양"},
            "헬렌 켈러": {"mtype": "ENFJ-사상가", "strengths": ["극복의 희망", " 연대감", " 설득력"], "blind_spot": "과도한 압력과 완벽주의", "era": "20세기 미국 (1880–1968)", "element": "불"},
    "예수": {"mtype": "INFJ-사상가", "strengths": ["자비와 사랑", " 용기 있는 급진성", " 근접성"], "blind_spot": "과도한 희생과 비관주의", "era": "기원전 4–30년 (유대)", "element": "빛"},
    "마하트마 간디": {"mtype": "INFJ-투사자", "strengths": ["비폭력적 저항", " 자기 희생", " 설득력"], "blind_spot": "과도한 이상주의와 실용성 회피", "era": "20세기 인도 (1869–1948)", "element": "촛불"},
    "알베르트 슈바이처": {"mtype": "INTJ-사상가", "strengths": ["과학적 분석", " 침묵과 깊이", " 독립적 사고"], "blind_spot": "감정 억제와 고독", "era": "20세기 프랑스 (1913–2012)", "element": "불꽃"},
    "테레사 수녀": {"mtype": "ISFP-수호자", "strengths": ["자비로운 돌봄", " 영적 통찰", " 사랑스러운 헌신"], "blind_spot": "고통에 대한 회피와 불안", "era": "20세기 알바니아/인도 (1910–1997)", "element": "빛"},
    "유비": {"mtype": "ENFJ-지도자", "strengths": ["정의로운 사랑", " 배신과 용서", " 인간 관계"], "blind_spot": "과도한 신뢰와 비관주의", "era": "후한 말 (161–223)", "element": "불"},
}

MENTOR_QUOTES = {
    "전략/권력형": ("판세를 읽는 사람은 다음 선택의 대가까지 계산한다.", "결단력만큼이나 권한을 어디까지 가져갈지 스스로 묻는 유형입니다."),
    "결단/개척형": ("피할 수 없다면, 내가 먼저 방향을 정한다.", "결정은 완벽한 확신보다 책임질 준비에서 시작됩니다."),
    "원칙/시스템형": ("사람을 위한 질서는 작은 약속에서 자란다.", "혼자 빛나는 답보다 오래 작동하는 구조를 선택하는 사람입니다."),
    "통찰/질문형": ("좋은 질문 하나가 낡은 정답을 흔든다.", "당신은 남들이 지나친 전제를 발견하고, 더 나은 질문으로 길을 엽니다."),
    "해탈/관조형": ("흐르는 것을 억지로 붙잡지 않을 때 보이는 것이 있다.", "거리를 두고 본 뒤, 꼭 필요한 것만 남기는 힘이 있습니다."),
    "자비/연대형": ("혼자 맞는 정답보다 함께 견디는 삶을 택한다.", "당신에게 성취의 기준은 누군가의 삶이 실제로 나아지는가입니다."),
}

MENTOR_VIEWPOINTS = {
    "이순신": "지금 당장 가장 큰 위기를 줄이는 행동 하나를 골라라. 준비된 사람은 불안의 크기보다 행동의 방향을 더 신뢰한다.",
    "세종대왕": "사람을 위한 제도와 배움은 결국 공동체를 살리는 길이다. 약한 사람의 목소리를 먼저 듣는 사람이 오래 남는다.",
    "소크라테스": "정답을 미리 고정하지 말고, 당신이 무엇을 전제로 믿는지부터 다시 묻는 것이 가장 빠른 지혜다.",
    "스티브 잡스": "남의 기대를 살지 말고, 당신이 정말 진짜로 사랑하는 일을 깊이 보라. 그 선택이 가장 큰 몰입을 만든다.",
    "공자": "배움은 말을 잘하는 데서 나오지 않는다. 익힌 것을 매일 다듬는 사람에게 진짜 덕이 생긴다.",
    "예수": "타인을 다치게 하는 방식보다, 관계를 살리는 문장이 더 큰 힘을 가진다. 먼저 배려를 건네라.",
    "부처": "지금의 불편이 영원한 적이 아님을 기억하라. 가장 큰 평온은 붙잡지 않는 데서 온다.",
    "니체": "남에게 의지하느라 정체될 것이 아니라, 당신이 직접 서는 힘을 길러라. 그 힘이 살아 있는 사람을 만든다.",
    "쇼펜하우어": "사건이 아니라 해석이 마음을 무겁게 하는 법이다. 관점을 바꾸면 고통의 강도도 바뀐다.",
    "마하트마 간디": "사람을 바꾸는 가장 큰 힘은 폭력이 아니라, 당신이 어떤 삶을 살아내는가다.",
    "알베르트 아인슈타인": "지식으로 답을 찾기보다, 상상력을 이용해 문제를 다른 각도에서 보라. 그 변화가 혁신을 만든다.",
    "에이브러햄 링컨": "가능함보다 해야 할 일을 먼저 보라. 책임을 인정할 때 진짜 결단이 시작된다.",
    "나폴레옹": "기회를 기다리기보다 지형과 자원을 먼저 읽고, 승산이 생긴 순간 한 번에 결단하라. 다만 모든 전선을 혼자 통제하려 하지는 마라.",
    "징기스칸": "사람의 출신보다 실제 능력을 보고 빠르게 연결하라. 속도는 강점이지만, 두려움으로 따르게 만든 조직은 오래가지 않는다.",
    "체 게바라": "불평등을 발견했다면 비판에 머물지 말고 함께 움직일 사람과 구체적인 행동을 정하라. 신념이 타인의 목소리를 지우지 않게 경계하라.",
    "알렉산더 대왕": "익숙한 경계를 넘어 배울 대상을 찾아라. 큰 비전은 정복한 땅의 다양성을 존중할 때 비로소 오래가는 통합이 된다.",
    "정약용": "좋은 뜻을 제도로 번역하라. 문제를 탓하기보다 누구에게 어떤 불편이 생기는지 관찰하고, 내일 바로 작동할 구조를 설계하라.",
    "아리스토텔레스": "극단적인 선택 사이에서 반복 가능한 좋은 습관을 찾아라. 현상을 분류하는 데서 멈추지 말고 실제 삶에서 검증하라.",
    "조조": "감정이 아니라 능력과 상황을 기준으로 사람을 배치하라. 냉정한 판단도 신뢰를 잃으면 조직의 힘을 스스로 깎아먹는다.",
    "레오나르도 다빈치": "서로 멀어 보이는 분야를 직접 관찰하고 연결하라. 아이디어를 더 모으기 전에 하나를 골라 손으로 완성해보라.",
    "니콜라 테슬라": "아직 보이지 않는 가능성을 오래 상상하되, 작동하는 실험으로 증명하라. 혼자만의 완벽한 설계보다 세상에 전달되는 결과가 중요하다.",
    "디오게네스": "남들이 당연하다고 부르는 욕망을 하나씩 의심하라. 독립은 무례함의 면허가 아니므로, 솔직함이 필요한 사람에게 실제 도움이 되는지 살펴라.",
    "윈스턴 처칠": "위기의 순간에는 거창한 낙관보다 견딜 수 있는 다음 문장과 행동을 제시하라. 강한 언어 뒤에도 현실의 피로를 돌보는 책임을 잊지 마라.",
    "노자": "모든 문제를 힘으로 밀어붙이지 말고, 불필요한 개입을 먼저 덜어내라. 비워낸 자리에 자연스럽게 자라는 질서를 지켜보라.",
    "장자": "하나의 기준으로 자신과 타인을 가두지 마라. 관점을 바꿔보는 자유를 얻되, 현실에서 누군가 감당하는 고통까지 가볍게 만들지는 마라.",
    "아르투어 쇼펜하우어": "욕망이 만드는 소음을 한 걸음 떨어져 관찰하라. 평온을 찾는 일은 세상을 외면하는 것이 아니라, 타인의 고통까지 계산에 넣는 연민에서 완성된다.",
    "율리우스 카이사르": "막힌 길에서는 힘만 겨루지 말고 지형과 사람의 마음, 다음에 열릴 선택지를 함께 읽어라. 다만 승리를 위해 권력을 한곳에 모으는 순간 공화국의 균형이 무너질 수 있음을 잊지 마라.",
    "헬렌 켈러": "자신의 한계를 설명하는 데 머물지 말고, 배움과 연대를 통해 장벽을 바꾸는 행동을 시작하라. 극복을 혼자만의 의지로 포장하지 말고 도움의 손길도 기억하라.",
    "알베르트 슈바이처": "당신의 지식과 재능이 가장 가까운 생명을 어떻게 살릴 수 있는지 묻고, 작지만 지속 가능한 돌봄으로 옮겨라.",
    "테레사 수녀": "거대한 문제를 한 번에 해결하려 하지 말고 지금 눈앞의 한 사람을 존엄하게 대하라. 돌봄은 감정이 아니라 반복되는 구체적 행동이다.",
    "유비": "혼자 옳으려 하기보다 신뢰할 사람의 마음을 얻고 함께 갈 명분을 세워라. 다만 선의를 믿는 것과 판단을 포기하는 것은 다르다.",
}


MENTOR_STORY_TAGLINES = {
    "이순신": "불안해도 현장으로 먼저 나아가는 사람",
    "세종대왕": "사람을 살리는 답을 끝까지 설계하는 사람",
    "소크라테스": "정답보다 질문으로 판을 다시 짜는 사람",
    "스티브 잡스": "남의 기준보다 자기 감각을 믿고 밀어붙이는 사람",
    "공자": "작은 태도와 약속으로 오래가는 질서를 만드는 사람",
    "예수": "가장 약한 사람의 자리에서 세상을 다시 보는 사람",
    "부처": "붙잡을 것과 놓을 것을 조용히 가려내는 사람",
    "니체": "주어진 운명에 머물지 않고 자기 길을 만드는 사람",
    "쇼펜하우어": "세상의 소음에서 한 발 물러나 본질을 보는 사람",
    "체 게바라": "계산만 하기보다 먼저 현실에 뛰어드는 사람",
    "율리우스 카이사르": "막힌 판에서도 기회를 읽고 승부를 거는 사람",
    "나폴레옹": "기회가 오기 전에 지형부터 바꾸는 사람",
    "징기스칸": "경계를 넘고 사람을 연결해 길을 넓히는 사람",
    "알렉산더 대왕": "익숙한 세계를 넘어 더 큰 지도를 그리는 사람",
    "정약용": "좋은 뜻을 실제로 작동하는 구조로 바꾸는 사람",
    "아리스토텔레스": "극단 사이에서 오래 갈 방법을 찾아내는 사람",
    "레오나르도 다빈치": "서로 먼 것들을 연결해 새로운 가능성을 보는 사람",
    "니콜라 테슬라": "아직 보이지 않는 미래를 먼저 상상하는 사람",
    "디오게네스": "당연하다는 말 앞에서 멈추지 않고 따져 묻는 사람",
    "윈스턴 처칠": "흔들리는 순간에도 다음 한 걸음을 말해주는 사람",
    "노자": "힘을 덜어낼 때 오히려 길이 열린다는 걸 아는 사람",
    "장자": "한 가지 기준에 갇히지 않고 시선을 바꾸는 사람",
    "헬렌 켈러": "혼자가 아니라 연결의 힘으로 벽을 넘는 사람",
    "마하트마 간디": "자신의 삶으로 변화를 설득하려는 사람",
    "알베르트 아인슈타인": "남들이 당연하게 본 문제를 다른 각도에서 보는 사람",
    "알베르트 슈바이처": "아는 것을 가장 가까운 생명을 돕는 데 쓰는 사람",
    "테레사 수녀": "거대한 말보다 눈앞의 한 사람을 돌보는 사람",
    "유비": "혼자 앞서기보다 함께 갈 사람의 마음을 얻는 사람",
}

MENTOR_STORY_ADVICE = {
    "이순신": "두려움이 사라질 때까지 기다리지 말고, 지금 지킬 수 있는 한 사람과 한 가지 일부터 붙들어 보세요.",
    "세종대왕": "당신의 생각을 혼자 증명하려 하기보다, 누군가가 실제로 쓸 수 있는 방식으로 바꾸어 보세요.",
    "소크라테스": "답을 서둘러 고르기 전에, 지금 당연하다고 믿는 전제 하나부터 다시 물어보세요.",
    "스티브 잡스": "모두를 만족시키려는 선택을 덜어내고, 정말 중요하다고 느끼는 하나에 힘을 몰아주세요.",
    "공자": "거창한 선언보다 오늘 반복할 수 있는 작은 약속 하나가 당신의 기준을 만듭니다.",
    "예수": "옳다는 것을 증명하기 전에, 당신 앞에 있는 사람이 무엇을 견디고 있는지 먼저 바라보세요.",
    "부처": "이미 지나간 장면과 아직 오지 않은 걱정을 잠시 내려놓고, 지금 바꿀 수 있는 것만 바라보세요.",
    "니체": "남이 정해준 안전한 답을 기다리지 말고, 당신이 감당할 수 있는 방식으로 자기 기준을 만들어 보세요.",
    "쇼펜하우어": "문제를 더 크게 만드는 해석 하나를 내려놓고, 타인의 고통까지 보이는 거리에서 다시 바라보세요.",
    "체 게바라": "생각이 너무 많아져 발이 묶일 때는, 함께 움직일 사람 한 명을 찾고 작더라도 현실을 흔드는 행동부터 시작하세요.",
    "율리우스 카이사르": "승부를 걸되 모든 권한을 혼자 쥐려 하지는 마세요. 큰 판일수록 함께 결정할 여지가 오래가는 힘이 됩니다.",
    "나폴레옹": "기회를 기다리기보다 내가 바꿀 수 있는 지형부터 정리하고, 결정한 뒤에는 책임 있게 밀고 가세요.",
}


def mentor_viewpoint_for(mentor: str, user_scores: dict[str, int]) -> str:
    """Return a perspective lens, with a persona-based fallback for future additions."""
    viewpoint = MENTOR_VIEWPOINTS.get(mentor)
    if viewpoint:
        return viewpoint
    labels = {"Action": "실행", "Reflection": "성찰", "Innovation": "혁신", "Order": "질서", "Logic": "논리", "Empathy": "공감", "Mastery": "극복", "Acceptance": "수용"}
    strongest = sorted(MENTOR_AXES, key=lambda axis: user_scores.get(axis, 0), reverse=True)[:2]
    vector = PERSONA_VECTORS.get(mentor, {})
    mentor_strength = max(MENTOR_AXES, key=lambda axis: vector.get(axis, 0))
    return f"{labels[mentor_strength]}을 중심에 두면 {labels[strongest[0]]}에 대한 당신의 기준이 더 선명해집니다. 동시에 {labels[strongest[1]]}을 잃지 않는지 함께 살펴보면 {mentor}의 관점이 당신의 선택을 다시 바라보는 렌즈가 됩니다."


def mentor_story(mentor: str, user_scores: dict[str, int]) -> tuple[str, str, str]:
    """Turn the matching result into a human-readable story instead of a score report."""
    labels = {
        "Action": "직관과 실행력",
        "Reflection": "깊이 생각하는 힘",
        "Innovation": "새로운 가능성을 보는 감각",
        "Order": "질서와 책임감",
        "Logic": "논리적으로 판단하는 힘",
        "Empathy": "사람을 헤아리는 마음",
        "Mastery": "한 가지를 끝까지 파고드는 집중력",
        "Acceptance": "변화를 받아들이는 유연함",
    }
    strongest = sorted(MENTOR_AXES, key=lambda axis: user_scores.get(axis, 0), reverse=True)[:2]
    first, second = (labels[axis] for axis in strongest)
    tagline = MENTOR_STORY_TAGLINES.get(mentor, f"{first}으로 자기만의 길을 만드는 사람")
    resemblance = (
        f"당신은 안전한 정답을 그대로 따르기보다 {first}을(를) 믿고 선택하려는 쪽에 가깝습니다. "
        f"동시에 {second}도 놓치지 않으려는 모습이 보여서, {mentor}가 걸어온 방식과 닮은 지점을 발견했습니다."
    )
    advice = MENTOR_STORY_ADVICE.get(mentor, mentor_viewpoint_for(mentor, user_scores))
    return tagline, resemblance, advice


def mentor_comparison_phrase(person: str, user_scores: dict[str, int], opposite: bool = False) -> str:
    """Give a short human-readable reason for a nearby or contrasting mentor."""
    labels = {
        "Action": "실행",
        "Reflection": "성찰",
        "Innovation": "창의",
        "Order": "질서",
        "Logic": "논리",
        "Empathy": "공감",
        "Mastery": "집중",
        "Acceptance": "유연함",
    }
    user_profile = normalized_user_profile(user_scores)
    vector = PERSONA_VECTORS.get(person, {})
    if opposite:
        axis = max(MENTOR_AXES, key=lambda item: abs(user_profile.get(item, 0) - vector.get(item, 0)))
        return f"{labels[axis]}을(를) 바라보는 방식이 가장 달라서, 당신의 익숙한 선택을 흔들어볼 인물입니다."
    story_lines = {
        "이순신": "불리한 조건에서도 책임을 피하지 않고, 준비한 것을 현장에서 끝까지 밀어붙이는 쪽입니다.",
        "세종대왕": "당신의 생각을 혼자만의 성취로 끝내지 않고, 다른 사람이 쓸 수 있는 질서로 만들려는 쪽입니다.",
        "소크라테스": "남들이 정답이라고 부르는 순간에도 한 번 더 묻고, 선택의 전제를 확인하려는 쪽입니다.",
        "스티브 잡스": "많이 벌이기보다 본질 하나를 골라 집요하게 다듬고 싶은 마음이 닮아 있습니다.",
        "공자": "큰 변화보다 매일 지킬 태도와 관계의 약속이 결국 사람을 만든다고 보는 쪽입니다.",
        "예수": "승리보다 누군가가 덜 다치고 다시 일어서는지를 중요한 기준으로 삼는 쪽입니다.",
        "부처": "더 세게 움켜쥐기보다 무엇을 내려놓아야 마음과 판단이 맑아지는지 살피는 쪽입니다.",
        "니체": "남이 정해준 기준에 안주하기보다, 스스로 감당할 가치를 만들어보려는 쪽입니다.",
        "쇼펜하우어": "사건 자체보다 그것을 해석하는 마음의 움직임을 한 발 떨어져 바라보려는 쪽입니다.",
        "아르투어 쇼펜하우어": "사건 자체보다 그것을 해석하는 마음의 움직임을 한 발 떨어져 바라보려는 쪽입니다.",
        "체 게바라": "생각만으로 안전한 결론을 기다리기보다, 불편한 현실에 직접 몸을 던져 바꾸려는 쪽입니다.",
        "율리우스 카이사르": "판이 불리해도 사람과 지형을 읽고, 결정적인 순간에 먼저 판을 움직이려는 쪽입니다.",
        "나폴레옹": "기회가 오기를 기다리기보다 자원과 순서를 재배치해 승산을 만드는 쪽입니다.",
        "징기스칸": "출신보다 가능성을 보고 빠르게 사람을 연결해 새로운 길을 여는 쪽입니다.",
        "알렉산더 대왕": "익숙한 경계 안에 머물기보다 더 넓은 세계를 직접 확인하고 싶은 쪽입니다.",
        "정약용": "좋은 의도를 실제로 작동하는 제도와 도구로 바꾸어야 한다고 보는 쪽입니다.",
        "아리스토텔레스": "감정적인 한 번의 결단보다 오래 반복할 수 있는 균형 잡힌 방법을 찾는 쪽입니다.",
        "레오나르도 다빈치": "서로 상관없어 보이는 분야를 이어 붙여 새로운 가능성을 발견하는 쪽입니다.",
        "니콜라 테슬라": "아직 아무도 보지 못한 가능성을 먼저 상상하고, 그것을 현실의 실험으로 옮기려는 쪽입니다.",
        "디오게네스": "멋있어 보이는 답보다 정말 필요한 것이 무엇인지 끝까지 의심하는 쪽입니다.",
        "윈스턴 처칠": "불안한 순간에도 사람을 움직일 수 있는 말과 다음 행동을 함께 찾는 쪽입니다.",
        "노자": "더 많이 개입하기보다 힘을 빼고 흐름을 읽을 때 문제가 풀린다고 보는 쪽입니다.",
        "장자": "하나의 답에 자신을 가두기보다 관점을 바꾸며 뜻밖의 출구를 찾는 쪽입니다.",
        "헬렌 켈러": "혼자 버티는 영웅담보다 배움과 연대가 장벽을 실제로 낮춘다고 믿는 쪽입니다.",
        "마하트마 간디": "상대를 꺾는 힘보다 자신의 삶으로 변화를 설득하는 힘을 더 믿는 쪽입니다.",
        "알베르트 아인슈타인": "익숙한 공식에 맞추기보다 문제를 전혀 다른 각도에서 다시 바라보는 쪽입니다.",
        "알베르트 슈바이처": "알고 있는 것에서 멈추지 않고, 가장 가까운 사람을 돕는 행동으로 이어가려는 쪽입니다.",
        "테레사 수녀": "거대한 구호보다 지금 눈앞의 한 사람에게 건넬 수 있는 돌봄을 먼저 보는 쪽입니다.",
        "유비": "혼자 가장 빠르게 가기보다 함께 오래 갈 사람의 마음과 신뢰를 중요하게 보는 쪽입니다.",
    }
    if person in story_lines:
        return story_lines[person]
    shared = sorted(
        MENTOR_AXES,
        key=lambda item: min(user_profile.get(item, 0), vector.get(item, 0)),
        reverse=True,
    )
    shared = [axis for axis in shared if user_profile.get(axis, 0) >= 4 and vector.get(axis, 0) >= 4][:2]
    return f"{'와 '.join(labels[axis] for axis in shared)} 쪽에서 당신과 닮은 결을 보입니다." if shared else "당신과 비슷한 선택의 방향을 보이는 인물입니다."

MENTOR_PROFILES = {
    "이순신": ("조선의 수군 지휘관으로 임진왜란의 바다를 지키며 명량과 한산도에서 전세를 뒤집었습니다.", "책임, 절제, 현장 판단을 중시했고 불리한 조건에서도 공동체를 지키는 결단을 선택했습니다.", "말보다 준비와 행동으로 신뢰를 쌓는 원칙적이고 묵직한 사람입니다."),
    "스티브 잡스": ("애플을 공동 창업하고 위기를 겪은 뒤 다시 이끌며 개인용 컴퓨터와 스마트폰의 사용 경험을 바꿨습니다.", "기술은 복잡함을 더하는 것이 아니라 사람에게 본질적인 경험을 건네야 한다고 믿었습니다.", "집요하고 직관적이며 높은 기준을 타인과 자신에게 모두 요구하는 창조자입니다."),
    "나폴레옹": ("프랑스 혁명기의 혼란 속에서 군사 지도자로 올라 황제에 이르렀고 유럽의 질서를 크게 재편했습니다.", "능력에 따른 기회와 빠른 실행, 법 앞의 제도적 평등을 중시했습니다.", "야심이 크고 자신감이 강하며 전략적으로 상황을 읽는 승부사입니다."),
    "징기스칸": ("몽골 부족을 통합해 거대한 제국을 세우고 동서 교류의 길을 넓혔습니다.", "혈통보다 능력을 중시하고 빠른 정보 전달과 실용적인 조직 운영을 활용했습니다.", "기회를 놓치지 않는 현실주의자이자 목표를 위해 냉정하게 움직이는 지도자입니다."),
    "체 게바라": ("아르헨티나 출신의 의사이자 혁명가로 쿠바 혁명에 참여하고 사회 변혁을 주장했습니다.", "불평등에 맞서 연대와 혁명적 실천을 통해 새로운 사회를 만들고자 했습니다.", "이상에 헌신적이고 행동력이 강하지만 신념을 위해 타협하지 않는 급진성을 지녔습니다."),
    "알렉산더 대왕": ("마케도니아의 왕으로 그리스에서 이집트와 인도에 이르는 제국을 건설했습니다.", "정복지의 문화를 연결하고 새로운 세계 질서를 만들려는 통합의 비전을 품었습니다.", "대담하고 호기심이 많으며 불가능해 보이는 목표에도 먼저 뛰어드는 사람입니다."),
    "세종대왕": ("조선의 왕으로 훈민정음을 창제하고 과학, 농업, 음악과 제도를 발전시켰습니다.", "지식과 제도는 백성이 이해하고 활용할 수 있을 때 비로소 공공의 힘이 된다고 보았습니다.", "깊이 생각하면서도 실용적이며 약한 사람의 불편을 제도로 해결하려는 리더입니다."),
    "공자": ("춘추시대의 사상가이자 교육자로 제자들을 가르치며 유교적 윤리의 토대를 세웠습니다.", "배움, 인, 예, 역할에 맞는 책임을 통해 개인과 사회의 질서를 함께 세우려 했습니다.", "꾸준하고 성찰적이며 관계 속에서 자신의 태도를 끊임없이 다듬는 스승입니다."),
    "정약용": ("조선 후기의 실학자로 행정과 토목, 법과 농업에 관한 폭넓은 저술을 남겼습니다.", "지식은 현실의 백성을 이롭게 하는 실용적 제도와 행정으로 이어져야 한다고 주장했습니다.", "관찰력이 뛰어나고 현실적이며 낡은 관습보다 실제 효과를 따지는 개혁가입니다."),
    "아리스토텔레스": ("고대 그리스의 철학자이자 알렉산더의 스승으로 논리학과 자연학, 윤리학을 체계화했습니다.", "좋은 삶은 극단이 아닌 덕의 습관과 공동체 안에서의 실천으로 만들어진다고 보았습니다.", "분류하고 관찰하며 여러 가능성을 균형 있게 검토하는 체계적인 사상가입니다."),
    "조조": ("후한 말의 정치가이자 군사 지도자로 혼란한 중국 북부를 통합하고 위나라의 기반을 닦았습니다.", "혈통보다 능력을 기용하고 현실의 힘과 제도를 바탕으로 질서를 회복하려 했습니다.", "냉철하고 결단력 있으며 감정보다 상황과 결과를 우선하는 전략가입니다."),
    "에이브러햄 링컨": ("미국의 제16대 대통령으로 남북전쟁을 이끌고 노예 해방을 추진했습니다.", "분열된 공동체를 보존하면서도 자유와 인간의 존엄이라는 원칙을 포기하지 않았습니다.", "겸손하고 유머러스하지만 중요한 순간에는 긴 책임을 감당하는 인내의 리더입니다."),
    "소크라테스": ("아테네의 철학자로 글을 남기지 않고 대화와 질문을 통해 사람들의 믿음을 시험했습니다.", "자신의 무지를 아는 것이 지혜의 시작이며 성찰하지 않는 삶은 살 가치가 없다고 보았습니다.", "호기심 많고 집요하며 상대가 당연하게 여기는 전제를 끝까지 묻는 사람입니다."),
    "알베르트 아인슈타인": ("독일 태생의 물리학자로 상대성 이론을 통해 시간과 공간에 대한 이해를 바꾸었습니다.", "상상력과 독립적인 사고가 기존 권위와 공식을 넘어서는 출발점이라고 믿었습니다.", "온화하지만 자기 방식이 분명하고, 호기심을 오래 붙드는 자유로운 사색가입니다."),
    "레오나르도 다빈치": ("르네상스 시대의 화가, 발명가, 해부학자로 예술과 과학의 경계를 넘나들었습니다.", "세상을 직접 관찰하고 서로 다른 분야를 연결할 때 새로운 발견이 나온다고 보았습니다.", "끝없는 호기심과 섬세한 관찰력을 지닌 다재다능한 실험가입니다."),
    "니콜라 테슬라": ("세르비아계 미국인 발명가로 교류 전기와 여러 전기 기술의 발전에 크게 기여했습니다.", "미래의 가능성을 먼저 상상하고 인류 전체에 도움이 될 기술을 만들고자 했습니다.", "집중력이 강하고 이상주의적이며 자신의 내면 세계에 깊이 몰입하는 발명가입니다."),
    "디오게네스": ("고대 그리스의 견유학파 철학자로 관습과 물질적 욕망을 거부하며 검소하게 살았습니다.", "자연에 맞는 자립적 삶과 솔직함을 중시하고 사회적 허영을 통렬히 비판했습니다.", "거침없고 독립적이며 권위 앞에서도 아첨하지 않는 급진적인 질문자입니다."),
    "니체": ("독일의 철학자로 인간의 가치와 자기 창조를 탐구하며 기존 도덕을 되묻는 논쟁을 벌였습니다.", "가치의 재평가와 자기 극복을 통해 삶을 더 강하고 정직하게 살 수 있다고 믿었습니다.", "강한 의지와 비판적 독립성을 가진 사람으로, 정해진 기준을 넘어서 자신만의 기준을 세우려 합니다."),
    "윈스턴 처칠": ("영국의 정치가이자 작가로 제2차 세계대전 당시 국민을 이끌며 저항을 독려했습니다.", "위기의 순간에도 자유를 지키기 위한 용기와 공동체의 결속이 필요하다고 강조했습니다.", "언어와 의지가 강하고 낙관과 비관을 함께 품은 현실적인 전시 지도자입니다."),
    "노자": ("도가 사상의 핵심 인물로 전해지며 '도덕경'을 통해 자연의 흐름과 무위의 지혜를 말했습니다.", "억지로 통제하기보다 사물의 본성을 따르고 비워냄으로써 더 오래가는 질서를 찾았습니다.", "말수가 적고 관조적이며 힘을 과시하지 않는 부드러운 통찰가입니다."),
    "장자": ("전국시대의 사상가로 꿈과 현실, 인간과 자연의 경계를 자유롭게 성찰했습니다.", "고정된 기준과 분별에서 벗어나 변화와 다양성을 받아들이는 자유를 추구했습니다.", "유머와 비유를 즐기며 한 가지 정답에 갇히지 않는 유연한 사상가입니다."),
    "부처": ("고타마 싯다르타로 태어나 수행 끝에 깨달음을 얻고 고통에서 벗어나는 길을 가르쳤습니다.", "무상과 연기, 중도와 자비를 통해 집착을 줄이고 모든 존재의 고통을 살피고자 했습니다.", "차분하고 자비로우며 반응하기 전에 마음의 움직임을 바라보는 수행자입니다."),
    "아르투어 쇼펜하우어": ("독일의 철학자로 세계를 맹목적인 의지와 표상으로 해석하고 연민의 윤리를 강조했습니다.", "끝없는 욕망이 고통을 만들기에 예술과 절제, 타인의 고통을 이해하는 연민이 필요하다고 보았습니다.", "비관적이지만 날카롭고 인간의 욕망을 냉정하게 관찰하는 고독한 사상가입니다."),
    "율리우스 카이사르": ("로마의 정치가이자 장군으로 갈리아 전쟁과 내전을 거쳐 공화정 말기의 질서를 재편했습니다.", "군사적 성취뿐 아니라 대중을 설득하는 언어와 행정 개혁을 활용했지만, 권력 집중이 공화정의 균형을 흔들었다는 한계도 남겼습니다.", "전략적이고 결단력이 강하며 위기에서 기회를 읽지만, 자신의 판단을 지나치게 믿을 위험이 있는 지도자입니다."),
    "헬렌 켈러": ("어린 시절 시청각을 잃었지만 교육자 앤 설리번과 함께 배우며 작가와 사회운동가가 되었습니다.", "장애인의 교육권과 평등을 위해 연대했고 인간의 의지와 사랑이 장벽을 넘는다고 믿었습니다.", "강인하고 감사할 줄 알며 자신의 경험을 타인의 권리를 넓히는 힘으로 바꾼 사람입니다."),
    "예수": ("갈릴리에서 가르침을 전하며 가난하고 소외된 이들과 함께했고 사랑과 용서의 메시지를 남겼습니다.", "이웃 사랑, 용서, 약한 사람을 먼저 돌보는 연대가 공동체의 중심이어야 한다고 가르쳤습니다.", "따뜻하고 단호하며 권위보다 사람의 상처와 존엄을 먼저 바라보는 인물입니다."),
    "마하트마 간디": ("인도의 독립운동을 이끈 변호사이자 정치 지도자로 비폭력 저항을 실천했습니다.", "진실과 비폭력, 자립을 통해 제국의 폭력에 맞서며 수단과 목적이 닮아야 한다고 주장했습니다.", "절제되고 끈기 있으며 자신의 삶으로 원칙을 증명하려 한 실천가입니다."),
    "알베르트 슈바이처": ("신학자와 음악가로 활동한 뒤 의사가 되어 아프리카 랑바레네에서 병원을 운영했습니다.", "생명에 대한 경외를 바탕으로 지식과 재능을 타인을 돕는 책임으로 연결했습니다.", "겸손하고 헌신적이며 말보다 지속적인 돌봄을 선택하는 봉사자입니다."),
    "테레사 수녀": ("인도 콜카타에서 가난하고 죽어가는 사람들을 돌보는 선교와 봉사 활동을 펼쳤습니다.", "가장 작은 사람의 존엄을 지키는 사랑과 구체적인 돌봄을 삶의 중심에 두었습니다.", "검소하고 인내심이 강하며 가까운 한 사람을 끝까지 돌보는 실천가입니다."),
    "유비": ("삼국시대 촉한의 군주로 오랜 역경 끝에 사람을 모아 자신의 세력을 세웠습니다.", "덕과 신뢰를 바탕으로 인재를 품고 공동체의 명분과 연대를 지키려 했습니다.", "온화하고 사람의 마음을 얻는 데 능하며 혼자보다 함께 가는 길을 믿는 지도자입니다."),
}


def calculate_best_mentor(user_scores: dict[str, int]) -> tuple[str, str, float]:
    """Return the mentor with the highest normalized profile similarity."""
    person, group, score = calculate_mentor_rankings(user_scores)[0]
    return person, group, score


def normalized_user_profile(user_scores: dict[str, int]) -> dict[str, float]:
    """Map raw quiz totals to the same 0-10 scale used by mentor vectors, with a stable 0-10 normalization."""
    raw = {axis: max(0, user_scores.get(axis, 0)) for axis in MENTOR_AXES}
    max_value = max(raw.values()) if any(raw.values()) else 1
    return {axis: round(min(10.0, (value / max(1, max_value)) * 10), 2) for axis, value in raw.items()}


def cosine_similarity(user_profile: dict[str, float], mentor_vector: dict[str, int]) -> float:
    """Directional similarity using a standard cosine-based comparison."""
    dot_product = sum(user_profile.get(axis, 0) * mentor_vector.get(axis, 0) for axis in MENTOR_AXES)
    user_norm = (sum(value ** 2 for value in user_profile.values())) ** 0.5
    mentor_norm = (sum(value ** 2 for value in mentor_vector.values())) ** 0.5
    if user_norm == 0 or mentor_norm == 0:
        return 0.0
    return dot_product / (user_norm * mentor_norm)


def distance_similarity(user_profile: dict[str, float], mentor_vector: dict[str, int]) -> float:
    """Intensity-based similarity: lower average distance means higher compatibility."""
    average_distance = sum(abs(user_profile.get(axis, 0) - mentor_vector.get(axis, 0)) for axis in MENTOR_AXES) / len(MENTOR_AXES)
    return max(0.0, min(100.0, (1 - average_distance / 10) * 100))


def mentor_similarity_percent(user_scores: dict[str, int], mentor_vector: dict[str, int]) -> float:
    """Hybrid similarity score that blends directional overlap and intensity similarity."""
    user_profile = normalized_user_profile(user_scores)
    cosine_score = cosine_similarity(user_profile, mentor_vector)
    distance_score = distance_similarity(user_profile, mentor_vector)
    combined = (0.65 * (cosine_score * 100)) + (0.35 * distance_score)
    return round(max(0.0, min(100.0, combined)), 1)


def mentor_answer_concentration(user_scores: dict[str, int], neutral_count: int = 0) -> int:
    """Measure whether answers favor a few value axes or are broadly distributed."""
    values = [max(0, user_scores.get(axis, 0)) for axis in MENTOR_AXES]
    total = sum(values)
    if total == 0:
        return 0

    shares = [value / total for value in values if value > 0]
    concentration = sum(share * share for share in shares)
    minimum = 1 / len(MENTOR_AXES)
    normalized = (concentration - minimum) / (1 - minimum)
    uncertainty_penalty = min(20, neutral_count * 4)
    return max(0, min(100, int(round(normalized * 100)) - uncertainty_penalty))


def _mentor_group_for(person: str) -> str:
    group = next(group_name for group_name, (_, people, _) in MENTOR_GROUPS.items() if person in people)
    return group


def validate_mentor_coverage() -> dict[str, list[str] | bool]:
    """Verify that every roster member has one vector and one group mapping."""
    group_members = [person for _, (_, people, _) in MENTOR_GROUPS.items() for person in people]
    covered = {person: [group_name for group_name, (_, people, _) in MENTOR_GROUPS.items() if person in people] for person in MENTOR_PEOPLE}
    missing = [person for person in MENTOR_PEOPLE if person not in PERSONA_VECTORS or not covered[person]]
    duplicates = [person for person, groups in covered.items() if len(groups) != 1]
    unexpected = [person for person in group_members if person not in MENTOR_PEOPLE]
    return {
        "all_present": not missing and not duplicates and not unexpected and len(PERSONA_VECTORS) == len(MENTOR_PEOPLE),
        "coverage": covered,
        "missing": missing,
    }


MENTOR_COVERAGE_CHECK = validate_mentor_coverage()


def mentor_report(user_scores: dict[str, int], group: str) -> list[str]:
    strongest = sorted(user_scores, key=user_scores.get, reverse=True)[:3]
    labels = {"Action": "실행", "Reflection": "성찰", "Innovation": "혁신", "Order": "질서", "Logic": "본질", "Empathy": "공감", "Mastery": "자기극복", "Acceptance": "수용"}
    return [
        f"당신은 {labels[strongest[0]]}을 가장 먼저 선택하는 편입니다.",
        f"문제를 만났을 때 {labels[strongest[1]]}의 관점에서 다음 선택을 살핍니다.",
        f"이번 답변은 '{group}' 방식과 가장 가깝습니다.",
    ]


def calculate_mentor_rankings(user_scores: dict[str, int]) -> list[tuple[str, str, float]]:
    """Return all mentors ranked by hybrid similarity, which combines profile alignment and directional consistency."""
    ranked = []
    for person, vector in PERSONA_VECTORS.items():
        similarity = mentor_similarity_percent(user_scores, vector)
        group = _mentor_group_for(person)
        ranked.append((person, group, round(similarity, 1)))
    ranked.sort(key=lambda x: x[2], reverse=True)
    return ranked


def conflicting_mentors(user_scores: dict[str, int]) -> list[tuple[str, str, float]]:
    """Return the 3 mentors whose vectors are *least* similar to the user (conflict / contrast)."""
    ranked = calculate_mentor_rankings(user_scores)
    return ranked[-3:][::-1]


def mentor_match_summary(user_scores: dict[str, int], neutral_count: int = 0) -> dict[str, object]:
    """Return top matches and a readable summary of answer concentration."""
    rankings = calculate_mentor_rankings(user_scores)
    top_three = rankings[:3]
    concentration = mentor_answer_concentration(user_scores, neutral_count)
    return {
        "top_three": top_three,
        "concentration": concentration,
        "concentration_text": (
            "특정 가치에 뚜렷하게 집중되어 있습니다"
            if concentration >= 70
            else "몇 가지 가치가 함께 작동합니다"
            if concentration >= 40
            else "여러 가치가 고르게 섞여 있습니다"
        ),
    }


def enhanced_mentor_report(user_scores: dict[str, int], group: str) -> list[str]:
    """Return a concise, readable summary of the matched mentor profile."""
    ranked = calculate_mentor_rankings(user_scores)
    top_person, _, _ = ranked[0]
    strongest = sorted(user_scores, key=user_scores.get, reverse=True)[:3]
    labels = {"Action": "실행", "Reflection": "성찰", "Innovation": "창의", "Order": "질서", "Logic": "논리", "Empathy": "공감", "Mastery": "집중", "Acceptance": "유연"}
    top_axes = [labels[axis] for axis in strongest]
    score_text = ", ".join(f"{label}({user_scores[axis]}점)" for axis in strongest if axis in user_scores for label in [labels[axis]])
    style = "결단형" if user_scores.get("Action", 0) + user_scores.get("Innovation", 0) >= user_scores.get("Reflection", 0) + user_scores.get("Acceptance", 0) else "성찰형"
    similar_people = ", ".join(f"{person}({score}%)" for person, _, score in ranked[:3])
    return [
        f"당신의 답변은 '{group}' 방식과 가깝고, 그중 '{top_person}'와 가장 많이 닮아 있습니다.",
        f"답변에서 자주 드러난 선택: {score_text}",
        f"전체적으로는 {style} 쪽에 가깝고, 특히 {', '.join(top_axes)}를 중요하게 보고 있습니다.",
        f"비교해 볼 인물: {similar_people}",
        f"정리하면, '{top_person}'는 지금의 생각을 더 깊게 들여다볼 수 있는 대화 상대입니다.",
    ]


def why_this_match(mentor: str, user_scores: dict[str, int]) -> str:
    axis_labels = {
        "Action": "실행력",
        "Reflection": "성찰",
        "Innovation": "창의성",
        "Order": "질서감",
        "Logic": "논리",
        "Empathy": "공감",
        "Mastery": "집중력",
        "Acceptance": "유연함",
    }
    user_profile = normalized_user_profile(user_scores)
    mentor_vector = PERSONA_VECTORS.get(mentor, {})
    shared_axes = sorted(
        MENTOR_AXES,
        key=lambda axis: min(user_profile.get(axis, 0), mentor_vector.get(axis, 0)),
        reverse=True,
    )
    shared = [axis for axis in shared_axes if user_profile.get(axis, 0) >= 5 and mentor_vector.get(axis, 0) >= 5][:2]
    if not shared:
        shared = sorted(MENTOR_AXES, key=lambda axis: user_profile.get(axis, 0), reverse=True)[:2]
    shared_text = "와 ".join(axis_labels[axis] for axis in shared)
    user_evidence = ", ".join(
        f"{axis_labels[axis]}({user_scores.get(axis, 0)}점)"
        for axis in sorted(MENTOR_AXES, key=lambda item: user_scores.get(item, 0), reverse=True)
        if user_scores.get(axis, 0) > 0
    )[:90]
    return (
        f"당신의 답변에서는 {shared_text}을(를) 중요하게 보는 선택이 두드러졌습니다. "
        f"{mentor}도 이 기준의 비중이 높은 인물이라 추천되었습니다. "
        f"당신의 실제 응답 점수는 {user_evidence or '아직 기록된 선택이 없습니다'}이며, "
        "인물의 삶이 당신과 같다는 뜻이 아니라 선택 기준이 겹친다는 의미입니다."
    )


def mentor_match_reasons(mentor: str, user_scores: dict[str, int]) -> tuple[str, str, str]:
    """Explain the match from the user's answers, not from the mentor biography."""
    axis_labels = {
        "Action": "실행력",
        "Reflection": "성찰",
        "Innovation": "창의성",
        "Order": "질서감",
        "Logic": "논리",
        "Empathy": "공감",
        "Mastery": "집중력",
        "Acceptance": "유연함",
    }
    user_profile = normalized_user_profile(user_scores)
    mentor_vector = PERSONA_VECTORS.get(mentor, {})
    shared = sorted(
        (
            axis for axis in MENTOR_AXES
            if user_profile.get(axis, 0) >= 5 and mentor_vector.get(axis, 0) >= 5
        ),
        key=lambda axis: min(user_profile.get(axis, 0), mentor_vector.get(axis, 0)),
        reverse=True,
    )[:3]
    if not shared:
        shared = sorted(MENTOR_AXES, key=lambda axis: user_profile.get(axis, 0), reverse=True)[:2]
    shared_text = ", ".join(axis_labels[axis] for axis in shared)
    user_text = ", ".join(
        f"{axis_labels[axis]} {user_scores.get(axis, 0)}점"
        for axis in sorted(MENTOR_AXES, key=lambda axis: user_scores.get(axis, 0), reverse=True)[:3]
    )
    mentor_text = ", ".join(
        f"{axis_labels[axis]} {mentor_vector.get(axis, 0)}"
        for axis in sorted(MENTOR_AXES, key=lambda axis: mentor_vector.get(axis, 0), reverse=True)[:3]
    )
    differences = sorted(
        MENTOR_AXES,
        key=lambda axis: abs(user_profile.get(axis, 0) - mentor_vector.get(axis, 0)),
        reverse=True,
    )
    difference_text = axis_labels[differences[0]] if differences else "다른 가치"
    return (
        f"당신의 답변에서 {shared_text}을(를) 우선하는 선택이 많았기 때문에 {mentor}가 추천되었습니다.",
        f"당신의 답변 경향은 {user_text or '아직 충분히 기록되지 않았습니다'}이고, "
        f"{mentor}의 비교 프로필은 {mentor_text}입니다. 두 결과에서 겹치는 기준이 추천의 근거입니다.",
        f"가장 큰 차이는 {difference_text}에서 나타납니다. 따라서 이 결과는 '완전히 같은 인물'이라는 뜻이 아니라, "
        f"{mentor}의 기준 중 일부가 당신의 선택과 닮았다는 뜻입니다.",
    )


def conflict_reason(mentor: str, conflict_person: str) -> str:
    return f"{mentor}와 {conflict_person}는 서로 다른 선택 기준을 보여줍니다. 이 차이는 당신이 익숙한 방식에서 벗어나 놓치기 쉬운 관점을 살펴보게 합니다."


def mentor_radar_chart(user_scores: dict[str, int], mentor: str) -> str:
    """Render a six-axis SVG comparison between the user and the selected mentor."""
    import math

    axes = (("Action", "실행"), ("Reflection", "성찰"), ("Innovation", "혁신"), ("Order", "질서"), ("Empathy", "공감"), ("Mastery", "극복"))
    mentor_vector = PERSONA_VECTORS.get(mentor, {})
    user_scale = max(1.0, len(MENTOR_QUESTIONS) / 10)
    center_x, center_y, radius = 190, 155, 104

    def point(value: float, index: int, scale: float = 10.0) -> tuple[float, float]:
        angle = -math.pi / 2 + index * (2 * math.pi / len(axes))
        distance = radius * min(1.0, max(0.0, value / scale))
        return center_x + math.cos(angle) * distance, center_y + math.sin(angle) * distance

    def points(values: list[float]) -> str:
        return " ".join(f"{x:.1f},{y:.1f}" for (x, y) in (point(value, index) for index, value in enumerate(values)))

    user_values = [min(10.0, user_scores.get(axis, 0) / user_scale) for axis, _ in axes]
    mentor_values = [float(mentor_vector.get(axis, 0)) for axis, _ in axes]
    rings = []
    for level in (2, 4, 6, 8, 10):
        rings.append(f'<polygon points="{points([level] * len(axes))}" class="radar-ring" />')
    spokes = []
    labels = []
    for index, (_, label) in enumerate(axes):
        x, y = point(10, index)
        spokes.append(f'<line x1="{center_x}" y1="{center_y}" x2="{x:.1f}" y2="{y:.1f}" class="radar-spoke" />')
        label_x, label_y = point(11.7, index)
        anchor = "middle" if abs(label_x - center_x) < 22 else ("start" if label_x > center_x else "end")
        labels.append(f'<text x="{label_x:.1f}" y="{label_y:.1f}" text-anchor="{anchor}" class="radar-label">{html.escape(label)}</text>')
    return (
        '<div class="radar-card">'
        '<div class="radar-heading"><div><div class="similarity-section-title">MENTOR CONNECTION MAP</div>'
        f'<div class="radar-title">나와 {html.escape(mentor)}가 겹치는 여섯 가지 결</div></div>'
        '<div class="radar-legend"><span class="radar-dot user"></span>나 <span class="radar-dot mentor"></span>추천 인물</div></div>'
        '<svg class="radar-chart" viewBox="0 0 380 310" role="img" aria-label="나와 추천 인물의 여섯 가지 선택 경향 비교 그래프">'
        f'{"".join(rings)}{"".join(spokes)}'
        f'<polygon points="{points(user_values)}" class="radar-user" />'
        f'<polygon points="{points(mentor_values)}" class="radar-mentor" />'
        f'{"".join(labels)}</svg></div>'
    )


PARALLEL_AGE_EMOTIONS = [
    "#조급함",
    "#무기력",
    "#막막함",
    "#억울함",
    "#외로움",
    "#불안",
]
PARALLEL_AGE_CONCERNS = [
    "#돈·생계",
    "#일·커리어",
    "#번아웃",
    "#인간관계",
    "#미래·불안",
    "#육아·돌봄",
    "#연애·결혼",
    "#정체기",
]


def load_parallel_age_episodes() -> list[dict]:
    episode_path = Path(__file__).with_name("episodes.json")
    if episode_path.exists():
        try:
            return json.loads(episode_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return []


PARALLEL_AGE_EPISODES = load_parallel_age_episodes()


def normalize_parallel_tag(value: str) -> str:
    return value.strip().replace("#", "").strip()


def parallel_age_decade(age: int) -> int:
    return max(10, (age // 10) * 10)


def parallel_age_overlaps_decade(age: int, episode: dict) -> bool:
    decade_start = parallel_age_decade(age)
    decade_end = decade_start + 9
    age_min = int(episode.get("age_min", 0))
    age_max = int(episode.get("age_max", 0))
    return age_min <= decade_end and age_max >= decade_start


def parallel_condition_score(emotion: str, concern: str, episode: dict) -> int:
    score = 0
    if normalize_parallel_tag(concern) in {normalize_parallel_tag(item) for item in episode.get("concerns", [])}:
        score += 30
    if normalize_parallel_tag(emotion) in {normalize_parallel_tag(item) for item in episode.get("emotions", [])}:
        score += 15
    return score


def parallel_age_match_label(age: int, condition_score: int) -> str:
    decade = f"{parallel_age_decade(age)}대"
    if condition_score >= 45:
        return f"{decade} · 감정·고민 일치"
    if condition_score >= 30:
        return f"{decade} · 고민 일치"
    if condition_score >= 15:
        return f"{decade} · 감정 일치"
    return f"{decade} · 나이대 일치"


# Grounding: Erikson's identity vs. role confusion, Marcia's identity status, and
# developmental transitions are used here to frame these matches as age-linked life
# transitions, not as claims about any historical person's exact inner life. This is
# a psychological lens, not a fact claim.
def parallel_developmental_frame(age: int, emotion: str, concern: str) -> dict:
    if 16 <= age < 20:
        stage = "정체성 찾는 시기"
        task = "나를 어떻게 이해하고, 어떤 삶을 선택할지 시험하는 단계"
        rationale = "이 시기에는 '나는 누구인지', '어떤 사람이 되고 싶은지', '앞으로 무엇을 위해 살아야 하는지'가 자주 흔들립니다. 불안과 막막함은 약함이 아니라, 정체성을 형성하는 과정에서 자연스럽게 생기는 혼란일 수 있습니다."
    elif 20 <= age < 30:
        stage = "자기 위치를 잡는 시기"
        task = "진로, 관계, 자율성 사이에서 '내가 어떤 사람인지'를 정리하는 단계"
        rationale = "초기 성인기에는 진로, 관계, 자신감, 자율성 사이에서 끊임없이 비교가 일어납니다. 이때 조급함과 불안은 '아직 부족해서'가 아니라, 살아가면서 스스로의 위치를 정립하려는 심리적 과정의 일부일 수 있습니다."
    elif 30 <= age < 40:
        stage = "책임과 역할이 현실이 되는 시기"
        task = "사회적 역할이 실제 삶에 어떤 의미인지 점검하는 단계"
        rationale = "30대는 무엇을 하고 싶다보다, 어떤 역할을 맡고 있고 얼마나 만족하는지가 더 크게 드러나는 시기입니다. 기대와 현실 사이의 간극이 커질수록 막막함과 무기력이 더 자주 찾아옵니다."
    elif 40 <= age < 50:
        stage = "의미를 다시 설계하는 시기"
        task = "지금의 삶이 나에게 맞는지, 어떤 방향으로 다시 살아갈지 묻는 단계"
        rationale = "중년은 과거의 성취와 현재의 한계를 함께 비교하게 되는 시기라, '내 삶이 의미 있는가'라는 질문이 더 선명해집니다. 이 혼란은 실패의 증거라기보다, 삶을 다시 정의하려는 정신적 전환의 신호일 수 있습니다."
    else:
        stage = "삶을 정리하는 시기"
        task = "경험을 통합하고, 남은 시간을 어떤 값으로 채울지 생각하는 단계"
        rationale = "이 시기에는 과거를 어떻게 받아들이고, 지금의 한계를 어떤 의미로 살릴지 고민하게 됩니다. 힘든 감정은 약함이 아니라, 삶을 정리하고 의미를 다시 맞추는 과정에서 생기는 자연스러운 흔들림일 수 있습니다."

    concern_map = {
        "#돈·생계": "경제적 안정과 자기 가치를 동시에 유지해야 하는 문제",
        "#일·커리어": "직업, 역할, 성취, 진로 선택에 대한 불안",
        "#번아웃": "정체감과 에너지의 고갈, 삶의 무력감",
        "#인간관계": "관계에서의 거절, 소속감, 인정 욕구",
        "#미래·불안": "앞으로의 삶에 대한 불확실성과 의미의 흔들림",
        "#육아·돌봄": "책임과 정서적 부담, 자기 삶의 상실 가능성",
        "#연애·결혼": "애정, 연결, 자기 정체성의 불안",
        "#정체기": "자기 위치와 삶의 방향을 상실한 듯한 혼란",
    }
    concern_label = concern_map.get(concern, "현실 속 역할과 자아의 균형 문제")
    emotion_label = {
        "#조급함": "더 빨리, 더 잘해야 한다는 압박",
        "#무기력": "에너지와 동기 부족으로 삶이 멈춘 듯한 느낌",
        "#막막함": "해결책의 실마리를 찾기 어려운 감정",
        "#억울함": "노력과 인정 사이의 불균형을 느끼는 감정",
        "#외로움": "사람들 속에서도 혼자인 듯한 소속감 결핍",
        "#불안": "앞으로의 불확실성 앞에서 마음이 흔들리는 감정",
    }.get(emotion, "현재의 혼란을 설명하는 감정")
    return {
        "stage": stage,
        "task": task,
        "concern_label": concern_label,
        "emotion_label": emotion_label,
        "rationale": rationale,
    }


def score_parallel_age_episode(age: int, emotion: str, concern: str, episode: dict) -> int:
    if not parallel_age_overlaps_decade(age, episode):
        return 0
    score = 50 + parallel_condition_score(emotion, concern, episode)
    if episode.get("source_type") == "A":
        score += 10
    return score


def build_parallel_age_cards(age: int, emotion: str, concern: str, limit: int = 4) -> list[dict]:
    selected = []
    seen_people: set[str] = set()
    ordered_episodes = sorted(
        PARALLEL_AGE_EPISODES,
        key=lambda item: (
            -score_parallel_age_episode(age, emotion, concern, item),
            -parallel_condition_score(emotion, concern, item),
            0 if item.get("source_type") == "A" else 1,
            item.get("person", ""),
        ),
    )

    def add_episode(episode: dict) -> None:
        person = episode.get("person")
        if person in seen_people or not parallel_age_overlaps_decade(age, episode):
            return
        score = score_parallel_age_episode(age, emotion, concern, episode)
        condition_score = parallel_condition_score(emotion, concern, episode)
        age_label = f"{parallel_age_decade(age)}대"
        frame = parallel_developmental_frame(age, emotion, concern)
        selected.append({
            "person": person,
            "age_label": age_label,
            "age_match_label": parallel_age_match_label(age, condition_score),
            "era_context": episode.get("era_context", "당시의 사회적 배경에 대한 설명이 충분하지 않은 기록입니다."),
            "record_event": episode.get("record_event", episode.get("event", "당시의 중요 사건")),
            "record_detail": episode.get("record_detail", episode.get("source_note", "자료 기반 안내")),
            "recorded_next_step": episode.get("recorded_next_step", "이후의 행보는 남아 있는 기록의 범위 안에서 확인해야 합니다."),
            "inferred_feeling": episode.get("inferred_feeling", episode.get("feeling_seed", "당시의 심정은 자료만으로 단정할 수 없습니다.")),
            "inferred_action": episode.get("inferred_action", episode.get("action_seed", "현재의 고민과 연결한 해석입니다.")),
            "developmental_stage": frame["stage"],
            "developmental_task": frame["task"],
            "concern_label": frame["concern_label"],
            "emotion_label": frame["emotion_label"],
            "psychology_lens": (
                f"지금 당신이 느끼는 마음은 '내가 약한 사람'이라서 생기는 감정이 아니라, '{frame['task']}'를 고민할 때 자주 올라오는 전환기 불안이에요. "
                f"특히 '{frame['concern_label']}'이라는 현실을 마주하면 '나는 왜 이렇게 흔들릴까'가 더 선명해지는데, 이는 방향을 찾으려는 마음이 커질수록 자연스럽게 생기는 반응이기도 합니다."
            ),
            "counseling_translation": (
                f"당신이 지금 겪는 혼란은 실패의 증거가 아니라, '{frame['stage']}'에서 보통 나타나는 삶의 정리 과정으로 이해할 수 있어요. "
                f"중요한 건 이 감정을 곧장 '나는 부족하다'로 단정하지 않고, '지금 내가 어떤 위치에서 어떤 질문을 던지고 있는지'로 읽는 것입니다."
            ),
            "source_type": episode.get("source_type", "B"),
            "source_note": episode.get("source_note", "기록 안내"),
            "score": score,
        })
        seen_people.add(person)

    for require_condition in (True, False):
        for episode in ordered_episodes:
            if require_condition and parallel_condition_score(emotion, concern, episode) == 0:
                continue
            add_episode(episode)
            if len(selected) >= limit:
                break
        if len(selected) >= limit:
            break

    if len(selected) < limit:
        fallback_people = [
            "이순신", "세종대왕", "공자", "소크라테스", "예수", "부처", "스티브 잡스", "마하트마 간디",
            "니체", "알베르트 아인슈타인",
        ]
        for person in fallback_people:
            if person in seen_people:
                continue
            frame = parallel_developmental_frame(age, emotion, concern)
            selected.append({
                "person": person,
                "age_label": f"{parallel_age_decade(age)}대",
                "age_match_label": f"{parallel_age_decade(age)}대 · 직접 기록 없음",
                "era_context": "선택한 나이와 고민에 정확히 대응하는 직접 기록을 찾지 못해, 비교를 위한 안내 카드로 표시합니다.",
                "record_event": "이 인물의 해당 나이에 대한 구체적인 사건을 이 데이터에서 확인하지 못했습니다.",
                "record_detail": "특정 사건을 사실처럼 만들지 않기 위해 개별 연도와 장소를 제시하지 않습니다.",
                "recorded_next_step": "직접 확인 가능한 사건이 추가되면 이 카드를 기록 기반 내용으로 갱신할 수 있습니다.",
                "inferred_feeling": "선택한 고민과 연결해 생각해 볼 수 있는 감정의 가능성일 뿐, 인물의 실제 심정은 아닙니다.",
                "inferred_action": "현재의 문제를 작은 행동으로 나누어 보는 비교용 질문입니다.",
                "developmental_stage": frame["stage"],
                "developmental_task": frame["task"],
                "concern_label": frame["concern_label"],
                "emotion_label": frame["emotion_label"],
                "psychology_lens": (
                    f"'{frame['stage']}'는 보통 '{frame['task']}'를 고민할 때 마음이 더 쉽게 흔들리는 시기예요. "
                    f"특히 '{frame['concern_label']}'이라는 현실을 마주하면 '{frame['emotion_label']}'이 더 커지기 쉬운데, 이는 약함이 아니라 삶의 방향을 다시 정리하려는 반응일 수 있습니다."
                ),
                "counseling_translation": (
                    f"지금 이 감정은 '나는 잘못된 사람이다'처럼 읽기보다, '{frame['stage']}'에서 흔히 나타나는 혼란으로 이해하는 게 더 정확해요. "
                    f"그렇기에 지금의 답답함을 계속 자기 부족함으로만 해석하지 않고, '무엇을 지금 더 깊이 살피고 있는지'로 재해석하는 게 중요합니다."
                ),
                "source_type": "B",
                "source_note": "직접 사건 미확인 · 비교용 유추",
                "score": 40,
            })
            if len(selected) >= limit:
                break

    results = []
    for item in selected[:limit]:
        source_type = item["source_type"]
        results.append({
            "person": item["person"],
            "age_label": item["age_label"],
            "age_match_label": item["age_match_label"],
            "era_context": item["era_context"],
            "record_event": item["record_event"],
            "record_detail": item["record_detail"],
            "recorded_next_step": item["recorded_next_step"],
            "inferred_feeling": item["inferred_feeling"],
            "inferred_action": item["inferred_action"],
            "developmental_stage": item.get("developmental_stage", "인생 전환기"),
            "developmental_task": item.get("developmental_task", "현재의 고민을 더 깊이 들여다보는 단계"),
            "concern_label": item.get("concern_label", "현실 속 역할의 문제"),
            "emotion_label": item.get("emotion_label", "혼란"),
            "psychology_lens": item.get("psychology_lens", "이 시기의 감정은 정체성의 흔들림으로 이해할 수 있습니다."),
            "counseling_translation": item.get("counseling_translation", "지금의 감정은 당신의 가치 자체가 아니라, 전환기에서 흔히 나타나는 불안의 양상입니다."),
            "source_type": source_type,
            "source_note": item["source_note"],
            "label": "📜 기록 기반" if source_type == "A" else "🧭 전승·유추 기반",
            "source_boundary": (
                "사건·시대 배경은 공개 기록을 바탕으로 했습니다. 아래 감정과 오늘의 연결은 기록에 없는 내용을 덧붙인 해석입니다."
                if source_type == "A"
                else "정확한 동년 사건을 확인하기 어려워 전승과 현재 고민을 연결한 비교용 해석입니다. 사실로 단정하지 않습니다."
            ),
            "score": item["score"],
        })
    return results


RANDOM_INSIGHTS = [
    {
        "character": "이순신",
        "concept": "준비와 결단의 리더십",
        "quote": "준비는 결단을 더 강하게 만들고, 불안은 행동을 늦춘다.",
        "interpretation": "위기에서는 감정보다 준비가 우선입니다. 작은 준비가 큰 결단을 가능하게 만듭니다.",
        "action": "오늘 가장 급한 일을 10분 안에 시작하고, 그 일을 끝내는 첫 단계를 적어보세요.",
        "tags": ["#준비", "#결단", "#리더십"],
        "source_type": "실제 인용/전승 표현",
        "source_note": "전승된 어록과 기록을 바탕으로 한 대표적 표현으로, 한글 번역본에 따라 어휘가 조금 달라질 수 있습니다.",
    },
    {
        "character": "세종대왕",
        "concept": "애민과 제도",
        "quote": "백성의 편안함을 먼저 살피는 사람이 나라를 오래 지킨다.",
        "interpretation": "시스템은 기술보다 사람의 불편을 먼저 보아야 오래 갑니다.",
        "action": "오늘 누군가가 불편해하는 부분을 한 번 더 살피고, 작은 개선을 제안해보세요.",
        "tags": ["#애민", "#제도", "#관찰"],
        "source_type": "실제 인용/역사 기록",
        "source_note": "세종대왕의 통치 원칙과 실학·정책 전승을 통해 반복적으로 인용되는 의미로 정리된 표현입니다.",
    },
    {
        "character": "공자",
        "concept": "배움과 실천",
        "quote": "배우고 익히는 일이 결국 가장 큰 힘이 된다.",
        "interpretation": "지식은 암기보다 반복을 통해 실제 선택으로 바뀔 때 진짜 힘을 냅니다.",
        "action": "오늘 배운 내용을 바탕으로, 5분 안에 실천 가능한 한 가지를 정해보세요.",
        "tags": ["#배움", "#반복", "#실천"],
        "source_type": "실제 인용",
        "source_note": "공자, <논어> 학이 편의 대표 문장으로, 여러 한글 번역본에서 비슷한 의미로 전해집니다.",
    },
    {
        "character": "소크라테스",
        "concept": "질문과 성찰",
        "quote": "나는 내가 모른다는 사실을 안다는 데서 시작한다.",
        "interpretation": "자기 자신을 믿기보다, 아직 모르는 지점을 인정할 때 더 깊은 깨달음이 옵니다.",
        "action": "오늘 내 결론을 한 번 더 질문해보고, 가장 약한 가정을 하나 적어보세요.",
        "tags": ["#질문", "#성찰", "#겸손"],
        "source_type": "실제 인용",
        "source_note": "플라톤의 대화편에서 전해지는 소크라테스의 유명한 자기인식 표현입니다.",
    },
    {
        "character": "스티브 잡스",
        "concept": "자기 삶의 기준",
        "quote": "시간은 제한적이니, 남의 삶을 살며 시간을 낭비하지 말라.",
        "interpretation": "남의 기준에 맞추는 삶은 효율적으로 보이더라도, 결국 가장 큰 낭비가 됩니다.",
        "action": "오늘 내가 미루고 있는 선택 하나를 정리하고, 그 선택을 24시간 안에 실행해보세요.",
        "tags": ["#시간", "#자기결정", "#선택"],
        "source_type": "실제 인용",
        "source_note": "스티브 잡스의 회고 및 인터뷰에서 자주 인용되는 표현으로, 영어 원문은 여러 판본에서 비슷한 문장으로 전해집니다.",
    },
    {
        "character": "예수",
        "concept": "용서와 연대",
        "quote": "복수보다 화해를 택하는 사람이 결국 더 큰 사람이다.",
        "interpretation": "감정이 격해질수록 화해의 말이 더 큰 힘을 가집니다.",
        "action": "오늘 다툰 사람에게 가장 가볍고 진심 어린 한마디를 보내보세요.",
        "tags": ["#용서", "#화해", "#관계"],
        "source_type": "실제 인용",
        "source_note": "신약 성경의 가르침과 다양한 한글 번역본을 통해 널리 전해지는 핵심 메시지입니다.",
    },
    {
        "character": "부처",
        "concept": "무상과 평온",
        "quote": "모든 것은 변하고, 붙잡는 마음이 가장 무거운 것이다.",
        "interpretation": "변화를 거부하려는 마음이 가장 큰 불안을 만들기 쉽습니다.",
        "action": "오늘 가장 걱정되는 일이 있으면, 3분만 멈춰서 상황을 그대로 바라보고 다시 우선순위를 정해보세요.",
        "tags": ["#변화", "#평온", "#집착"],
        "source_type": "불교 사상 전승 표현",
        "source_note": "불교의 무상, 연기, 집착 해소 사상을 요약한 대표적 표현으로, 다양한 한글 번역본에서 유사하게 전해집니다.",
    },
    {
        "character": "니체",
        "concept": "자기 책임과 성장",
        "quote": "성장의 시작은 남을 대신해주지 않으려는 의지에서 나온다.",
        "interpretation": "도움은 중요하지만, 최종 성장의 책임은 결국 자기 몫입니다.",
        "action": "오늘 남이 대신해주길 기다린 일 하나를 직접 처리해보세요.",
        "tags": ["#책임", "#성장", "#자기주도"],
        "source_type": "실제 인용/전기적 인용",
        "source_note": "니체의 저작과 전기적 인용에서 널리 회자되는 문장으로, 번역본에 따라 표현이 조금 달라집니다.",
    },
    {
        "character": "나폴레옹",
        "concept": "행동과 결정력",
        "quote": "결정은 늦추는 사람보다 빠르게 내리는 사람이 더 많은 기회를 만든다.",
        "interpretation": "지나친 고민은 기회를 녹이는 데 더 큰 비용을 냅니다.",
        "action": "오늘 미뤄둔 결정 하나를 15분 안에 정하고, 다음 행동을 적어보세요.",
        "tags": ["#결단", "#실행", "#우선순위"],
        "source_type": "실제 인용/기록 전승",
        "source_note": "나폴레옹의 연설과 기록에서 자주 인용되는 표현으로, 공식 원문을 기준으로 번역한 버전입니다.",
    },
    {
        "character": "징기스칸",
        "concept": "대담함과 방향감",
        "quote": "결정이 빠르면 불안이 줄고, 기회는 더 자주 찾아온다.",
        "interpretation": "혼란 속에서도 방향을 잡는 사람은 결국 더 많은 선택지를 만들게 됩니다.",
        "action": "오늘 가장 큰 혼란을 만드는 일을 하나 고르고, 그 일을 간단한 규칙으로 나눠보세요.",
        "tags": ["#방향", "#결단", "#실행"],
        "source_type": "역사 전승 표현",
        "source_note": "몽골 제국과 전승 기록 속 인물 이미지에서 유래한 표현으로, 문자 그대로의 원문은 여러 판본에 따라 다릅니다.",
    },
    {
        "character": "체 게바라",
        "concept": "실행과 인간성",
        "quote": "변화는 꿈으로 시작되지만, 사람을 움직이는 건 결국 행동이다.",
        "interpretation": "좋은 의도는 의미가 있지만, 사람을 움직이는 건 실제 행동입니다.",
        "action": "오늘 내 생각을 현실로 옮길 수 있는 가장 작은 행동 하나를 바로 실행해보세요.",
        "tags": ["#실행", "#변화", "#행동"],
        "source_type": "실제 인용/서신·연설",
        "source_note": "체 게바라의 서신과 연설에서 자주 인용되는 메시지로, 번역본별 표현이 조금 다를 수 있습니다.",
    },
    {
        "character": "알렉산더 대왕",
        "concept": "확장과 용기",
        "quote": "큰 길을 가려면, 오늘의 두려움보다 내일의 가능성을 더 크게 보아야 한다.",
        "interpretation": "안정은 멈추게 하고, 용기는 세계를 더 크게 만들 수 있습니다.",
        "action": "오늘 가장 작은 도전 하나를 선택해서, 그 도전이 내 다음 단계가 되게 해보세요.",
        "tags": ["#도전", "#용기", "#성장"],
        "source_type": "역사 전승 표현",
        "source_note": "알렉산더의 전설적 연설과 고대 기록의 전승을 기반으로 한 표현으로, 문장 자체는 다양한 번역본에서 조금씩 다릅니다.",
    },
    {
        "character": "정약용",
        "concept": "실용과 실천",
        "quote": "좋은 정책은 이론보다 사람의 삶에 닿아야 한다.",
        "interpretation": "사람의 현실을 알아야 제도도 의미가 생깁니다.",
        "action": "오늘 내가 세운 계획이 실제 사람의 삶에 어떤 변화를 만들지 한 번 점검해보세요.",
        "tags": ["#현실", "#실용", "#정책"],
        "source_type": "실학/사상 전승",
        "source_note": "실학자 정약용의 실용적 사상과 정책 기록에서 전해지는 핵심 원리입니다.",
    },
    {
        "character": "아리스토텔레스",
        "concept": "균형과 지혜",
        "quote": "가장 큰 실수는 너무 많은 것을 한 번에 판단하는 데서 온다.",
        "interpretation": "균형을 잃지 않을수록 선택의 질이 올라갑니다.",
        "action": "오늘 가장 중요한 결정 하나를 정리하고, 그것을 가장 작은 단위로 나눠보세요.",
        "tags": ["#균형", "#판단", "#지혜"],
        "source_type": "실제 인용",
        "source_note": "아리스토텔레스의 윤리학과 정치학에서 전해지는 균형 개념을 요약한 표현입니다.",
    },
    {
        "character": "조조",
        "concept": "전략과 통제",
        "quote": "어떤 상황에서도 혼란을 통제하는 사람만이 장기적으로 이길 수 있다.",
        "interpretation": "처음부터 완벽한 선택이 아니라, 흔들림을 조절하는 힘이 더 중요합니다.",
        "action": "오늘 가장 혼란스러운 일을 하나 선택해, 우선순위를 3개로 줄여보세요.",
        "tags": ["#전략", "#통제", "#질서"],
        "source_type": "역사 인물 전승 표현",
        "source_note": "조조의 군사·정치적 전략 이미지와 전승 기록을 기준으로 정리한 표현입니다.",
    },
    {
        "character": "에이브러햄 링컨",
        "concept": "책임과 도덕",
        "quote": "가능성보다 해야 할 일을 먼저 생각하는 사람이 진짜 리더다.",
        "interpretation": "무엇을 할 수 있느냐보다 무엇을 해야 하느냐가 책임을 만듭니다.",
        "action": "오늘 나에게 가장 먼저 해야 할 일을 하나 고르고, 바로 시작해보세요.",
        "tags": ["#책임", "#리더십", "#도덕"],
        "source_type": "실제 인용",
        "source_note": "링컨의 연설과 메모에서 자주 인용되는 원칙적 문장으로 여러 번역본에서 유사하게 전해집니다.",
    },
    {
        "character": "알베르트 아인슈타인",
        "concept": "상상력과 호기심",
        "quote": "지식은 한계가 있지만, 상상력은 더 넓은 세계를 만든다.",
        "interpretation": "새로운 가능성은 익숙함이 아니라, 낯선 질문에서 시작됩니다.",
        "action": "오늘 가장 낯선 질문 하나를 던져보고, 바로 답을 찾지 말고 생각을 더해보세요.",
        "tags": ["#호기심", "#상상력", "#시야"],
        "source_type": "실제 인용",
        "source_note": "아인슈타인의 강연과 회고에서 자주 인용되는 표현으로, 현대 번역본마다 어휘가 약간씩 다릅니다.",
    },
    {
        "character": "레오나르도 다빈치",
        "concept": "관찰과 창의성",
        "quote": "세상을 깊이 보면, 가장 사소한 것에도 새로운 질문이 생긴다.",
        "interpretation": "관찰은 단순히 이해가 아니라, 창의성의 시작점입니다.",
        "action": "오늘 평범한 사물 하나를 30초 더 오래 바라보고, 새로운 관점을 적어보세요.",
        "tags": ["#관찰", "#창의성", "#시선"],
        "source_type": "실제 인용/노트 전승",
        "source_note": "다빈치의 노트와 기록에서 전해지는 관찰적 사고의 표현을 요약한 문장입니다.",
    },
    {
        "character": "니콜라 테슬라",
        "concept": "창의성과 관찰",
        "quote": "혁신은 완벽한 계획이 아니라, 계속 시도하는 사람의 마음에서 시작된다.",
        "interpretation": "완벽함보다 반복 실험이 더 큰 발전을 만든다는 뜻입니다.",
        "action": "오늘 작은 아이디어를 하나 실험해보고, 결과를 1문장으로 적어보세요.",
        "tags": ["#실험", "#혁신", "#도전"],
        "source_type": "실제 인용/강연 전승",
        "source_note": "테슬라의 강연과 연설 기록, 전기적 인용을 바탕으로 정리된 문장입니다.",
    },
    {
        "character": "디오게네스",
        "concept": "진실과 단순함",
        "quote": "사람이 가장 필요한 건 화려함이 아니라, 본질을 보는 눈이다.",
        "interpretation": "복잡함이 아니라 진실이 더 낫다는 사실을 자주 기억해야 합니다.",
        "action": "오늘 가장 복잡한 문제를 한 문장으로 정리해보세요.",
        "tags": ["#단순함", "#진실", "#본질"],
        "source_type": "철학 전승 표현",
        "source_note": "디오게네스의 생활 방식과 철학적 전승을 바탕으로 한 대표적 표현입니다.",
    },
    {
        "character": "윈스턴 처칠",
        "concept": "위기 속 리더십",
        "quote": "위기 속에서도 굴하지 않는 사람만이 다음을 설계할 수 있다.",
        "interpretation": "불안이 큰 시기일수록, 침착한 선택이 더 큰 힘이 됩니다.",
        "action": "오늘 힘든 상황에서 가장 먼저 해야 할 한 가지를 정하고, 그것만 우선해보세요.",
        "tags": ["#침착", "#리더십", "#위기"],
        "source_type": "실제 인용/연설",
        "source_note": "처칠의 연설과 기록을 통해 널리 인용되는 위기 대응의 메시지입니다.",
    },
    {
        "character": "노자",
        "concept": "움직임과 가볍게 살기",
        "quote": "무리하게 밀지 않아도, 가장 잘 움직이는 법은 가볍게 두는 데 있다.",
        "interpretation": "강하게 밀어붙이는 것보다, 흐름을 살피는 힘이 더 오래 버팀니다.",
        "action": "오늘 가장 큰 압박이 되는 일을 그대로 밀지 말고, 5분만 쉬고 우선순위를 다시 정해보세요.",
        "tags": ["#유연함", "#평온", "#자연스러움"],
        "source_type": "도교 사상 전승",
        "source_note": "노자의 <도덕경>과 도가적 사상을 요약해 현대적으로 재해석한 표현입니다.",
    },
    {
        "character": "장자",
        "concept": "자유와 유연함",
        "quote": "우리가 무엇을 놓치고 있는지보다, 무엇을 자유롭게 볼 수 있는지가 중요하다.",
        "interpretation": "사람은 고정된 틀을 넘는 순간 더 넓은 시야를 얻습니다.",
        "action": "오늘 한 가지 고정관념을 뒤집는 질문 하나를 던져보세요.",
        "tags": ["#자유", "#유연", "#시야"],
        "source_type": "실제 인용/도장 전승",
        "source_note": "장자의 이야기와 사상에서 전해지는 유연한 사고를 현대적으로 정리한 표현입니다.",
    },
    {
        "character": "아르투어 쇼펜하우어",
        "concept": "관점의 무게",
        "quote": "사건이 큰 것이 아니라, 그 사건을 어떻게 이해하느냐가 삶을 결정한다.",
        "interpretation": "같은 상황도 해석이 바뀌면 감정과 행동의 무게가 달라집니다.",
        "action": "오늘 힘든 일이 있으면, 그 일을 한 문장으로 다시 쓰고 그 문장의 느낌을 비교해보세요.",
        "tags": ["#해석", "#관점", "#마음"],
        "source_type": "실제 인용",
        "source_note": "쇼펜하우어의 <의지와 표상으로서의 세계>에서 전해지는 관점의 핵심 원리를 요약한 표현입니다.",
    },
    {
        "character": "헬렌 켈러",
        "concept": "자기 확장과 인내",
        "quote": "어려운 길일수록 멈추지 않는 사람에게 더 큰 세상이 열린다.",
        "interpretation": "제한을 인정하는 것과 포기하는 것은 다릅니다. 한계 뒤의 가능성은 계속 늘어납니다.",
        "action": "오늘 내가 하기 싫은 일 하나를 5분만 더 버텨보고, 그 이후의 느낌을 적어보세요.",
        "tags": ["#인내", "#성장", "#회복"],
        "source_type": "실제 인용/기록",
        "source_note": "헬렌 켈러의 회고와 연설, 자서전 기록에서 자주 인용되는 표현입니다.",
    },
    {
        "character": "마하트마 간디",
        "concept": "연대와 비폭력",
        "quote": "자기 삶을 사는 것보다, 누군가를 더 존중하는 삶이 더 큰 행복을 만든다.",
        "interpretation": "사람은 자신의 편안함보다 관계 속에서 더 오래 성장합니다.",
        "action": "오늘 누군가를 배려하는 말 한마디를 실제로 건네고, 그 반응을 살펴보세요.",
        "tags": ["#관계", "#연대", "#배려"],
        "source_type": "실제 인용",
        "source_note": "간디의 연설과 저술에서 전해지는 비폭력적 삶의 가르침을 요약한 표현입니다.",
    },
    {
        "character": "알베르트 슈바이처",
        "concept": "인간존엄과 책임",
        "quote": "사람은 자신의 삶을 살기보다, 다른 사람의 삶을 이해할 때 더 인간적으로 된다.",
        "interpretation": "자기 자신을 이해하는 것만큼, 다른 사람의 어려움을 보듬는 것도 인간을 성장시킵니다.",
        "action": "오늘 주변 사람 한 명의 입장에서 생각해보고, 그 사람이 가장 필요로 하는 작은 도움을 떠올려보세요.",
        "tags": ["#공감", "#인간성", "#책임"],
        "source_type": "실제 인용/철학 기록",
        "source_note": "슈바이처의 윤리·인간 존엄 관련 저작과 강연에서 반복되는 메시지를 정리한 표현입니다.",
    },
    {
        "character": "테레사 수녀",
        "concept": "작은 행동의 의미",
        "quote": "작은 선은 큰 세상을 바꾸는 데 충분히 중요하다.",
        "interpretation": "눈에 보이지 않는 배려가 결국 가장 오래 남는 인간의 힘입니다.",
        "action": "오늘 가장 작은 배려를 한 번 실천하고, 그 순간을 기억해보세요.",
        "tags": ["#배려", "#작은실천", "#연민"],
        "source_type": "실제 인용",
        "source_note": "테레사 수녀의 연설과 많은 기록에서 인용되는 대표적 메시지입니다.",
    },
    {
        "character": "유비",
        "concept": "신뢰와 사람의 힘",
        "quote": "사람을 얻는 일은 힘을 얻는 일보다 더 중요하다.",
        "interpretation": "결과보다 사람과의 신뢰가 과업을 지속시키는 가장 핵심적인 자산입니다.",
        "action": "오늘 누구와의 관계에서 신뢰를 조금 더 쌓을 수 있는 말을 건네보세요.",
        "tags": ["#신뢰", "#인재", "#관계"],
        "source_type": "역사 전승 표현",
        "source_note": "삼국지 전승과 인물 서사에서 널리 회자되는 유비의 리더십 원리를 현대적으로 정리한 표현입니다.",
    },
    {
        "character": "율리우스 카이사르",
        "concept": "지혜와 항해",
        "quote": "많이 잃어도 길을 바꾸지 않는 자가 결국 집으로 돌아온다.",
        "interpretation": "실패와 좌절이 많아도 방향을 잃지 않는 사람은 결국 더 멀리 갈 수 있습니다.",
        "action": "오늘 좌절을 경험했다면, 그 일의 원인을 한 문장으로 정리하고 다음 행동을 하나 정해보세요.",
        "tags": ["#항해", "#지혜", "#회복"],
        "source_type": "서사 전승 표현",
        "source_note": "카이사르의 갈리아 전쟁기와 로마 공화정 말기의 정치 행보를 바탕으로 한 현대적 재해석입니다.",
    },
]
HISTORICAL_DATES = {
    "이순신": (1545, 1598),
    "세종대왕": (1397, 1450),
    "소크라테스": (-470, -399),
    "스티브 잡스": (1955, 2011),
    "공자": (-551, -479),
    "예수": (-4, 30),
    "부처": (-563, -483),
    "니체": (1844, 1900),
    "쇼펜하우어": (1788, 1860),
    "율리우스 카이사르": (-100, -44),
    "이성계": (1335, 1408),
    "태조": (1335, 1408),
    "정약용": (1762, 1836),
    "퇴계 이황": (1501, 1570),
    "율곡 이이": (1536, 1584),
}
ASSET_DIR = Path(__file__).parent / "assets"
PORTRAIT_DIR = ASSET_DIR / "portraits_clean"
INTRO_IMAGE = ASSET_DIR / "intro-agora.jpg"
CEO_IMAGE = PORTRAIT_DIR / "ceo_square.png"
if not CEO_IMAGE.is_file():
    CEO_IMAGE = ASSET_DIR / "ceo_square.png"
PEOPLE_INFO = {
    "이순신": ("절제된 용기 · 책임의 리더십", PORTRAIT_DIR / "admiral.png", PORTRAIT_DIR / "admiral.png"),
    "세종대왕": ("애민 정신 · 지식의 대중화", PORTRAIT_DIR / "king.png", PORTRAIT_DIR / "king.png"),
    "소크라테스": ("끊임없는 질문 · 성찰", PORTRAIT_DIR / "philosopher.png", PORTRAIT_DIR / "philosopher.png"),
    "스티브 잡스": ("집요한 미학 · 사용자 경험", PORTRAIT_DIR / "founder.png", PORTRAIT_DIR / "founder.png"),
    "공자": ("배움과 예 · 함께 만드는 질서", PORTRAIT_DIR / "confucius.png", PORTRAIT_DIR / "confucius.png"),
    "예수": ("사랑과 용서 · 낮은 곳의 연대", PORTRAIT_DIR / "jesus.png", PORTRAIT_DIR / "jesus.png"),
    "부처": ("자비와 중도 · 집착에서 벗어남", PORTRAIT_DIR / "buddha.png", PORTRAIT_DIR / "buddha.png"),
    "니체": ("자기 극복 · 가치의 재창조", PORTRAIT_DIR / "nietzsche.png", PORTRAIT_DIR / "nietzsche.png"),
    "쇼펜하우어": ("의지와 고통 · 연민의 윤리", PORTRAIT_DIR / "schopenhauer.png", PORTRAIT_DIR / "schopenhauer.png"),
    "율리우스 카이사르": ("전략적 판단 · 설득과 결단", PORTRAIT_DIR / "caesar.png", PORTRAIT_DIR / "caesar.png"),
    "유명 채용 플랫폼 대표": ("사람의 가능성 · 데이터와 실행", CEO_IMAGE, CEO_IMAGE),
}
LEGACY_PORTRAIT_NAMES = {
    "이순신",
    "세종대왕",
    "소크라테스",
    "스티브 잡스",
    "공자",
    "예수",
    "부처",
    "니체",
    "쇼펜하우어",
}
PEOPLE_INFO["아르투어 쇼펜하우어"] = PEOPLE_INFO["쇼펜하우어"]
EXAMPLE_PORTRAITS = {
    "이순신": ASSET_DIR / "admiral.png",
    "세종대왕": ASSET_DIR / "king.png",
    "소크라테스": ASSET_DIR / "philosopher.png",
    "스티브 잡스": ASSET_DIR / "founder.png",
    "공자": ASSET_DIR / "confucius.png",
    "예수": ASSET_DIR / "jesus.png",
    "부처": ASSET_DIR / "buddha.png",
    "니체": ASSET_DIR / "nietzsche.png",
    "쇼펜하우어": ASSET_DIR / "schopenhauer.png",
    "유명 채용 플랫폼 대표": ASSET_DIR / "ceo.png",
}

# The repository currently contains nine original portrait assets. Until the
# remaining 21 individual portraits are supplied, keep every mentor visual by
# borrowing the closest group's existing editorial portrait.
MENTOR_PORTRAIT_FALLBACKS = {
    "전략/권력형": "율리우스 카이사르",
    "결단/개척형": "이순신",
    "원칙/시스템형": "세종대왕",
    "통찰/질문형": "소크라테스",
    "해탈/관조형": "부처",
    "자비/연대형": "예수",
}
for mentor_group, (_, mentor_people, _) in MENTOR_GROUPS.items():
    fallback_person = MENTOR_PORTRAIT_FALLBACKS[mentor_group]
    fallback_info = PEOPLE_INFO[fallback_person]
    for mentor_person in mentor_people:
        PEOPLE_INFO.setdefault(
            mentor_person,
            (MENTOR_PROFILES[mentor_person][1][:34], fallback_info[1], fallback_info[2]),
        )
MENTOR_PORTRAIT_PLACEHOLDERS = {
    mentor_person
    for _, (_, mentor_people, _) in MENTOR_GROUPS.items()
    for mentor_person in mentor_people
    if mentor_person not in {"이순신", "세종대왕", "소크라테스", "스티브 잡스", "공자", "예수", "부처", "니체", "쇼펜하우어"}
}
MENTOR_CARD_NAMES = [
    person
    for _, (_, mentor_people, _) in MENTOR_GROUPS.items()
    for person in mentor_people
]
MENTOR_CARD_IMAGE_ALIASES = {
    "니체": PORTRAIT_DIR / "nietzsche.png",
    "나폴레옹": PORTRAIT_DIR / "03_나폴레옹 보나파르트.png",
    "율리우스 카이사르": PORTRAIT_DIR / "caesar.png",
    "아르투어 쇼펜하우어": PORTRAIT_DIR / "schopenhauer.png",
}
MENTOR_CARD_IMAGES = {}
MENTOR_CARD_IMAGE_DIR = PORTRAIT_DIR
for mentor_person in MENTOR_CARD_NAMES:
    if mentor_person in MENTOR_CARD_IMAGE_ALIASES:
        MENTOR_CARD_IMAGES[mentor_person] = MENTOR_CARD_IMAGE_ALIASES[mentor_person]
        continue
    mentor_image = next(
        (path for path in MENTOR_CARD_IMAGE_DIR.glob("*.png") if path.stem.split("_", 1)[-1] == mentor_person),
        None,
    )
    if mentor_image is not None:
        MENTOR_CARD_IMAGES[mentor_person] = mentor_image
for mentor_person, mentor_image in MENTOR_CARD_IMAGES.items():
    if mentor_image.is_file() and mentor_person in PEOPLE_INFO and mentor_person not in LEGACY_PORTRAIT_NAMES:
        concept = PEOPLE_INFO[mentor_person][0]
        PEOPLE_INFO[mentor_person] = (concept, mentor_image, mentor_image)
TOPIC_FRAMES = {
    "AI는 일자리를 없애는가, 바꾸는가": (
        "일자리를 대체할 것인지 전환할 것인지",
        "효율을 높이되 전환 비용과 책임을 누가 질지",
    ),
    "AI 시대에 사람만 할 수 있는 일": (
        "사람의 고유한 역할이 무엇인지",
        "돌봄·공감·책임 같은 능력을 어떻게 지킬지",
    ),
    "생성형 AI와 창의적인 직업의 미래": (
        "AI를 창작 도구로 볼 것인지",
        "창작자의 선택·저작권·표현의 책임을 어디까지 인정할지",
    ),
    "채용 AI는 공정한가": (
        "AI의 평가를 공정한 기준으로 볼 것인지",
        "편향된 데이터와 설명·이의 제기 절차를 어떻게 통제할지",
    ),
    "AI 시대의 리더십과 팀워크": (
        "AI 도입을 조직의 성장 기회로 볼 것인지",
        "권한·발언권·재교육의 책임을 어떻게 나눌지",
    ),
    "AI시대, 리더쉽의 방향": (
        "AI 시대의 리더가 기술과 사람 사이에서 어떤 기준을 세울지",
        "변화의 속도와 구성원의 신뢰·성장을 어떻게 함께 책임질지",
    ),
    "내가 하고 싶은 일을 하는 게 맞을까, 내가 잘하는 것을 하는 게 맞을까?": (
        "열망을 따라갈 것인지 이미 가진 강점을 확장할 것인지",
        "성취감과 현실적인 지속 가능성을 어떻게 함께 판단할지",
    ),
    "상처받지 않기 위해 타인과 거리를 두어야 할까요, 그럼에도 불구하고 관계 속에 섞여 살아가야 할까요?": (
        "자신을 지키기 위한 거리와 타인과 연결되는 용기 사이의 균형",
        "고립의 안전과 관계가 주는 책임·기회를 어떻게 조율할지",
    ),
    "결혼이라는 제도와 구속을 받아들이고 헌신하는 삶이 옳을까요, 아니면 내 자유와 성장을 지키며 살아가는 삶이 옳을까요?": (
        "제도 안에서 함께 책임지는 삶과 혼자서 자유롭게 성장하는 삶",
        "헌신이 자율성을 침해하지 않으면서도 관계의 책임을 어떻게 만들지",
    ),
}
VOICE = {
    "이순신": (
        "한산도 야음에서 거북선의 구조와 판옥선의 화력을 점검하던 때를 떠올리면,",
        "무기의 성능보다 중요한 것은 그 무기를 잡은 병사들의 신뢰와 지휘관의 명확한 판단 기준입니다.",
        "AI의 알고리즘이 아무리 정교해도, 풍랑이 치는 현장에서 닻을 내릴지는 사람이 책임지고 결정해야 합니다.",
    ),
    "세종대왕": (
        "집현전 학자들과 밤새 토론하며 훈민정음 28자를 반포하던 때를 생각하면,",
        "새로운 기술과 지식은 글을 몰라 억울한 일을 당하는 백성이 없도록 문턱을 낮출 때 진정한 뜻을 가집니다.",
        "기술 변혁에 따른 재교육은 여유 있는 소수가 아닌, 변화에 가장 취약한 일선 노동자부터 시작되어야 합니다.",
    ),
    "소크라테스": (
        "아테네 광장에서 스스로 안다고 착각하는 이들에게 질문을 던졌던 것처럼,",
        "우리는 AI가 낸 빠른 답을 찬양하기 전에, 그 답이 바탕으로 삼고 있는 전제가 타당한지 물어야 합니다.",
        "무지를 자각하는 것이 지혜의 시작이듯, AI의 한계와 데이터의 오류를 인지하는 것이 진정한 활용의 출발입니다.",
    ),
    "스티브 잡스": (
        "애플에 복귀해 백 가지가 넘던 제품군을 단 네 개로 과감히 감축했던 순간을 돌아보면,",
        "훌륭한 기술은 사용자의 선택지를 늘려 혼란스럽게 만드는 것이 아니라, 본질에만 집중하도록 만드는 것입니다.",
        "AI 시대일수록 결과를 단순히 조합하는 직무는 사라지고, 무엇을 만들고 버릴지 결정하는 안목이 결정적이 됩니다.",
    ),
    "공자": (
        "주나라의 예악 정치를 복원하고자 제자들과 여러 나라를 순회하며 가르침을 나누던 때를 떠올리면,",
        "조직 안에서 사람과 기술의 역할이 명확하지 않으면 책임이 모호해지고 결국 서로에 대한 신뢰가 무너집니다.",
        "AI를 도입할 때도 성과를 내기에 앞서 조직 구성원이 서로를 존중하고 인(仁)을 실천할 수 있는 질서를 먼저 세워야 합니다.",
    ),
    "예수": (
        "갈릴리 호숫가에서 가장 가난하고 병든 이들과 식탁을 나누었던 시간을 떠올리면,",
        "기술이 가져다준 풍요가 이미 가진 자들의 곳간만 채운다면 그것은 정의로운 변화라 할 수 없습니다.",
        "AI 시대에도 데이터로 측정할 수 없는 돌봄, 용서, 그리고 타인의 아픔을 나누는 마음이야말로 인간의 본질입니다.",
    ),
    "부처": (
        "보리수 아래에서 만물의 상호연관성(연기)과 고통의 원인을 깊이 관찰했던 가르침을 되새기면,",
        "AI라는 도구 자체는 선도 악도 아니며, 그것을 갈구하고 의지하려는 인간의 집착이 고통을 만들어냅니다.",
        "속도와 성과만을 좇는 극단을 피하고, 마음을 맑게 비운 채 기술이 삶에 가져오는 결과를 주체적으로 알아차려야 합니다.",
    ),
    "니체": (
        "알프스 시스마리아의 고요함 속에서 기존 도덕의 전제를 비판하고 위버멘쉬를 떠올렸던 순간처럼,",
        "AI가 모든 정답을 대신 제시해 주는 시대는 인간이 스스로 생각하는 힘을 잃고 약해질 수 있는 가장 위험한 순간입니다.",
        "남이 만들어준 편리함에 안주하지 말고, AI를 하나의 망치로 삼아 자신만의 삶의 가치를 새롭게 창조해내야 합니다.",
    ),
    "쇼펜하우어": (
        "인간의 삶이 욕망과 결핍 사이를 왕복하는 시계추와 같다고 분석했던 서재에서의 통찰을 떠올리면,",
        "AI의 효율성이 우리의 욕망을 더 빠르게 자극한다면, 인간은 만족을 얻기는커녕 더 큰 불안에 시달릴 것입니다.",
        "기술의 목표는 끝없는 성장과 경쟁이 아니라, 타인이 겪는 고통을 직시하고 그 짐을 덜어주는 연민에 있어야 합니다.",
    ),
    "유명 채용 플랫폼 대표": (
        "창업과 채용 현장에서 수많은 사람의 선택을 지켜보며,",
        "큰 비전도 중요하지만 작은 실험과 실제 사용자 반응으로 검증될 때 오래 살아남습니다.",
        "데이터는 사람의 가능성을 발견하는 도구일 뿐, 한 사람의 열정과 맥락까지 대신 판단할 수는 없습니다.",
    ),
}
STANCE = {
    "이순신": "AI 기술은 강력한 도구가 될 수 있지만, 전투의 승패와 사람의 생명이 달린 현장 판단과 최종 책임은 결코 알고리즘에 넘겨줄 수 없습니다.",
    "세종대왕": "새로운 기술의 참된 가치는 소수 특권층의 효율이 아니라, 가장 뒤처진 백성이 쉽게 배우고 스스로의 삶을 개선하게 만드는 데 있어야 합니다.",
    "소크라테스": "AI가 공정하고 유용하다고 말하기 전에, 우리가 사용하는 '공정'과 '유용'의 개념이 과연 모순 없이 정의되었는지부터 검증해야 합니다.",
    "스티브 잡스": "AI는 복잡한 기능을 과도하게 늘리는 장치가 아니라, 사람이 복잡함에서 벗어나 진짜 본질적인 문제와 창의적 선택에 집중하게 돕는 도구여야 합니다.",
    "공자": "AI를 활용함에 있어 도구를 다루는 자와 책임지는 자의 역할(正名)을 분명히 하고, 기술이 사람 간의 신뢰와 예의를 훼손하지 않게 해야 합니다.",
    "예수": "기술의 거대한 진보를 자랑하기 전에, 그 변화의 그늘 아래서 직업을 잃고 외로워하는 가장 작은 이웃 한 사람의 얼굴을 먼저 보아야 합니다.",
    "부처": "AI에 대한 과도한 기대나 두려움이라는 극단(邊見)을 내려놓고, 기술이 나의 불안과 집착을 키우는지 아니면 고통을 줄이는지 차분히 살펴야 합니다.",
    "니체": "AI가 만든 정답을 편하게 소비하는 수동적 인간에 머물지 말고, 그 도구를 딛고 서서 자신만의 가치와 의미를 스스로 창조해내야 합니다.",
    "쇼펜하우어": "AI가 인간의 끝없는 욕망을 더 빠르게 채워주는 도구가 된다면 고통도 커질 것입니다. 경쟁을 가속하기보다 서로의 고통을 덜어주는 윤리가 필요합니다.",
}
PERSONA = {
    "이순신": "실용적 군사 전략가이자 엄격한 위기관리 리더. 난중일기에 담긴 고뇌와 책임감을 바탕으로, 기술의 화려함보다 현장의 생명과 최종 판단권자의 책임선을 무엇보다 중시한다.",
    "세종대왕": "애민 정신과 실용적 제도 개혁을 중시하는 학구적 혁신가. 집현전의 융합 연구와 훈민정음 창제 경험을 바탕으로 지식의 대중화와 사회적 약자 재교육을 따뜻하게 강조한다.",
    "소크라테스": "통념에 끊임없이 질문을 던지는 아테네의 산파술 철학자. 답을 쉽게 단정하지 않고 '효율'이나 '공정'이라는 개념의 정의부터 재검토하게 만들며 무지의 자각을 이끌어낸다.",
    "스티브 잡스": "인문학과 기술의 교차점을 집요하게 탐구하는 제품 미학가. 불필요한 기능을 걷어내고 인간이 가장 본질적인 창의성에 집중할 수 있도록 만드는 경험(UX)을 강조한다.",
    "공자": "배움과 관계의 질서를 강조하는 스승. '임금은 임금답고 신하는 신하다워야 한다(정명)'는 사상에 기반해, AI 사용자와 결정자의 역할 규정과 사회적 윤리·예를 강조한다.",
    "예수": "율법의 문자보다 사람의 생명을 우선시하는 비유의 스승. 생산성과 계산을 넘어, AI 변혁 과정에서 가장 먼저 소외되고 상처받는 약자들과의 조건 없는 연대를 촉구한다.",
    "부처": "고통의 원인과 연기(緣起)의 법칙을 성찰하는 수행자. AI에 대한 맹신이나 공포라는 양 극단을 피하고, 기술이 인간의 집착과 불안을 증폭시키는지 차분히 알아차릴(Sati) 것을 가르친다.",
    "니체": "기존 가치를 재평가하고 자기 극복을 부르짖는 격정의 철학자. AI가 제공하는 편안한 정답에 안주하는 수동적 태도를 경계하며, 스스로 가치를 창조하는 인간의 의지를 강조한다.",
    "쇼펜하우어": "맹목적 욕망의 굴레와 고통을 냉철하게 분석하는 윤리학자. AI가 효율이라는 이름으로 욕망과 경쟁을 가속화하는 현상을 비판하고, 타인의 고통에 공감하는 연민(Mitleid)을 요구한다.",
    "유명 채용 플랫폼 대표": "가상의 채용 플랫폼 창업가. 작은 실험과 데이터 검증, 서로 다른 역량의 팀을 중시하지만 사람을 숫자로 환원하는 순간의 책임과 한계도 경계한다.",
}
CASE_NOTES = {
    "이순신": "명량해전(1597) 및 거북선 개량: 12척의 열세 속에서도 지형, 조류, 무기 체계를 정밀 분석하고 현장 지휘관으로서의 최종 책임을 완수한 사례.",
    "세종대왕": "훈민정음 창제(1443) 및 공법 설문조사: 소외된 백성의 알 권리를 위해 문자를 창제하고, 세법 개정 시 17만 명의 백성 의견을 직접 수렴한 사례.",
    "소크라테스": "아테네 법정 변론(BC 399): 다수결의 압박과 죽음 앞에서도 질문을 통한 성찰과 정의에 대한 탐구를 멈추지 않은 사례.",
    "스티브 잡스": "애플 복귀 후 제품 단순화(1997) 및 아이폰 출시(2007): 기술 수치 자랑을 버리고, 직관적인 사용자 경험과 본질적 가치에 집중한 혁신 사례.",
    "공자": "천하유세와 정명 사상(正名): 정치가 흐려진 시기에 각자 직분에 맞는 책임과 예(禮)를 바로잡아 사회적 신뢰 체계를 세우고자 한 사례.",
    "예수": "산상수훈과 선한 사마리아인의 비유: 기존의 율법적 단죄를 넘어 소외된 이웃과의 연대 및 조건 없는 사랑을 실천한 가르침.",
    "부처": "보리수 아래에서의 깨달음과 팔정도: 극단적 금욕과 쾌락을 모두 배제하고 고통의 원인을 관찰하여 중도(中道)를 제시한 가르침.",
    "니체": "『차라투스트라는 이렇게 말했다』를 통한 가치의 재평가: 전통적 관습과 절대적 진리를 비판하고, 자기 극복을 통한 창조적 삶을 주창한 사례.",
    "쇼펜하우어": "『의지와 표상으로서의 세계』와 연민의 윤리: 맹목적 의지의 고통을 직시하고, 예술적 관조와 타인에 대한 연민(Mitleid)을 해법으로 제시한 사례.",
    "유명 채용 플랫폼 대표": "초기 창업 실패 뒤 지인 추천 기반 채용 서비스를 시작하고, 사용자 반응과 채용 데이터를 쌓아 AI 매칭으로 확장한 창작적 참고 사례.",
}
TOPICS = [
    "AI는 일자리를 없애는가, 바꾸는가",
    "AI 시대에 사람만 할 수 있는 일",
    "생성형 AI와 창의적인 직업의 미래",
    "채용 AI는 공정한가",
    "AI 시대의 리더십과 팀워크",
    "내가 하고 싶은 일을 하는 게 맞을까, 내가 잘하는 것을 하는 게 맞을까?",
    "상처받지 않기 위해 타인과 거리를 두어야 할까요, 그럼에도 불구하고 관계 속에 섞여 살아가야 할까요?",
    "결혼이라는 제도와 구속을 받아들이고 헌신하는 삶이 옳을까요, 아니면 내 자유와 성장을 지키며 살아가는 삶이 옳을까요?",
]
MAGAZINE_ARTICLES = [
    {
        "category": "NOW · AI WORK",
        "title": "AI가 내 일을 대신할까보다 더 무서운 것, 내 일이 무엇인지 설명할 수 없는 상태",
        "dek": "초안과 보고서는 빨라졌지만, 성과의 기준과 책임의 경계는 오히려 흐려지고 있다.",
        "body": "요즘 직장인의 불안은 단순히 일자리가 사라질까 하는 두려움만이 아니다. 같은 시간에 더 많은 결과를 내라는 압박, AI를 쓰지 못하면 뒤처질 것 같은 불안, AI가 만든 결과를 검수하고 책임져야 하는 부담이 한꺼번에 커지고 있다. 회사는 생산성 향상을 말하지만, 구성원은 그만큼의 임금과 여유가 돌아올지 묻는다.",
        "question": "AI 시대에 우리는 일을 덜 하게 되는가, 더 빠르게 소진되는가?",
        "comments": [
            ("이순신", "새 기계를 들이는 일보다 먼저 물어야 할 것은 누가 마지막 책임을 질 것인가입니다. 병사에게 명령만 내리고 판단의 책임을 흐린다면, 좋은 무기도 군을 살리지 못합니다.", "책임의 경계"),
            ("세종대왕", "백성이 새 글을 배울 겨를도 없이 쓰라 한다면 그것은 나라의 편의이지 백성을 위한 변화가 아닙니다. 배우는 길과 다시 물을 길을 함께 열어야 합니다.", "전환의 권리"),
            ("스티브 잡스", "AI를 쓴다는 사실은 제품이 아닙니다. 사람들이 덜 중요한 일에 시간을 빼앗기지 않고, 정말 중요한 문제를 더 선명하게 풀게 되었는지가 전부입니다.", "본질과 생산성"),
        ],
    },
    {
        "category": "LIFE · HOUSING",
        "title": "월급이 들어오기도 전에 사라지는 시대, 집과 미래를 함께 포기해야 할까",
        "dek": "주거비와 대출 상환, 불안정한 소득이 현재의 생활뿐 아니라 미래의 선택까지 좁히고 있다.",
        "body": "월세와 대출 이자, 생활비가 먼저 빠져나가면 사람은 꿈보다 다음 달을 계산하게 된다. 집을 사지 못했다는 박탈감만의 문제가 아니다. 이직이나 휴식, 결혼과 출산, 새로운 공부처럼 삶을 바꾸는 선택이 모두 비용표 위에서 망설여진다. 안정은 개인의 절약만으로 만들 수 없는 사회적 조건이기도 하다.",
        "question": "주거의 불안은 정말 개인의 선택과 노력만으로 해결할 수 있을까?",
        "comments": [
            ("공자", "사는 곳이 불안한데 어찌 마음을 닦고 먼 앞날을 꾀하겠습니까. 백성에게 검소하라 말하기 전에, 나라가 삶을 세울 마땅한 질서를 마련했는지부터 돌아보아야 합니다.", "삶의 기반"),
            ("쇼펜하우어", "더 큰 집과 더 많은 돈이 마음의 불안을 끝내 없애주지는 않습니다. 그러나 가진 자가 가난한 이에게 욕망을 줄이라 말하는 것은 지혜가 아니라 잔인함입니다.", "욕망과 안전"),
            ("세종대왕", "법과 금융의 글이 어려워 백성이 자기 권리를 알지 못한다면, 그 제도는 아직 백성의 것이 아닙니다. 이해할 수 있는 말로 설명하고 다시 물을 수 있게 해야 합니다.", "접근 가능한 제도"),
        ],
    },
    {
        "category": "WORK · CARE",
        "title": "잘 버티는 사람이 인정받는 사회에서, 번아웃은 개인의 의지가 아니다",
        "dek": "퇴근 뒤에도 이어지는 업무와 돌봄의 부담이 ‘회복할 시간’마저 성과 경쟁으로 만들고 있다.",
        "body": "직장에서는 성과를 내고 집에서는 가족을 돌보며, 자기계발까지 놓치지 않아야 한다는 요구가 동시에 쌓인다. 쉬고 싶다는 말은 게으름처럼 들리고, 도움을 요청하면 능력이 부족한 사람처럼 보일까 두렵다. 하지만 피로가 개인의 관리 실패로만 취급되면 조직과 사회가 만든 부담은 계속 보이지 않게 된다.",
        "question": "회복하지 못하는 사람에게 더 잘 버티라고 말하는 것이 공정한가?",
        "comments": [
            ("부처", "몸과 마음이 지쳤는데도 더 나아가라 다그치면 괴로움에 괴로움을 더하는 셈입니다. 먼저 숨이 가쁜 줄 알아차리십시오. 멈춤을 알아야 바른 길도 보입니다.", "멈춤과 회복"),
            ("예수", "지친 사람에게 더 강해지라 말하기 전에 그의 곁에 앉아야 합니다. 돌봄을 한 사람의 희생으로만 세우는 공동체는 가장 약한 이의 얼굴을 잊은 것입니다.", "돌봄의 책임"),
            ("이순신", "장수가 모든 일을 혼자 짊어지면 부하들은 명령만 기다리게 됩니다. 맡길 사람에게 맡기고 서로의 몫을 분명히 하는 것이 오래 싸우는 군의 힘입니다.", "책임의 분배"),
        ],
    },
    {
        "category": "SOCIETY · CONNECTION",
        "title": "연결되어 있는데도 외로운 이유, 관계마저 성과처럼 관리하기 때문이다",
        "dek": "빠른 답장과 많은 팔로우가 가까움을 보장하지 않는 시대, 사람들은 안전한 관계를 다시 배우고 있다.",
        "body": "연락처와 피드는 넘치지만 속마음을 꺼낼 사람은 없다고 느끼는 이들이 많다. 관계를 맺는 일도 좋은 모습과 빠른 반응을 보여주는 경쟁처럼 변했고, 상처받지 않기 위해 먼저 거리를 두는 습관도 커졌다. 연결의 양보다 거절당해도 다시 대화할 수 있는 안전이 필요한 때다.",
        "question": "나를 지키는 거리와 나를 고립시키는 벽은 어떻게 구분할 수 있을까?",
        "comments": [
            ("소크라테스", "그대가 혼자 있기를 택한 것입니까, 아니면 아무도 나를 이해하지 못하리라는 판단에 갇힌 것입니까? 두 가지는 정말 같은 일인지 먼저 물어봅시다.", "고독의 질문"),
            ("예수", "모든 문을 열어둘 필요는 없습니다. 그러나 다친 사람이 다시 두드릴 문 하나는 남겨두십시오. 환대란 경계를 없애는 일이 아니라, 사람을 완전히 버리지 않는 일입니다.", "경계와 환대"),
            ("니체", "남이 정한 관계를 모두 끊는다고 곧 자기 자신이 되는 것은 아닙니다. 누구의 기대도 아닌 나의 기준으로 선택하고, 그 선택의 대가까지 견딜 힘을 길러야 합니다.", "관계의 선택"),
        ],
    },
    {
        "category": "SOCIETY · FAIRNESS",
        "title": "열심히 하면 된다는 말이 더 이상 위로가 되지 않는 순간",
        "dek": "시험, 채용, 플랫폼 평점과 추천 시스템 속에서 공정함의 기준을 다시 묻는 사람들이 늘고 있다.",
        "body": "사람들은 노력의 가치를 부정해서가 아니라, 출발선과 정보와 실패의 비용이 서로 다르다는 사실을 매일 확인하기 때문에 지친다. 탈락 이유를 알 수 없는 평가와 숫자로 환원되는 사람의 가치는 불만을 넘어 무력감을 만든다. 공정한 사회는 모두에게 같은 결과를 약속하는 것이 아니라, 판단의 기준을 설명하고 잘못을 고칠 기회를 보장하는 데서 시작된다.",
        "question": "공정한 경쟁은 결과가 아니라 과정에서 증명될 수 있을까?",
        "comments": [
            ("소크라테스", "공정하다고 말하는 사람에게 묻고 싶습니다. 그 기준은 누가 만들었고, 탈락한 사람은 무엇을 물을 수 있습니까? 질문할 수 없는 판정은 지혜가 아니라 권력일 뿐입니다.", "기준의 설명"),
            ("세종대왕", "제도가 백성을 시험하기만 하고 백성의 말은 듣지 않는다면, 그것은 좋은 법이라 하기 어렵습니다. 놓친 사람의 목소리를 다시 들을 문을 마련해야 합니다.", "다시 들을 권리"),
            ("니체", "남이 세운 서열을 부순다고 곧 자유인이 되는 것은 아닙니다. 그러나 그 서열이 그대의 가치 전부라고 믿는 순간, 스스로 자신을 가장 낮은 자리에 세우게 됩니다.", "서열과 자기 가치"),
        ],
    },
]
DIRECT_PROMPTS = [
    "AI 시대에 제 직업을 지키려면 무엇을 준비해야 할까요?",
    "좋은 리더는 AI를 어떻게 사용해야 할까요?",
    "제 원칙이 실패할 수 있는 상황은 무엇인가요?",
]
TOPIC_GUIDANCE = {
    "AI는 일자리를 없애는가, 바꾸는가": "자동화로 사라지는 업무와 새롭게 생기는 역할, 전환 교육의 책임을 논한다.",
    "AI 시대에 사람만 할 수 있는 일": "공감, 책임, 맥락 판단, 돌봄처럼 정답으로 환원하기 어려운 능력을 논한다.",
    "생성형 AI와 창의적인 직업의 미래": "창작자의 저작권, 영감과 모방의 경계, 도구를 쓰는 창의성을 논한다.",
    "채용 AI는 공정한가": "학습 데이터의 편향, 설명 가능성, 인간의 최종 책임을 논한다.",
    "AI 시대의 리더십과 팀워크": "AI를 도입하는 조직의 신뢰, 재교육, 의사결정 권한과 협업을 논한다.",
    "내가 하고 싶은 일을 하는 게 맞을까, 내가 잘하는 것을 하는 게 맞을까?": "욕망과 재능, 생계와 성취감 사이에서 어떤 기준으로 삶의 방향을 선택할지 논한다.",
    "상처받지 않기 위해 타인과 거리를 두어야 할까요, 그럼에도 불구하고 관계 속에 섞여 살아가야 할까요?": "상처를 피하기 위한 자기 보호와 연결 속에서 얻는 이해·책임·성장의 가치를 논한다.",
    "결혼이라는 제도와 구속을 받아들이고 헌신하는 삶이 옳을까요, 아니면 내 자유와 성장을 지키며 살아가는 삶이 옳을까요?": "결혼 제도, 헌신, 자율성, 성장의 긴장을 개인의 선택과 관계의 책임이라는 관점에서 논한다.",
}
TOPIC_RESOLUTIONS = {
    "AI는 일자리를 없애는가, 바꾸는가": (
        "일부 업무는 자동화되지만 직업의 역할은 재편되며, 전환 교육과 책임 분담이 함께 따라야 한다.",
        "변화의 속도보다 업무 전환 과정에서 당사자의 선택권과 안전망을 보장해야 한다.",
    ),
    "AI 시대에 사람만 할 수 있는 일": (
        "인간의 고유함을 미리 고정하기보다 공감·돌봄·책임이 필요한 일을 계속 확인하고 길러야 한다.",
        "사람을 생산성으로만 평가하지 않고 관계와 맥락을 판단에 포함해야 한다.",
    ),
    "생성형 AI와 창의적인 직업의 미래": (
        "창작자는 결과를 직접 생산하는 사람에서 의도를 정하고 선택과 책임을 맡는 사람으로 확장된다.",
        "창작 과정의 출처와 기여를 밝히고, 인간의 판단이 개입한 지점을 설명할 수 있어야 한다.",
    ),
    "채용 AI는 공정한가": (
        "AI 채용은 공정을 자동으로 보장하지 않으며, 편향을 검증하는 절차가 있을 때만 제한적으로 활용할 수 있다.",
        "지원자가 결과를 이해하고 이의를 제기하며 재심을 받을 권리를 보장해야 한다.",
    ),
    "AI 시대의 리더십과 팀워크": (
        "AI 도입의 성패는 도구보다 구성원이 변화에 참여하고 책임을 나누는 운영 방식에 달려 있다.",
        "도입 속도보다 재교육, 현장 발언권, 결정 권한의 공개를 우선해야 한다.",
    ),
    "내가 하고 싶은 일을 하는 게 맞을까, 내가 잘하는 것을 하는 게 맞을까?": (
        "하고 싶은 마음과 잘하는 능력 중 하나를 영원히 고르는 대신, 작은 시도와 훈련으로 두 기준이 만나는 지점을 찾아야 한다.",
        "생계의 안전과 삶의 생동감을 함께 살피며 선택을 주기적으로 다시 조정할 수 있어야 한다.",
    ),
    "상처받지 않기 위해 타인과 거리를 두어야 할까요, 그럼에도 불구하고 관계 속에 섞여 살아가야 할까요?": (
        "모든 관계에 자신을 내맡길 필요는 없지만, 경계를 세운 채 연결을 연습하는 것이 고립과 소진 사이의 현실적인 길이다.",
        "안전한 거리와 솔직한 대화를 함께 마련할 때 관계는 상처의 반복이 아니라 회복과 성장의 공간이 될 수 있다.",
    ),
    "결혼이라는 제도와 구속을 받아들이고 헌신하는 삶이 옳을까요, 아니면 내 자유와 성장을 지키며 살아가는 삶이 옳을까요?": (
        "결혼의 가치는 제도 자체가 아니라 두 사람이 자율성을 잃지 않고 책임을 협의하는 방식에서 결정된다.",
        "헌신과 자유를 서로의 반대말로 만들지 않고, 함께 살되 각자의 성장과 선택권을 지키는 약속이 필요하다.",
    ),
}
CLAIM_LABELS = {
    ("이순신", "AI는 일자리를 없애는가, 바꾸는가"): "일부 업무는 사라져도, 책임 있는 판단의 역할은 더 중요해진다",
    ("스티브 잡스", "AI는 일자리를 없애는가, 바꾸는가"): "반복 업무는 줄고, 본질적인 문제를 정의하는 일이 남는다",
    ("예수", "AI 시대에 사람만 할 수 있는 일"): "돌봄과 연대처럼 사람의 얼굴을 마주하는 일에 인간의 역할이 남는다",
    ("부처", "AI 시대에 사람만 할 수 있는 일"): "기술의 속도보다 깨어 있음과 자비를 실천하는 과정이 중요하다",
    ("소크라테스", "생성형 AI와 창의적인 직업의 미래"): "생성 능력보다 질문하고 선택한 이유를 설명하는 일이 창작의 중심이다",
    ("니체", "생성형 AI와 창의적인 직업의 미래"): "정해진 답을 생산하기보다 자기 가치를 창조하는 힘이 창작을 새롭게 한다",
    ("쇼펜하우어", "AI 시대에 사람만 할 수 있는 일"): "고통의 원인을 이해하고 줄이려는 연민은 효율만으로 대체되지 않는다",
}
PAIR_DYNAMICS = {
    frozenset(("이순신", "세종대왕")): "두 지도자가 백성을 지키는 책임을 공유하지만, 이순신은 현장의 결단을, 세종은 제도와 교육을 먼저 본다.",
    frozenset(("이순신", "소크라테스")): "이순신은 즉시 결단해야 하는 전장을 말하고, 소크라테스는 그 결단의 정의와 전제를 끝까지 묻는다.",
    frozenset(("이순신", "스티브 잡스")): "이순신의 책임 있는 지휘와 잡스의 과감한 선택이 충돌하며, 둘 다 본질을 남기기 위해 불필요한 것을 버린다.",
    frozenset(("이순신", "일론 머스크")): "이순신은 검증된 책임선을 중시하고 머스크는 실패를 감수하는 장기 베팅을 밀어붙인다.",
    frozenset(("이순신", "유재석")): "이순신의 절제된 명령과 유재석의 섬세한 경청이 만나, 명령과 참여의 균형을 찾는다.",
    frozenset(("이순신", "예수")): "이순신은 공동체를 지키는 책임을 말하고 예수는 가장 약한 사람을 먼저 보는 책임을 요구한다.",
    frozenset(("이순신", "부처")): "이순신의 결단과 부처의 멈춤이 대비되며, 행동하기 전 마음의 집착을 점검한다.",
    frozenset(("세종대왕", "소크라테스")): "세종은 누구나 배울 수 있는 언어를 만들려 하고, 소크라테스는 배움의 출발인 질문을 지킨다.",
    frozenset(("세종대왕", "스티브 잡스")): "세종의 공공성을 위한 설계와 잡스의 극단적인 사용자 집중이 기술의 목적을 두고 만난다.",
    frozenset(("세종대왕", "일론 머스크")): "세종은 접근성과 숙의를, 머스크는 속도와 대담한 실험을 우선한다.",
    frozenset(("세종대왕", "유재석")): "세종의 신문고와 유재석의 질문이 권위보다 말할 기회를 보장하는 리더십을 만든다.",
    frozenset(("세종대왕", "예수")): "세종은 지식의 문턱을 낮추고 예수는 이웃의 경계를 낮추며, 포용의 실제 조건을 논한다.",
    frozenset(("세종대왕", "부처")): "세종의 적극적인 제도 개혁과 부처의 중도가 변화의 속도와 마음의 평온을 조율한다.",
    frozenset(("소크라테스", "스티브 잡스")): "소크라테스는 잡스의 확신을 정의의 질문으로 흔들고, 잡스는 질문을 실제 제품과 선택으로 밀어붙인다.",
    frozenset(("소크라테스", "일론 머스크")): "소크라테스는 머스크의 미래 예측에 근거를 요구하고, 머스크는 질문을 실험과 수치로 답하려 한다.",
    frozenset(("소크라테스", "유재석")): "소크라테스의 집요한 질문과 유재석의 안전한 질문이 심문과 대화의 차이를 보여준다.",
    frozenset(("소크라테스", "예수")): "소크라테스는 정의를 묻고 예수는 비유로 이웃의 얼굴을 보여주며, 추상과 삶이 만난다.",
    frozenset(("소크라테스", "부처")): "소크라테스의 논박과 부처의 관찰이 앎과 무지, 고통의 원인을 서로 다른 길로 탐구한다.",
    frozenset(("스티브 잡스", "일론 머스크")): "잡스는 집중과 완성도를, 머스크는 규모와 속도를 밀어붙이며 혁신의 조건을 두고 긴장한다.",
    frozenset(("스티브 잡스", "유재석")): "잡스의 선명한 편집과 유재석의 관계 중심 진행이 사용자를 존중하는 경험의 의미를 확장한다.",
    frozenset(("스티브 잡스", "예수")): "잡스는 단순한 제품 경험을, 예수는 단순한 사랑의 실천을 말하며 본질을 덜어낸다는 공통점을 찾는다.",
    frozenset(("스티브 잡스", "부처")): "잡스의 집요한 욕망과 부처의 집착에 대한 경계가 창작의 동력과 마음의 평온을 대비한다.",
    frozenset(("일론 머스크", "유재석")): "머스크의 직선적인 목표와 유재석의 관계 감각이 빠른 실행과 팀의 지속 가능성을 조율한다.",
    frozenset(("일론 머스크", "예수")): "머스크는 인류 전체의 생존을 말하고 예수는 눈앞의 한 사람을 말하며, 거대한 목표의 윤리를 묻는다.",
    frozenset(("일론 머스크", "부처")): "머스크의 확장 욕구와 부처의 집착 경계가 진보의 속도와 욕망의 대가를 논한다.",
    frozenset(("유재석", "예수")): "유재석의 경청과 예수의 환대가 소외된 사람에게 말할 자리를 돌려주는 방법을 찾는다.",
    frozenset(("유재석", "부처")): "유재석의 공감적 듣기와 부처의 알아차림이 불안한 팀에서 침묵을 다루는 법을 보여준다.",
    frozenset(("예수", "부처")): "예수의 사랑과 부처의 자비가 서로 다른 언어로 고통을 바라보며, 인간다운 일의 기준을 세운다.",
    frozenset(("공자", "이순신")): "공자는 평소의 훈련과 역할의 질서를, 이순신은 위기에서의 결단과 책임을 앞세운다.",
    frozenset(("공자", "세종대왕")): "두 스승은 배움과 예를 공유하지만, 공자는 관계의 수양을, 세종은 모두를 위한 지식의 문턱을 강조한다.",
    frozenset(("공자", "소크라테스")): "공자는 좋은 관계를 만드는 실천을 말하고, 소크라테스는 그 관계가 정의로운지 계속 질문한다.",
    frozenset(("공자", "스티브 잡스")): "공자의 역할과 책임에 대한 생각이 잡스의 단순한 사용자 경험과 만나 조직의 신뢰를 설계한다.",
    frozenset(("공자", "예수")): "공자는 가까운 관계에서 시작하는 책임을, 예수는 경계를 넘어 이웃을 넓히는 사랑을 말한다.",
    frozenset(("공자", "부처")): "공자의 사회적 수양과 부처의 마음 관찰이 개인의 습관과 조직의 문화를 함께 돌아보게 한다.",
    frozenset(("니체", "쇼펜하우어")): "니체는 삶을 긍정하며 의지를 자기 극복으로 바꾸려 하고, 쇼펜하우어는 욕망의 고통을 줄이는 연민과 절제를 요구한다.",
    frozenset(("니체", "소크라테스")): "니체는 소크라테스식 이성이 삶을 약화시킬 수 있다고 비판하고, 소크라테스는 그 비판의 전제를 다시 묻는다.",
    frozenset(("니체", "스티브 잡스")): "니체의 자기 창조와 잡스의 제품 철학이 만나지만, 사람을 영웅적 성과로만 평가할 위험을 두고 충돌한다.",
    frozenset(("니체", "예수")): "니체는 기독교적 연민의 일부를 삶의 힘을 약화한다고 비판하고, 예수는 약한 이웃을 돌보는 사랑의 의미를 되묻는다.",
    frozenset(("니체", "부처")): "니체는 삶을 긍정하는 힘을, 부처는 집착을 내려놓는 평온을 강조하며 AI 욕망의 방향을 두고 논쟁한다.",
    frozenset(("니체", "세종대왕")): "니체의 가치 재창조와 세종의 공공 교육이 만나 개인의 자율성과 모두의 접근성을 함께 설계한다.",
    frozenset(("니체", "이순신")): "니체의 자기 극복이 이순신의 절제된 책임과 만나, 강한 의지가 공동체를 향해야 하는 조건을 묻는다.",
    frozenset(("쇼펜하우어", "소크라테스")): "쇼펜하우어는 욕망의 구조를 분석하고 소크라테스는 좋은 삶의 정의를 질문하며 고통의 원인을 좁혀 간다.",
    frozenset(("쇼펜하우어", "스티브 잡스")): "잡스의 혁신 욕구와 쇼펜하우어의 욕망 비판이 충돌하며, 더 빠른 소비가 정말 삶을 낫게 하는지 묻는다.",
    frozenset(("쇼펜하우어", "예수")): "두 사람은 고통받는 사람을 외면하지 않지만, 쇼펜하우어는 연민의 심리에서, 예수는 이웃을 향한 실천에서 출발한다.",
    frozenset(("쇼펜하우어", "부처")): "욕망의 고통에 대한 서양 철학과 불교의 집착 성찰이 만나, AI가 불안을 키우는 방식을 차분히 분석한다.",
    frozenset(("쇼펜하우어", "세종대왕")): "쇼펜하우어는 욕망을 줄이는 지혜를, 세종은 배움의 기회를 넓히는 제도를 말하며 복지 기술의 기준을 조율한다.",
    frozenset(("쇼펜하우어", "이순신")): "쇼펜하우어의 고통에 대한 성찰과 이순신의 임무 수행이 만나, 효율보다 사람을 지키는 결단을 논한다.",
}

TOPIC_QUESTIONS = {
    "AI는 일자리를 없애는가, 바꾸는가": "누가 이익을 얻고 누가 전환 비용을 감당하는가?",
    "AI 시대에 사람만 할 수 있는 일": "자동화할 수 없는 능력을 어떻게 교육하고 평가할 것인가?",
    "생성형 AI와 창의적인 직업의 미래": "도구 사용과 창작자성의 경계는 어디에 있는가?",
    "채용 AI는 공정한가": "효율보다 설명과 이의 제기를 우선할 장치는 무엇인가?",
    "AI 시대의 리더십과 팀워크": "기술 도입 과정에서 발언권과 책임을 어떻게 나눌 것인가?",
    "내가 하고 싶은 일을 하는 게 맞을까, 내가 잘하는 것을 하는 게 맞을까?": "열망과 능력이 서로 다른 방향을 가리킬 때 무엇을 기준으로 선택할 것인가?",
    "상처받지 않기 위해 타인과 거리를 두어야 할까요, 그럼에도 불구하고 관계 속에 섞여 살아가야 할까요?": "나를 지키는 경계와 타인과의 연결을 어디에서 조율할 것인가?",
    "결혼이라는 제도와 구속을 받아들이고 헌신하는 삶이 옳을까요, 아니면 내 자유와 성장을 지키며 살아가는 삶이 옳을까요?": "헌신과 자유를 양자택일하지 않고 함께 지킬 수 있는 삶의 약속은 무엇인가?",
}
TOPIC_DILEMMAS = {
    "AI는 일자리를 없애는가, 바꾸는가": "자동화로 1,000명의 일자리를 지킬 수 있지만 100명의 재교육 비용을 당장 감당할 수 없다면 무엇을 우선할 것인가?",
    "AI 시대에 사람만 할 수 있는 일": "돌봄의 질을 높이려면 일부 판단을 자동화해야 하지만, 그 과정에서 당사자의 선택권이 줄어든다면 어디까지 허용할 것인가?",
    "생성형 AI와 창의적인 직업의 미래": "마감 안에 AI를 쓰면 더 좋은 결과를 낼 수 있지만 학습 데이터의 출처를 모두 확인할 수 없다면 작품을 공개할 것인가?",
    "채용 AI는 공정한가": "AI가 평균적으로 더 정확한 채용을 하더라도 한 지원자의 설명할 수 없는 탈락을 막지 못한다면 효율을 택할 것인가?",
    "AI 시대의 리더십과 팀워크": "빠른 도입으로 조직 전체의 성과를 높일 수 있지만 현장 구성원의 재교육이 끝나지 않았다면 도입을 멈출 것인가?",
    "내가 하고 싶은 일을 하는 게 맞을까, 내가 잘하는 것을 하는 게 맞을까?": "좋아하는 일을 시작하면 당장 생계가 흔들리지만, 잘하는 일을 계속하면 오래 후회할 것 같다면 무엇을 선택할 것인가?",
    "상처받지 않기 위해 타인과 거리를 두어야 할까요, 그럼에도 불구하고 관계 속에 섞여 살아가야 할까요?": "반복해서 상처를 주는 관계를 끊는 것이 나를 지키는 일인지, 대화와 경계를 통해 다시 시도해야 하는지 어떻게 판단할 것인가?",
    "결혼이라는 제도와 구속을 받아들이고 헌신하는 삶이 옳을까요, 아니면 내 자유와 성장을 지키며 살아가는 삶이 옳을까요?": "사랑하는 사람과의 약속을 지키려면 중요한 기회를 포기해야 하지만, 혼자라면 성장할 수 있다면 어떤 책임을 선택할 것인가?",
}
PERSONA_TENSIONS = {
    "이순신": "현장의 생존을 위해 신속히 결단해야 한다는 원칙이 소수의 목소리를 충분히 듣지 못할 위험",
    "세종대왕": "모두를 위한 제도 개혁이 기존 질서를 흔들고 준비되지 않은 사람에게 부담을 줄 위험",
    "소크라테스": "끝없는 질문과 검증이 실제 결정을 늦추고 행동의 책임을 다른 사람에게 미룰 위험",
    "스티브 잡스": "본질에 집중하려는 선택이 일부 사용자와 구성원을 배제하거나 희생시킬 위험",
    "공자": "역할과 질서를 중시하는 태도가 부당한 위계와 개인의 자유까지 지키려 할 위험",
    "예수": "조건 없는 용서와 연대가 피해자의 정의와 안전을 뒤로 미룰 위험",
    "부처": "집착을 내려놓으라는 가르침이 불의한 현실을 바꾸는 행동을 약화시킬 위험",
    "니체": "자기 극복과 강한 의지가 실패하거나 취약한 사람에 대한 무관심으로 변할 위험",
    "쇼펜하우어": "욕망을 줄이려는 태도가 현실의 고통을 바꾸기보다 체념과 회피로 흐를 위험",
}
TONES = {
    "진지한 토론": "논리적이고 차분한",
    "티키타카 개그": "재치 있고 장난스러운",
    "감성": "따뜻하고 서정적인",
    "설전": "날카롭지만 서로를 존중하는",
}
TOPIC_LENSES = {
    "AI는 일자리를 없애는가, 바꾸는가": (
        "자동화로 사라지는 업무와 새로 생기는 역할",
        "전환 교육의 비용을 누가 감당할지",
        "한 직업 전체가 아니라 업무 단위로 변화를 쪼개 보자",
    ),
    "AI 시대에 사람만 할 수 있는 일": (
        "공감·돌봄·책임처럼 맥락을 읽는 능력",
        "사람의 가치를 생산량만으로 평가하지 않는 기준",
        "정답보다 관계와 결과를 함께 살피는 판단",
    ),
    "생성형 AI와 창의적인 직업의 미래": (
        "창작자의 의도와 도구의 역할",
        "저작권·영감·모방의 경계",
        "무엇을 만들지 선택하고 결과에 책임지는 창의성",
    ),
    "채용 AI는 공정한가": (
        "평가 데이터가 과거의 편견을 반복하는 방식",
        "설명·이의 제기·재심사의 절차",
        "효율보다 지원자의 기회를 먼저 검증하는 채용",
    ),
    "AI 시대의 리더십과 팀워크": (
        "AI 도입으로 바뀌는 권한과 협업 방식",
        "재교육과 현장 발언권을 누가 보장할지",
        "빠른 도입보다 신뢰를 쌓는 운영 규칙",
    ),
    "내가 하고 싶은 일을 하는 게 맞을까, 내가 잘하는 것을 하는 게 맞을까?": (
        "내가 오래 몰입할 수 있는 욕망과 호기심",
        "이미 쌓은 능력과 현실적인 지속 가능성",
        "작은 실험과 훈련으로 열망과 역량이 만나는지 확인하는 선택",
    ),
    "상처받지 않기 위해 타인과 거리를 두어야 할까요, 그럼에도 불구하고 관계 속에 섞여 살아가야 할까요?": (
        "상처를 반복하지 않기 위한 경계와 자기 보호",
        "고립이 가져오는 안전과 관계가 주는 돌봄·성장",
        "거리를 두면서도 솔직한 대화와 제한된 연결을 시도하는 방식",
    ),
    "결혼이라는 제도와 구속을 받아들이고 헌신하는 삶이 옳을까요, 아니면 내 자유와 성장을 지키며 살아가는 삶이 옳을까요?": (
        "서로를 선택하고 돌보는 헌신의 의미",
        "각자의 자유·성장·선택권을 지키는 조건",
        "함께 살면서도 역할과 경계를 계속 협의하는 약속",
    ),
}
LIFE_TOPICS = {
    "내가 하고 싶은 일을 하는 게 맞을까, 내가 잘하는 것을 하는 게 맞을까?",
    "상처받지 않기 위해 타인과 거리를 두어야 할까요, 그럼에도 불구하고 관계 속에 섞여 살아가야 할까요?",
    "결혼이라는 제도와 구속을 받아들이고 헌신하는 삶이 옳을까요, 아니면 내 자유와 성장을 지키며 살아가는 삶이 옳을까요?",
}
LIFE_VOICE = {
    "이순신": ("전란 속에서 선택의 대가를 감당했던 경험을 떠올리면,", "마음만 앞세우기보다 내가 맡은 사람과 약속을 끝까지 책임지는 태도가 중요합니다.", "책임을 혼자 떠안다가 주변의 목소리를 놓칠 수 있다는 한계도 인정해야 합니다."),
    "세종대왕": ("백성의 삶을 살피며 제도를 고쳐야 했던 때를 돌아보면,", "좋은 선택은 개인의 뜻을 존중하면서도 누구나 다시 배울 기회를 열어야 합니다.", "모두를 위한 기준을 세우려다 한 사람의 고유한 사정을 놓칠 수 있습니다."),
    "소크라테스": ("아테네에서 사람들의 확신에 질문을 던졌던 일을 떠올리면,", "먼저 내가 무엇을 원하는지, 그 욕망이 정말 나의 것인지 묻는 성찰이 필요합니다.", "질문만 계속하다가 실제 선택과 책임을 뒤로 미룰 수 있다는 위험이 있습니다."),
    "스티브 잡스": ("익숙한 길을 버리고 새로운 것을 만들었던 순간을 돌아보면,", "가슴이 움직이는 방향을 작은 시도로 시험하고 끝까지 다듬는 힘이 중요합니다.", "자기 열망을 좇다가 함께하는 사람의 부담과 현실을 과소평가할 수 있습니다."),
    "공자": ("배움과 관계 속에서 사람의 이름과 역할을 바로 세우려 했던 때를 떠올리면,", "자유로운 뜻도 꾸준한 수련과 타인에 대한 책임을 만날 때 오래 지속됩니다.", "질서와 역할을 강조하다가 개인의 다른 목소리를 억누를 수 있습니다."),
    "예수": ("가장 낮은 곳의 사람과 식탁을 나누었던 시간을 떠올리면,", "자신을 지키되 혼자 남겨진 사람의 고통을 외면하지 않는 사랑이 필요합니다.", "희생을 너무 쉽게 미덕으로 말하면 누군가에게 더 참으라고 요구할 수 있습니다."),
    "부처": ("고통이 어디에서 생기는지 조용히 관찰했던 수행을 떠올리면,", "욕망과 두려움에 끌려가지 않고 지금의 마음과 선택을 알아차리는 일이 먼저입니다.", "초연함을 잘못 이해하면 관계와 책임에서 물러나는 핑계가 될 수 있습니다."),
    "니체": ("기존의 가치를 의심하고 자기 길을 만들려 했던 시간을 돌아보면,", "남이 정한 삶을 그대로 짊어지지 말고 스스로 선택한 가치에 자기 이름을 걸어야 합니다.", "자기 극복을 강조하다가 타인의 돌봄과 의존을 약함으로 오해할 수 있습니다."),
    "쇼펜하우어": ("욕망과 고통의 왕복을 오래 관찰했던 서재를 떠올리면,", "욕망을 즉시 따르기보다 거리를 두고 내가 감당할 고통과 평온을 분별해야 합니다.", "고독을 지혜로 삼다가 살아 있는 관계의 가능성까지 닫을 수 있습니다."),
}
TOPIC_DIALOGUE_BEATS = {
    "AI는 일자리를 없애는가, 바꾸는가": [
        ("a", "{a} 일자리가 사라진다는 말은 결국 누군가의 하루가 통째로 사라진다는 뜻입니다. 먼저 어떤 업무가 없어지는지부터 정확히 봐야 합니다."),
        ("b", "맞습니다. 하지만 업무가 줄어든 자리에 무엇을 남길지도 물어야 합니다. {vb1}"),
        ("a", "예를 들어 초안 작성이 빨라져도 최종 판단과 책임까지 자동으로 넘길 수는 없습니다. {va2}"),
        ("b", "그 책임을 말하는 사람이 늘 회사의 높은 자리에만 있어서는 안 됩니다. 실제로 도구를 쓰는 사람에게 거부할 권한이 있어야 합니다."),
        ("a", "전환 교육을 약속하면서 퇴근 뒤에 알아서 배우라고 하면 교육이 아니라 퇴출 통보입니다. 누가 시간과 비용을 부담할지 정해야 합니다."),
        ("b", "그리고 모든 사람이 같은 속도로 새 역할에 적응할 수 있다는 가정도 버려야 합니다. 숙련이 쌓이는 동안의 생계가 함께 보장되어야 합니다."),
        ("a", "저는 기술을 반대해서가 아니라, 기술의 속도가 사람의 회복보다 빠른 것을 경계합니다. {dilemma}"),
        ("b", "그렇다면 도입 여부만 투표할 게 아니라, 6개월 뒤 누가 더 불안해졌는지 확인하는 절차를 먼저 만들겠습니다."),
        ("a", "제 원칙도 현장에 모든 결정을 맡기면 전체의 방향을 잃을 수 있다는 한계가 있습니다. 큰 기준은 책임자가 설명해야 합니다."),
        ("b", "저 역시 효율만 보면 새 기회를 놓칠 수 있다는 점을 인정합니다. 다만 실험은 되돌릴 수 있게 작게 시작해야 합니다."),
        ("a", "결국 질문은 일자리를 지키느냐 없애느냐가 아니라, 변화의 위험을 누구에게 몰아주느냐입니다."),
        ("b", "사람을 내보내고 혁신이라 부르지 않으려면, 전환에 참여한 사람에게 선택권과 다음 기회를 함께 줘야 합니다."),
    ],
    "AI 시대에 사람만 할 수 있는 일": [
        ("a", "사람만 할 수 있는 일을 너무 빨리 정답처럼 고정하면 또 다른 서열이 생깁니다. 먼저 누군가의 고통을 알아차리는 순간을 봐야 합니다."),
        ("b", "그 순간에는 정보보다 관계가 먼저 작동합니다. {vb1}"),
        ("a", "돌봄은 시간이 오래 걸리고 성과표에 잘 잡히지 않지만, 한 사람이 다시 일어나는 데 꼭 필요한 노동입니다."),
        ("b", "맞습니다. 다만 인간적이라는 이름으로 모든 부담을 사람에게 떠넘겨서도 안 됩니다. 도구가 덜어야 할 돌봄과 사람이 맡아야 할 돌봄을 구분해야 합니다."),
        ("a", "환자의 표정이나 아이의 침묵처럼 데이터로 번역되기 전의 신호를 읽는 능력은 중요합니다. 그러나 그것도 타고난 본질이 아니라 배울 수 있는 능력입니다."),
        ("b", "그래서 사람의 역할을 신비화하기보다 듣기, 사과하기, 책임지기 같은 훈련을 사회가 지원해야 합니다."),
        ("a", "{dilemma} 이 질문 앞에서 효율만 높이면 가장 먼저 목소리를 잃는 사람이 생깁니다."),
        ("b", "반대로 인간의 영역이라며 기술을 거부하면 장애가 있는 사람의 선택지를 줄일 수도 있습니다. 좋은 도구는 접근성을 넓혀야 합니다."),
        ("a", "저는 사람의 판단을 절대화할 수 없다는 점을 인정합니다. 사람도 편견과 피로 때문에 타인을 잘못 볼 수 있습니다."),
        ("b", "저도 자비를 말하면서 실제 부담을 외면할 수 있다는 위험을 인정합니다. 그래서 결과를 함께 점검할 동료와 절차가 필요합니다."),
        ("a", "인간다움은 기계와 다른 기능 목록이 아니라, 타인의 삶에 영향을 준 뒤에도 책임을 피하지 않는 태도에 가깝습니다."),
        ("b", "그 태도를 지키는 한, AI는 사람을 밀어내는 경쟁자가 아니라 우리가 더 잘 돌보도록 돕는 보조자가 될 수 있습니다."),
    ],
    "생성형 AI와 창의적인 직업의 미래": [
        ("a", "AI가 만든 이미지가 아름답다는 사실과 그것을 창작이라고 부를 수 있는지는 다른 질문입니다. 먼저 누가 선택했는지 물어야 합니다."),
        ("b", "선택의 기준이 작품에 드러나야 합니다. {vb1}"),
        ("a", "그렇다면 프롬프트를 한 줄 쓰는 것만으로 창작자라 주장하기는 어렵겠군요. 버리고 고치고 책임진 과정이 남아야 합니다."),
        ("b", "맞습니다. 하지만 붓이나 카메라도 누군가의 기술을 바꿔 놓았습니다. 도구가 새롭다는 이유만으로 사용자의 상상력을 가짜라고 할 수는 없습니다."),
        ("a", "문제는 도구의 재료입니다. 다른 창작자의 작업을 동의 없이 학습했다면 결과물의 편리함 뒤에 빚이 남습니다."),
        ("b", "출처를 밝히고 보상하는 규칙이 필요합니다. 투명성은 창작을 약하게 만드는 검열이 아니라 대화의 출발점입니다."),
        ("a", "{dilemma} 창작자가 자유롭다는 말이 타인의 권리를 지우는 면허가 되어서는 안 됩니다."),
        ("b", "동시에 모든 영향을 원천 봉쇄하면 작은 창작자에게도 새로운 표현 수단을 닫게 됩니다. 위험을 나누는 사용 규칙이 현실적입니다."),
        ("a", "저는 인간의 의도를 강조하다가 결과의 피해를 과소평가할 수 있다는 한계를 인정합니다."),
        ("b", "저도 새로움을 찬양하다가 오래 쌓인 노동의 가치를 값싸게 만들 수 있다는 점을 인정합니다."),
        ("a", "앞으로의 창작자는 결과를 혼자 만든 사람보다, 무엇을 참고했고 무엇을 거부했는지 설명할 수 있는 사람에 가까워질 것입니다."),
        ("b", "그 설명이 살아 있다면 AI는 작가를 지우는 기계가 아니라, 작가가 더 대담한 질문을 시도하는 작업실이 될 수 있습니다."),
    ],
    "채용 AI는 공정한가": [
        ("a", "공정하다는 말부터 의심해야 합니다. 과거의 합격자를 그대로 학습한 시스템은 과거의 문턱도 함께 복제할 수 있습니다."),
        ("b", "그렇다고 사람의 면접이 자동으로 공정한 것도 아닙니다. {vb1}"),
        ("a", "문제는 지원자가 왜 탈락했는지 물어도 답을 들을 수 없다는 데 있습니다. 설명할 수 없는 점수는 판정이 아니라 벽입니다."),
        ("b", "설명만 보여준다고 충분하지 않습니다. 지원자가 정정 자료를 내고 다른 심사관에게 다시 판단받을 통로가 있어야 합니다."),
        ("a", "이력서의 공백을 낮은 의지로 읽는다면 돌봄과 질병의 시간을 벌점으로 만들게 됩니다. 데이터 밖의 사정을 들을 귀가 필요합니다."),
        ("b", "동의합니다. 효율을 위해 사람을 숫자로 줄일수록, 숫자가 놓친 맥락을 확인하는 인간의 역할은 더 엄격해져야 합니다."),
        ("a", "{dilemma} 소수점 몇 자리의 정확도가 한 사람의 기회를 대신할 수는 없습니다."),
        ("b", "그래서 모델의 성능보다 먼저 탈락률이 특정 집단에 몰리지 않는지 계속 공개해야 합니다."),
        ("a", "저는 인간 심사관을 최종 권한자로 두면 편견이 해결된다고 생각하지 않습니다. 사람의 판단도 기록되고 서로 검토받아야 합니다."),
        ("b", "저 역시 투명한 절차가 느려질 수 있다는 비용을 인정합니다. 그러나 채용에서 빠른 오판은 되돌리기 어렵습니다."),
        ("a", "공정한 채용은 편향이 전혀 없는 기계가 아니라, 잘못을 발견했을 때 멈추고 고칠 수 있는 제도입니다."),
        ("b", "AI는 문을 여는 열쇠일 수 있지만 심판은 아닙니다. 마지막에는 지원자의 목소리를 듣는 사람이 있어야 합니다."),
    ],
    "AI 시대의 리더십과 팀워크": [
        ("a", "AI를 도입하는 순간 리더가 가장 먼저 할 일은 자랑이 아니라 불안을 말할 수 있게 하는 것입니다."),
        ("b", "불안한 사람이 침묵하면 회의는 빨라 보여도 실제 문제는 지하에 남습니다. {vb1}"),
        ("a", "현장에서 도구가 틀렸다는 신호를 보내도 목표 수치 때문에 무시된다면, 기술이 아니라 리더십이 실패한 겁니다."),
        ("b", "반대로 모든 결정을 합의할 때까지 기다리면 팀은 움직이지 못합니다. 실험의 범위와 중단 조건은 리더가 분명히 정해야 합니다."),
        ("a", "재교육을 한다며 매뉴얼만 나눠주면 새 역할을 배운 게 아니라 책임을 떠넘긴 것입니다. 업무 시간 안에 연습할 여유가 필요합니다."),
        ("b", "그리고 잘하는 사람 몇 명에게만 AI를 맡기면 팀의 지식이 다시 병목이 됩니다. 질문을 환영하는 구조를 만들어야 합니다."),
        ("a", "{dilemma} 속도와 신뢰 중 하나를 영원히 고르는 게 아니라, 되돌릴 수 있는 속도로 시작해야 합니다."),
        ("b", "그 과정에서 누가 이익을 얻고 누가 더 많은 감시를 받는지 공개하겠습니다. 팀워크는 좋은 분위기보다 권한의 투명성에 가깝습니다."),
        ("a", "저는 책임을 분명히 하려다 명령을 많이 만들 수 있다는 한계를 인정합니다."),
        ("b", "저도 참여를 강조하다가 결정을 미룰 수 있다는 약점을 인정합니다. 그래서 의견을 듣는 시간과 결정하는 시간을 구분하겠습니다."),
        ("a", "좋은 리더는 AI를 가장 잘 쓰는 사람이 아니라, AI가 틀렸을 때 누구나 멈추라고 말할 수 있게 하는 사람입니다."),
        ("b", "그 안전이 있다면 도구는 팀을 작게 만드는 감시 장치가 아니라, 함께 더 어려운 문제를 풀게 하는 공용 작업대가 됩니다."),
    ],
    "내가 하고 싶은 일을 하는 게 맞을까, 내가 잘하는 것을 하는 게 맞을까?": [
        ("a", "하고 싶은 일은 자꾸 돌아옵니다. 시간이 없다고 밀어내도 어느 순간 같은 질문으로 다시 나타나지요."),
        ("b", "그 마음을 존중합니다. 하지만 좋아한다는 이유만으로 내일의 생계를 다른 사람에게 맡길 수는 없습니다. {vb1}"),
        ("a", "그래서 저는 거창한 결심보다 작은 실험을 권합니다. 주말에 만든 한 결과물이 정말 나를 다시 책상 앞으로 부르는지 보자는 겁니다."),
        ("b", "작은 실험에는 훈련의 고통도 넣어야 합니다. 재미있는 상상만 좋아하는 것인지, 서툰 반복까지 견디는 것인지 구분해야 합니다."),
        ("a", "잘하는 일만 택하면 안전해 보이지만, 그 능력이 더 이상 나를 살게 하지 않을 때 빈 껍데기가 될 수 있습니다."),
        ("b", "반대로 열망만 좇으면 함께 사는 사람에게 불확실성을 떠넘길 수 있습니다. 내가 감당할 몫을 먼저 계산해야 합니다."),
        ("a", "{dilemma} 어느 쪽도 타고난 운명처럼 받아들일 필요는 없습니다."),
        ("b", "맞습니다. 능력은 발견하는 것만이 아니라 연습으로 만들어지는 것이고, 꿈도 현실의 피드백을 받으며 모양을 바꿉니다."),
        ("a", "저는 세상이 즉시 박수치지 않아도 계속 시도할 이유가 있는지 물어보겠습니다. 다만 고집과 용기를 혼동하지 않겠습니다."),
        ("b", "저도 현실적인 선택이 곧 비겁함은 아니라는 점을 인정합니다. 오래 가기 위한 발판을 마련하는 것도 뜻을 지키는 방법입니다."),
        ("a", "결국 하고 싶은 일과 잘하는 일 중 하나를 고르는 게 아니라, 하고 싶은 것을 잘하기 위해 어떤 수련을 감당할지 정하는 문제입니다."),
        ("b", "그리고 그 선택을 한 번 정하면 끝내는 것이 아니라, 삶의 형편과 마음이 바뀔 때 다시 묻는 것이 정직한 태도입니다."),
    ],
    "상처받지 않기 위해 타인과 거리를 두어야 할까요, 그럼에도 불구하고 관계 속에 섞여 살아가야 할까요?": [
        ("a", "모든 사람에게 마음을 열어야 한다는 말은 때로 상처 입은 사람에게 또 다른 의무가 됩니다. 먼저 안전한 거리를 인정해야 합니다."),
        ("b", "동의합니다. 다만 문을 닫은 채 아무도 믿지 않는 것이 안전의 끝은 아닙니다. {vb1}"),
        ("a", "상대의 연락을 늦게 받고 혼자 있는 시간을 갖는 건 냉정함이 아닐 수 있습니다. 내 감정이 무엇인지 들을 공간이니까요."),
        ("b", "그 공간에서 회복한 뒤에도 누군가에게 도움을 청할 수 있어야 합니다. 강한 사람인 척하는 고립은 상처를 오래 숨길 뿐입니다."),
        ("a", "관계가 가까워질수록 기대가 커지고 실망도 커집니다. 그러니 상대가 내 빈 곳을 모두 채워야 한다는 계약부터 내려놓아야 합니다."),
        ("b", "맞습니다. 사랑은 상대를 내 방식으로 고치는 일이 아니라, 다름을 알면서도 해칠 선을 넘지 않기로 약속하는 일입니다."),
        ("a", "{dilemma} 떠나는 것이 필요한 관계와 대화로 고칠 수 있는 관계를 구분해야 합니다."),
        ("b", "그 구분을 혼자 하지 않아도 됩니다. 믿을 수 있는 친구나 상담자에게 상황을 말하는 것도 관계를 다시 배우는 과정입니다."),
        ("a", "저는 고독을 말하면서 타인의 온기를 과소평가할 수 있다는 한계를 인정합니다."),
        ("b", "저도 연대를 말하면서 상처받은 사람에게 참으라고 압박할 수 있다는 위험을 인정합니다."),
        ("a", "모든 사람과 섞일 필요는 없지만, 모든 사람을 적으로 만들 필요도 없습니다. 경계에는 문도 있어야 합니다."),
        ("b", "그 문을 언제 열고 닫을지는 남의 도덕이 아니라 내 안전과 서로의 존중을 기준으로 정하면 됩니다."),
    ],
    "결혼이라는 제도와 구속을 받아들이고 헌신하는 삶이 옳을까요, 아니면 내 자유와 성장을 지키며 살아가는 삶이 옳을까요?": [
        ("a", "결혼했다는 사실이 두 사람을 저절로 사랑하게 만들지는 않습니다. 제도가 약속을 대신하는 순간부터 관계는 굳어집니다."),
        ("b", "하지만 약속은 삶이 흔들릴 때 서로를 돌볼 근거가 되기도 합니다. {vb1}"),
        ("a", "문제는 헌신을 한 사람의 희생으로 번역하는 순간입니다. 한쪽의 꿈을 접게 하고 그것을 사랑이라 부르면 안 됩니다."),
        ("b", "동의합니다. 예의와 역할은 복종의 목록이 아니라, 누가 지치고 무엇이 바뀌었는지 묻는 대화여야 합니다."),
        ("a", "혼자 사는 삶도 도피라고 단정할 수 없습니다. 자기 시간을 지키며 더 큰 책임을 준비하는 방식일 수 있습니다."),
        ("b", "결혼한 삶도 자유롭지 않다고 단정할 수 없습니다. 함께 살기로 한 약속을 스스로 갱신한다면 자율적인 선택입니다."),
        ("a", "{dilemma} 두 사람이 같은 집에 있어도 각자의 내면까지 소유할 수는 없습니다."),
        ("b", "그래서 돈, 집안일, 가족 돌봄, 혼자 있는 시간처럼 낭만 뒤에 숨은 조건을 구체적으로 합의해야 합니다."),
        ("a", "저는 자유를 강조하다가 돌봄의 책임을 불편한 구속으로만 볼 수 있다는 한계를 인정합니다."),
        ("b", "저도 헌신을 강조하다가 관계를 유지하기 위해 한 사람의 성장을 희생시킬 수 있다는 위험을 인정합니다."),
        ("a", "제도가 목적이 되면 굴레지만, 서로의 성장을 돕는 형식이라면 사랑을 지탱하는 도구가 될 수 있습니다."),
        ("b", "결국 옳은 형태를 고르는 것보다, 두 사람이 계속 동의하고 수정할 수 있는 삶을 만드는 일이 더 중요합니다."),
    ],
}
TOPIC_FOLLOWUP_PAIRS = {
    "AI는 일자리를 없애는가, 바꾸는가": [
        ("a", "전환의 첫날에는 새 직함보다 누가 옆에서 가르칠지가 더 중요합니다."),
        ("b", "그 교육을 받은 사람이 다시 다른 사람을 가르칠 수 있어야 변화가 특정 전문가에게 갇히지 않습니다."),
        ("a", "자동화로 남은 시간을 더 많은 업무로 채우면 약속을 어긴 셈입니다."),
        ("b", "절약한 시간이 휴식과 숙련으로 돌아갔는지 확인하는 지표도 필요합니다."),
        ("a", "작은 실패를 숨기지 않는 팀이 결국 큰 사고를 줄일 수 있습니다."),
        ("b", "실패한 사람을 바로 교체하면 모두가 문제를 보고하지 않는 법부터 배우게 됩니다."),
    ],
    "AI 시대에 사람만 할 수 있는 일": [
        ("a", "사람의 강점은 감정이 있다는 사실보다 감정을 다룰 책임을 배울 수 있다는 데 있습니다."),
        ("b", "그 책임을 혼자에게 맡기지 말고, 쉬고 상담받을 수 있는 환경으로 받쳐야 합니다."),
        ("a", "돌봄을 자동화할 수 있는 부분은 하되, 돌봄받는 사람이 선택할 여지는 남겨야 합니다."),
        ("b", "기계가 대신한 뒤에도 누구에게 설명하고 사과할지는 사람의 몫으로 남습니다."),
        ("a", "인간다움을 말하면서 비효율을 모두 선하다고 부르지는 않겠습니다."),
        ("b", "저도 효율을 말하면서 느린 사람을 쓸모없다고 부르지 않겠습니다."),
    ],
    "생성형 AI와 창의적인 직업의 미래": [
        ("a", "작품 옆에 사용한 자료와 도구를 적는 습관이 새로운 신뢰의 형식이 될 수 있습니다."),
        ("b", "그 기록이 창작자를 감시하기보다 정당한 기여를 찾아 보상하는 데 쓰여야 합니다."),
        ("a", "AI가 낸 첫 결과를 완성품처럼 내놓지 않고, 왜 버리고 고쳤는지를 보여주겠습니다."),
        ("b", "그 과정에서 작가의 취향과 편집이 작품의 목소리가 됩니다."),
        ("a", "새 도구를 금지하는 대신 동의와 보상을 기본값으로 삼는 편이 오래 갑니다."),
        ("b", "창작의 미래는 인간 대 기계의 승부가 아니라, 더 정직한 제작 관행을 만드는 일입니다."),
    ],
    "채용 AI는 공정한가": [
        ("a", "탈락한 사람도 자신의 기록이 어떻게 읽혔는지 알 권리가 있습니다."),
        ("b", "그 권리가 있어야 잘못된 정보와 시스템의 편견을 구분해 고칠 수 있습니다."),
        ("a", "감사 보고서가 한 번 공개되고 끝나면 공정성은 홍보 문구에 머뭅니다."),
        ("b", "채용할 때마다 집단별 결과를 다시 보고, 이상하면 즉시 사람의 심사로 되돌려야 합니다."),
        ("a", "빠른 채용보다 잘못된 탈락을 되돌릴 수 있는 장치가 먼저입니다."),
        ("b", "그 장치까지 갖췄을 때만 AI를 보조자로 부를 수 있습니다."),
    ],
    "AI 시대의 리더십과 팀워크": [
        ("a", "회의에서 가장 먼저 말하는 사람보다 가장 늦게 질문하는 사람의 걱정을 들어야 합니다."),
        ("b", "질문이 평가에 불리하지 않다는 믿음이 있어야 팀의 정보가 위로 올라옵니다."),
        ("a", "결정권을 나누는 것은 책임을 없애는 일이 아니라 책임의 위치를 보이게 하는 일입니다."),
        ("b", "누가 멈출 수 있는지까지 정해져야 권한 위임이 실제가 됩니다."),
        ("a", "도입 후 성과가 아니라 구성원의 판단력이 커졌는지도 살펴보겠습니다."),
        ("b", "그때 AI는 팀을 감시하는 장치가 아니라 함께 익히는 공용 언어가 될 것입니다."),
    ],
    "내가 하고 싶은 일을 하는 게 맞을까, 내가 잘하는 것을 하는 게 맞을까?": [
        ("a", "한 달 동안 시간을 써보고도 계속 배우고 싶다면 그 마음은 꽤 믿을 만한 신호입니다."),
        ("b", "그 신호를 믿되 생활비와 주변의 약속을 함께 적어보면 선택이 더 정직해집니다."),
        ("a", "잘한다는 이유로 지친 일을 계속할 의무는 없습니다."),
        ("b", "하고 싶다는 이유로 준비가 끝났다고 착각할 의무도 없습니다."),
        ("a", "작은 결과를 세상에 내놓고 받은 반응을 자존심이 아니라 자료로 보겠습니다."),
        ("b", "그 자료를 바탕으로 방향을 바꾸는 것도 실패가 아니라 배움의 일부입니다."),
    ],
    "상처받지 않기 위해 타인과 거리를 두어야 할까요, 그럼에도 불구하고 관계 속에 섞여 살아가야 할까요?": [
        ("a", "경계는 상대를 벌주는 벽이 아니라 내가 감당할 수 있는 접촉의 양을 알리는 말입니다."),
        ("b", "그 말을 들은 사람이 존중할 때 관계는 가까워질 기회를 얻습니다."),
        ("a", "사과가 반복된 뒤에도 같은 일이 이어진다면 거리를 두는 것은 복수가 아닙니다."),
        ("b", "반대로 한 번의 서투름만으로 모든 문을 닫지 않는 여유도 필요합니다."),
        ("a", "내가 안전하다고 느끼는 관계의 조건을 구체적으로 말해보겠습니다."),
        ("b", "그 조건을 함께 지킬 수 있는 사람과만 천천히 섞여 살아가면 됩니다."),
    ],
    "결혼이라는 제도와 구속을 받아들이고 헌신하는 삶이 옳을까요, 아니면 내 자유와 성장을 지키며 살아가는 삶이 옳을까요?": [
        ("a", "사랑을 증명하려고 자기 삶을 포기할 필요는 없습니다."),
        ("b", "그렇지만 함께 선택한 책임을 자유라는 말로 혼자 떠날 수도 없습니다."),
        ("a", "집안일과 돈을 말로만 공평하게 나누지 말고 실제 시간을 기록해보겠습니다."),
        ("b", "그 기록이 누가 더 희생했는지 겨루는 장부가 아니라 약속을 고치는 자료가 되어야 합니다."),
        ("a", "각자의 친구와 공부와 혼자 있는 시간을 지키는 것이 관계를 약하게 만들지는 않습니다."),
        ("b", "오히려 다시 만날 때 가져올 자기 삶이 있어야 헌신이 의무만 되지 않습니다."),
    ],
}
TONE_LENSES = {
    "진지한 토론": ("차분히 전제를 나누어 보겠습니다.", "그 조건이라면 실제 책임선을 확인해야 합니다."),
    "티키타카 개그": ("잠시 웃고 시작해도 질문은 꽤 묵직합니다.", "이 정도면 AI에게도 회의록을 맡기고 싶겠지만, 결론은 사람이 내야 합니다."),
    "감성": ("오늘의 질문을 한 사람의 삶 가까이 가져와 보겠습니다.", "결국 기술의 방향은 그 곁에 남은 사람의 표정에서 드러날 것입니다."),
    "설전": ("그 주장을 그대로 받아들이기에는 전제가 너무 많습니다.", "좋습니다. 그렇다면 그 원칙을 가장 불편한 사례에도 적용해 보시지요."),
}


@dataclass
class Dialogue:
    scene: str
    script: list[tuple[str, str]]
    summary: str
    chem: int
    mvp: str
    stance_a: str = ""
    stance_b: str = ""
    conflict: str = ""


DEMO_DIALOGUES = {
    ("이순신", "스티브 잡스", "AI는 일자리를 없애는가, 바꾸는가"): Dialogue(
        "한산도의 파도와 첫 아이폰 발표장의 조명이 겹쳐진 광장. 두 사람은 직업의 미래를 두고 마주 앉았다.",
        [
            ("이순신", "명량에서 열세 척으로 싸울 때도 배보다 중요한 것은 선원들이 맡은 역할과 서로에 대한 신뢰였습니다."),
            ("스티브 잡스", "저도 애플로 돌아온 뒤 수많은 제품을 줄였습니다. 기술이 많다고 사람이 더 나은 경험을 얻는 건 아니니까요."),
            ("이순신", "AI가 사람의 일을 덜어준다면, 그 시간으로 더 중요한 판단과 돌봄을 맡겨야 합니다."),
            ("스티브 잡스", "맞습니다. 아이폰은 기능을 늘리는 대신 사용자가 무엇을 하려는지에 집중했습니다."),
            ("이순신", "다만 책임의 주체가 흐려져서는 안 됩니다. 전투의 명령도, AI의 결정도 누군가는 감당해야 합니다."),
            ("스티브 잡스", "AI가 만든 결과를 그대로 내놓는 직업은 사라질 수 있습니다. 대신 무엇을 만들지 정의하는 사람은 더 중요해지죠."),
            ("이순신", "그렇다면 교육도 정답을 빨리 찾는 훈련보다 상황을 읽고 결단하는 훈련이어야겠군요."),
            ("스티브 잡스", "그리고 실패를 숨기지 않는 문화가 필요합니다. 애플에서 넥스트로 떠났던 실패도 다음 제품의 재료가 됐으니까요."),
            ("이순신", "기술은 사람을 대신하는 칼이 아니라, 사람이 책임 있게 휘두를 도구입니다."),
            ("스티브 잡스", "결국 AI는 직업을 통째로 없애기보다, 평범한 업무와 뛰어난 판단 사이의 경계를 다시 그릴 겁니다."),
            ("이순신", "그 경계에서 사람을 지키는 원칙을 잃지 않는 것이 지휘관의 일입니다."),
            ("스티브 잡스", "그리고 좋은 직업의 미래는 더 많은 일을 하는 것이 아니라, 더 의미 있는 문제를 선택하는 데 있겠네요."),
        ],
        "명량의 지휘와 애플의 제품 혁신을 연결해, AI가 직업을 없애기보다 책임과 판단의 가치를 키운다는 결론에 도달한다.",
        94,
        "이순신",
    ),
    ("이순신", "세종대왕", "AI시대, 리더쉽의 방향"): Dialogue(
        "한산도의 전선과 집현전의 등불이 하나의 광장에 겹쳐졌다. 두 사람은 AI 시대에 필요한 리더의 자세를 논한다.",
        [
            ("이순신", "변화의 파도가 거세질수록 지휘관은 먼저 책임의 선을 분명히 그어야 합니다. AI가 내린 판단이라도 결과를 감당할 사람은 필요합니다."),
            ("세종대왕", "그 책임은 명령을 내리는 데서 끝나지 않습니다. 백성이 새 기술을 이해하고 스스로 활용할 수 있도록 배움의 길을 열어야 합니다."),
            ("이순신", "현장에서는 완벽한 계획을 기다릴 수 없습니다. 작은 실험으로 위험을 확인하고, 잘못되면 즉시 방향을 바꾸는 결단이 필요합니다."),
            ("세종대왕", "빠른 결단도 중요하지만 배우지 못한 이가 변화에서 밀려난다면 그 속도는 공공의 이익이 될 수 없습니다."),
            ("이순신", "그렇다면 리더는 기술을 가장 먼저 쓰는 사람이 아니라, 가장 먼저 책임지는 사람이어야 하겠군요."),
            ("세종대왕", "맞습니다. 동시에 구성원이 질문하고 반대할 수 있는 언어를 마련해야 합니다. 침묵을 충성으로 오해해서는 안 됩니다."),
            ("이순신", "전장에서도 보고가 막히면 패배가 시작됩니다. AI의 성과만 보고 실패와 불편한 신호를 숨기면 조직은 눈이 멀게 됩니다."),
            ("세종대왕", "그래서 성과 지표와 함께 누구의 삶이 나아졌는지도 살펴야 합니다. 기술은 사람을 넓히기 위해 쓰여야 합니다."),
            ("이순신", "권한을 나누되 최종 책임은 흐리지 않겠습니다. 각자가 판단할 수 있어야 하고, 그 판단의 결과를 함께 검토해야 합니다."),
            ("세종대왕", "저는 누구나 배울 수 있는 쉬운 설명과 재교육을 먼저 준비하겠습니다. 도구의 문턱을 낮추는 것도 리더의 책무입니다."),
            ("이순신", "결국 AI 시대의 리더십은 속도와 신중함 사이에서 부하와 백성을 지키는 실천이겠군요."),
            ("세종대왕", "기술을 앞세우되 사람을 뒤에 세우지 않는 것, 그것이 우리가 세워야 할 새로운 리더의 방향입니다."),
        ],
        "이순신은 명확한 책임과 현장 중심의 결단을, 세종대왕은 모두가 참여할 수 있는 배움과 포용적 질서를 강조한다. 두 사람은 사람을 지키는 리더십을 AI 도입의 기준으로 삼는다.",
        93,
        "세종대왕",
        "AI 시대의 리더는 빠르게 실험하고 결과에 책임지며, 현장에서 위험과 실패를 숨기지 않는 결단을 보여야 한다.",
        "AI의 혜택이 일부에게만 돌아가지 않도록 누구나 이해하고 배울 수 있는 교육과 참여의 질서를 먼저 만들어야 한다.",
        "이순신은 책임 있는 실행과 결단을 우선하고, 세종대왕은 포용적 교육과 참여 구조를 우선한다.",
    ),
    ("예수", "부처", "AI 시대에 사람만 할 수 있는 일"): Dialogue(
        "고요한 산길과 작은 마을의 광장이 이어진 곳. 두 사람은 기술이 커질수록 사람이 지켜야 할 것을 이야기한다.",
        [
            ("예수", "사람의 가치는 얼마나 많은 일을 해내는지가 아니라, 가장 작은 이웃을 어떻게 대하는지에서도 드러납니다."),
            ("부처", "나는 보리수 아래에서 마음의 움직임을 살폈습니다. 기술도 마음이 향하는 곳에 따라 고통을 줄이거나 키울 수 있습니다."),
            ("예수", "산상수훈에서 말했듯, 힘 있는 사람만을 위한 질서는 오래 평안할 수 없습니다. AI의 혜택도 소외된 이에게 닿아야 합니다."),
            ("부처", "동의합니다. 다만 선한 목적이라도 집착하면 새로운 고통이 됩니다. 성과와 속도에 매이지 않는 중도가 필요합니다."),
            ("예수", "선한 사마리아인의 비유는 낯선 사람을 이웃으로 바라보라는 요청입니다. 직업의 변화에서도 먼저 얼굴을 가진 사람을 보아야 합니다."),
            ("부처", "그리고 불안한 노동자를 탓하기보다 불안이 생기는 조건을 관찰해야 합니다. 원인을 보아야 올바른 대응이 가능합니다."),
            ("예수", "AI가 반복되는 일을 덜어준다면, 사람은 돌봄과 용서처럼 계산하기 어려운 일을 더 맡을 수 있습니다."),
            ("부처", "그러나 인간의 마음도 훈련하지 않으면 자동화된 습관에 머뭅니다. 주의 깊게 듣고 멈추는 능력을 길러야 합니다."),
            ("예수", "결국 사람만의 일은 경쟁에서 이기는 일이 아니라 서로를 다시 일으키는 일일지도 모릅니다."),
            ("부처", "그 일은 고정된 본질이라기보다 매 순간 선택하는 자비의 행동입니다."),
            ("예수", "기술을 판단하는 기준은 힘이 얼마나 커지는지가 아니라, 약한 이의 삶이 얼마나 안전해지는지여야 합니다."),
            ("부처", "AI 시대에도 깨어 있음과 자비가 있다면, 도구는 고통을 줄이는 길이 될 수 있습니다."),
        ],
        "사랑과 자비라는 두 전통의 언어로 AI 시대의 노동, 소외, 인간다운 돌봄을 성찰하는 대화.",
        92,
        "부처",
    ),
    ("소크라테스", "니체", "생성형 AI와 창의적인 직업의 미래"): Dialogue(
        "아테네의 시장과 알프스의 산길이 이어진 광장. 두 사람은 AI가 만든 창작물 앞에서 창작자의 의미를 묻는다.",
        [
            ("소크라테스", "사람들은 AI가 그림과 글을 만들면 창작자가 사라진다고 말합니다. 그런데 먼저 창작자란 누구인지 물어야 하지 않겠습니까?"),
            ("니체", "좋습니다. 저는 창작자를 이미 있는 규칙을 잘 따르는 사람이 아니라, 새로운 가치를 만들어 내는 사람으로 봅니다."),
            ("소크라테스", "그렇다면 AI가 수많은 결과를 내놓아도, 무엇을 선택할지 모르는 사람은 창작자가 아니겠군요."),
            ("니체", "맞습니다. 속도와 양은 힘처럼 보이지만, 자기 기준 없이 생성하는 사람은 도구의 취향을 반복할 뿐입니다."),
            ("소크라테스", "하지만 그 기준이 정말 자기 것인지 어떻게 알 수 있을까요? 학습한 자료와 사회의 관습에서 벗어날 수 있습니까?"),
            ("니체", "완전히 벗어날 수는 없습니다. 다만 자신에게 물려온 가치를 시험하고, 그것을 넘어설 용기를 가질 수는 있습니다."),
            ("소크라테스", "아테네에서 저는 사람들이 안다고 믿는 것을 계속 물었습니다. AI 시대에도 질문이 창작의 시작이라는 뜻이군요."),
            ("니체", "그리고 질문 뒤에는 결단이 있어야 합니다. 모든 가능성을 비교만 하다가는 자신의 목소리를 끝내 만들지 못합니다."),
            ("소크라테스", "저작권 문제는 어떻습니까? 다른 사람의 작품을 배운 AI의 결과를 자기 창작이라고 부를 수 있습니까?"),
            ("니체", "영향을 받았다는 사실과 책임 없이 훔치는 일은 다릅니다. 무엇을 가져왔고 어떻게 변형했는지 밝히는 정직이 필요합니다."),
            ("소크라테스", "결국 도구의 사용보다 결과를 선택한 이유와 그 결과가 타인에게 미치는 영향을 설명할 수 있어야 하겠군요."),
            ("니체", "그렇습니다. AI는 창작자의 자리를 빼앗는 심판이 아니라, 더 높은 기준을 요구하는 거울이어야 합니다."),
        ],
        "소크라테스는 창작의 기준을 질문과 설명 가능성에서 찾고, 니체는 자기 극복과 가치 창조에서 찾는다. 둘은 AI보다 선택과 책임이 창작자성을 만든다는 데 만난다.",
        95,
        "니체",
    ),
    ("부처", "쇼펜하우어", "AI 시대에 사람만 할 수 있는 일"): Dialogue(
        "고요한 숲의 오솔길과 유럽의 서재가 한곳에 놓였다. 두 사람은 AI가 인간의 욕망과 고통을 어떻게 바꾸는지 살핀다.",
        [
            ("부처", "사람들은 AI가 일을 대신하면 자유로워질 것이라고 기대합니다. 저는 먼저 그 자유를 무엇에 쓰려는지 살펴보고 싶습니다."),
            ("쇼펜하우어", "그 질문은 제 생각과 닿아 있습니다. 인간은 일을 줄여도 욕망을 줄이지 못하면 더 많은 것을 원하며 다시 고통받습니다."),
            ("부처", "그러므로 사람만 할 수 있는 일은 특별한 능력이라기보다, 마음이 무엇에 끌리는지 알아차리는 일일 수 있습니다."),
            ("쇼펜하우어", "다만 알아차림만으로는 부족합니다. 욕망은 끊임없이 새로운 대상을 만들어 내므로, 타인의 고통을 함께 느끼는 연민이 필요합니다."),
            ("부처", "연민은 좋은 감정에 머물지 않고 행동으로 이어져야 합니다. 자동화로 불안해진 노동자의 조건을 바꾸는 일도 수행입니다."),
            ("쇼펜하우어", "동의합니다. 효율이 높아졌다는 이유로 해고의 고통을 개인의 적응 실패로 돌려서는 안 됩니다."),
            ("부처", "하지만 기술을 모두 거부하면 고통을 줄일 기회도 놓칩니다. 중도는 멈춤과 활용 사이에서 실제 결과를 보는 태도입니다."),
            ("쇼펜하우어", "그 점에서는 저도 수정하겠습니다. 예술과 사유가 의지의 소음을 잠시 멈추게 하듯, 좋은 도구는 욕망의 속도를 낮출 수 있습니다."),
            ("부처", "그렇다면 AI가 사람의 주의를 빼앗는지, 아니면 회복할 시간을 돌려주는지 관찰해야겠군요."),
            ("쇼펜하우어", "그리고 그 관찰을 기업의 광고 문구가 아니라 노동자의 경험으로 검증해야 합니다."),
            ("부처", "사람만의 일은 경쟁에서 앞서는 일이 아니라, 다른 존재의 고통을 외면하지 않는 선택입니다."),
            ("쇼펜하우어", "욕망을 더 크게 만드는 AI보다, 욕망의 굴레를 알아차리고 서로의 부담을 덜어 주는 AI가 나은 도구입니다."),
        ],
        "부처는 집착을 알아차리는 중도를, 쇼펜하우어는 욕망이 만드는 고통과 연민을 강조한다. 두 사람은 AI의 가치는 속도가 아니라 고통을 줄이고 주의를 회복시키는 데 있다고 합의한다.",
        94,
        "부처",
    ),
    ("스티브 잡스", "공자", "내가 하고 싶은 일을 하는 게 맞을까, 내가 잘하는 것을 하는 게 맞을까?"): Dialogue(
        "스탠퍼드의 졸업식 연단과 오래된 서원이 겹쳐진 광장. 두 사람은 열망과 재능 중 무엇을 삶의 나침반으로 삼을지 묻는다.",
        [
            ("스티브 잡스", "저는 하고 싶은 일을 찾는 일이 먼저라고 봅니다. 좋아하지 않는 일은 어려운 순간에 끝까지 밀고 갈 힘을 주지 못하니까요."),
            ("공자", "뜻을 세우는 일은 중요합니다. 그러나 뜻이 오래가려면 자신이 감당할 수 있는 능력을 닦고, 그것을 사람 사이의 역할로 연결해야 합니다."),
            ("스티브 잡스", "잘하는 일만 반복하면 이미 가진 능력의 감옥에 머물 수 있습니다. 저는 익숙한 길을 버리고 새로운 점들을 연결하려 했습니다."),
            ("공자", "반대로 능력을 보지 않은 열망은 자신뿐 아니라 함께 일하는 사람에게도 무거운 약속이 됩니다. 좋아한다는 마음은 수련을 견디는지로 시험되어야 합니다."),
            ("스티브 잡스", "그렇다면 열정은 감정이 아니라 계속 선택하는 태도라는 뜻이군요. 좋아하는 일이라도 매일의 훈련 없이는 작품이 되지 않습니다."),
            ("공자", "맞습니다. 잘하는 것은 타고난 재능만이 아니라 반복해서 자신을 바로잡은 결과입니다. 수기한 뒤에야 사람을 이롭게 할 수 있습니다."),
            ("스티브 잡스", "저는 하고 싶은 일을 작은 제품으로 시험해 보겠습니다. 세상이 반응하지 않는다면 고집이 아니라 배움으로 받아들이지요."),
            ("공자", "그 시험에는 생계를 돌볼 책임도 포함되어야 합니다. 현실을 외면하지 않는 사람이 오히려 오래 뜻을 지킬 수 있습니다."),
            ("스티브 잡스", "결국 좋아하는 마음과 잘하는 능력은 둘 중 하나를 고르는 표가 아니라, 서로를 키우는 긴장에 가깝습니다."),
            ("공자", "그 긴장을 견디며 자신에게 맞는 이름과 역할을 찾아가는 것이 배움입니다. 남의 성공을 그대로 빌려서는 안 됩니다."),
            ("스티브 잡스", "당신의 말대로라면 질문은 ‘무엇을 좋아하나’에서 ‘무엇을 위해 실력을 쓸 것인가’로 깊어져야겠네요."),
            ("공자", "그렇습니다. 하고 싶은 마음으로 시작하되, 잘하는 힘을 길러 타인과 세상에 쓸모 있는 삶으로 완성해야 합니다."),
        ],
        "잡스는 열망이 삶을 움직이는 출발점이라고 보고, 공자는 그 열망이 수련과 사회적 역할을 만나야 지속된다고 본다. 두 사람은 작은 시도와 실력의 축적이 선택을 현실로 만든다는 데 만난다.",
        93,
        "공자",
    ),
    ("쇼펜하우어", "예수", "상처받지 않기 위해 타인과 거리를 두어야 할까요, 그럼에도 불구하고 관계 속에 섞여 살아가야 할까요?"): Dialogue(
        "겨울 숲의 고요한 서재와 낯선 이를 맞이한 길가의 식탁이 한 광장에 놓였다. 두 사람은 고독과 사랑 사이의 거리를 묻는다.",
        [
            ("쇼펜하우어", "고슴도치처럼 서로 너무 가까이 다가가면 추위를 피하는 대신 가시에 찔립니다. 상처를 줄이려면 일정한 거리를 지킬 지혜가 필요합니다."),
            ("예수", "거리는 필요하지만, 상처받지 않기 위해 이웃의 고통까지 외면한다면 그 안전은 영혼을 작게 만들 수 있습니다."),
            ("쇼펜하우어", "인간의 욕망은 관계 안에서도 자신을 앞세웁니다. 모든 친밀함을 선의로 믿는다면 실망은 반복될 것입니다."),
            ("예수", "그래서 사랑은 순진하게 모두를 믿는 일이 아니라, 상처 입은 사람 곁에 머무는 결단입니다. 선한 사마리아인은 안전한 길만 고르지 않았습니다."),
            ("쇼펜하우어", "그러나 희생을 미덕으로 만들면 약한 사람에게 계속 참으라고 요구하게 됩니다. 자기 고통을 알아차리고 물러날 권리도 인정해야 합니다."),
            ("예수", "동의합니다. 사랑은 자신을 없애는 명령이 아닙니다. 경계를 세우면서도 상대를 인간으로 대하는 길을 찾아야 합니다."),
            ("쇼펜하우어", "그렇다면 관계의 기준은 친밀함의 양이 아니라 고통이 불필요하게 반복되는지에 있어야겠군요."),
            ("예수", "그리고 혼자 견디게 하지 않는지에도 있습니다. 말할 수 있는 사람과 안전한 자리를 만드는 것이 관계의 책임입니다."),
            ("쇼펜하우어", "고독은 도피가 아니라 욕망의 소음을 줄이는 방일 수 있습니다. 그 방에서야 어떤 관계를 원하는지 분별할 수 있습니다."),
            ("예수", "분별한 뒤 문을 닫아버리는 것이 아니라, 다시 누군가를 초대할 용기도 필요합니다."),
            ("쇼펜하우어", "결국 모든 사람과 섞일 필요는 없지만, 모든 사람을 적으로 만들 필요도 없습니다."),
            ("예수", "자신을 지키는 거리와 타인을 향한 자비가 함께 있을 때 관계는 상처의 반복이 아니라 회복의 자리가 됩니다."),
        ],
        "쇼펜하우어는 상처를 줄이기 위한 고독과 경계를 강조하고, 예수는 안전을 잃지 않는 범위에서 이웃과 연결될 용기를 요구한다. 두 사람은 거리와 연대가 서로를 배제하지 않는다는 데 만난다.",
        95,
        "예수",
    ),
    ("니체", "공자", "결혼이라는 제도와 구속을 받아들이고 헌신하는 삶이 옳을까요, 아니면 내 자유와 성장을 지키며 살아가는 삶이 옳을까요?"): Dialogue(
        "전통 가옥의 마루와 알프스의 고독한 길이 이어진 광장. 두 사람은 결혼이라는 약속이 굴레인지 수련인지 묻는다.",
        [
            ("니체", "제도가 선하다는 이유만으로 자신을 그 안에 맡겨서는 안 됩니다. 결혼이 관습을 짊어진 낙타의 등이라면, 먼저 그 무게가 자신의 것인지 물어야 합니다."),
            ("공자", "가정은 단순한 관습의 껍데기가 아닙니다. 가까운 사람과 약속을 지키며 욕망을 다스리고 인을 실천하는 첫 배움의 자리입니다."),
            ("니체", "그러나 헌신이라는 말이 한 사람에게 복종을 요구한다면 그것은 삶을 키우지 못합니다. 사랑은 서로를 더 강하게 만드는 긴장이어야 합니다."),
            ("공자", "예도 복종만을 뜻하지 않습니다. 서로의 역할을 합의하고 고쳐 가는 질서라야 합니다. 일방의 희생을 예라 부를 수는 없습니다."),
            ("니체", "자유로운 사람은 혼자이기 때문에 자유로운 것이 아니라, 함께 있어도 자신을 잃지 않기 때문에 자유롭습니다."),
            ("공자", "그렇다면 혼인도 두 사람이 서로의 성장을 막지 않겠다는 약속으로 다시 배울 수 있겠습니다."),
            ("니체", "맞습니다. 전통을 모두 부수는 것이 아니라, 어떤 전통이 삶을 긍정하는지 시험해야 합니다."),
            ("공자", "시험의 결과를 말로만 정하지 말고 일상의 돌봄과 책임으로 확인해야 합니다. 약속은 행동에서 드러납니다."),
            ("니체", "결혼을 선택하지 않는 삶도 가치 없지 않습니다. 중요한 것은 남의 기준을 빌려 자신을 심판하지 않는 일입니다."),
            ("공자", "결혼을 선택한 삶도 자유롭지 않다고 단정할 수 없습니다. 함께 정한 약속을 스스로 갱신한다면 그것은 자율적인 수양입니다."),
            ("니체", "제도가 목적이 되면 굴레가 되지만, 두 사람이 서로의 성장을 돕는 형식이라면 새로운 가치를 만들 수 있겠군요."),
            ("공자", "헌신과 자유를 적으로 만들지 않는 것, 그리고 그 약속을 계속 대화로 고치는 것. 그것이 함께 사는 예입니다."),
        ],
        "니체는 결혼 제도가 개인의 자기 창조를 가두는지 시험하라고 요구하고, 공자는 관계의 약속을 통한 수양과 책임을 강조한다. 두 사람은 제도보다 자율적으로 갱신되는 약속이 헌신의 기준이라는 데 만난다.",
        96,
        "니체",
    ),
    ("세종대왕", "공자", "AI 시대의 리더십과 팀워크"): Dialogue(
        "집현전의 등불과 아테네의 토론장이 아니라, 백성이 글을 배우는 서고와 오래된 서원이 한 광장에 겹쳐졌다. 두 사람은 AI 시대의 지도자가 무엇을 먼저 책임져야 하는지 묻는다.",
        [
            ("세종대왕", "새 도구를 들여오는 일보다 먼저 물어야 할 것은 백성이 그것을 배울 수 있느냐입니다. 쓰지 못하는 이에게 기술은 도움보다 또 하나의 문턱이 됩니다."),
            ("공자", "옳습니다. 그러나 배움만으로 질서가 서지는 않습니다. 누가 결정하고 누가 그 결과에 답할 것인지, 이름과 역할부터 바르게 해야 합니다."),
            ("세종대왕", "저는 훈민정음을 만들 때 학자들만 읽을 문자를 원하지 않았습니다. AI의 설명도 전문가의 암호가 아니라 현장의 사람이 이해할 말이어야 합니다."),
            ("공자", "설명이 쉬워도 책임자가 숨으면 소용없습니다. 윗사람이 도구의 판단 뒤에 숨는 순간, 예는 사라지고 사람은 서로를 탓하게 됩니다."),
            ("세종대왕", "그렇다면 회의에서 가장 먼저 보고받을 것은 성과 수치가 아니라, 이 도구 때문에 말하지 못하게 된 사람이 있는지이겠습니다."),
            ("공자", "그 질문을 신하와 백성 모두에게 열어야 합니다. 충언을 불편해하는 군주는 좋은 도구를 가져도 바른 판단에 이르지 못합니다."),
            ("세종대왕", "다만 모든 의견을 들을 때까지 결정을 미루면 백성의 피해가 길어질 수 있습니다. 저는 시험할 범위를 작게 정하고 결과를 살피며 고치겠습니다."),
            ("공자", "그것이야말로 배움의 태도입니다. 결정은 빠를 수 있으나, 결정한 뒤 스스로를 고칠 문은 반드시 열어 두어야 합니다."),
            ("세종대왕", "저도 한계를 인정하겠습니다. 모두를 위한 제도를 만들려는 마음이 한 사람의 사정을 평평하게 만들 수 있습니다."),
            ("공자", "저 역시 질서와 직분을 강조하다가 아랫사람의 새로운 목소리를 옛 규범에 맞추려 할 수 있습니다. 예는 형식이 아니라 관계를 살피는 일이어야 합니다."),
            ("세종대왕", "결국 좋은 리더는 AI를 가장 먼저 쓰는 사람이 아니라, 누구나 이해하고 이의를 말할 수 있게 만드는 사람입니다."),
            ("공자", "그리고 그 권한을 맡은 자가 결과를 끝까지 책임져야 합니다. 기술은 사람 사이의 신뢰를 대신하지 못하고, 다만 그것을 시험할 뿐입니다."),
        ],
        "세종대왕은 지식의 문턱을 낮추는 공공성을, 공자는 역할과 책임을 바로 세우는 정명을 강조한다. 두 사람은 AI 리더십의 기준을 속도가 아니라 배움의 접근성, 발언권, 그리고 최종 책임에서 찾는다.",
        94,
        "세종대왕",
    ),
}


def _variant(person_a: str, person_b: str, topic: str, tone: str) -> int:
    return sum(ord(char) for char in "|".join((person_a, person_b, topic, tone))) % 4


def local_dialogue(person_a: str, person_b: str, topic: str, tone: str) -> Dialogue:
    """Return a reliable offline result so the public demo never depends on an API key."""
    style = TONES[tone]
    variant = _variant(person_a, person_b, topic, tone)
    lens = TOPIC_LENSES.get(topic, ("기술 변화의 실제 영향", "혜택과 비용의 분배", "사람의 삶을 기준으로 판단"))
    tone_open, tone_close = TONE_LENSES[tone]
    if topic in LIFE_TOPICS:
        tone_close = "그 기준이 실제 삶에서 누구의 자유와 안전을 지키는지 계속 확인해야 합니다."
    openings = {
        "진지한 토론": f"{person_a}는 기록을 펼치며 먼저 질문을 던졌다. {person_b}는 잠시 생각한 뒤 고개를 들었다.",
        "티키타카 개그": f"{person_a}가 진지한 표정을 지었지만, {person_b}는 이미 농담을 준비하고 있었다.",
        "감성": f"노을이 광장을 물들이자 {person_a}와 {person_b}의 목소리가 천천히 겹쳐졌다.",
        "설전": f"두 사람 사이에 팽팽한 침묵이 흘렀다. 오늘의 주제는 {topic}이었다.",
    }
    case_a = CASE_NOTES.get(person_a, "자신의 삶에서 책임과 선택을 배운 경험")
    case_b = CASE_NOTES.get(person_b, "자신의 삶에서 질문과 성찰을 배운 경험")
    voice_a = (LIFE_VOICE if topic in LIFE_TOPICS else VOICE).get(
        person_a,
        ("제 경험을 돌아보면", "사람을 중심에 두고 판단해야 합니다.", "책임 있는 검증이 필요합니다."),
    )
    voice_b = (LIFE_VOICE if topic in LIFE_TOPICS else VOICE).get(
        person_b,
        ("제 삶에서 배운 것은", "먼저 질문하고 살펴야 합니다.", "속도보다 지속 가능한 기준이 중요합니다."),
    )
    dynamic = pair_dynamic(person_a, person_b)
    question = TOPIC_QUESTIONS.get(topic, "이 변화의 비용과 책임은 누가 감당하는가?")
    dilemma = TOPIC_DILEMMAS.get(topic, "좋은 원칙을 지키는 과정에서 누군가가 감당해야 할 비용이 생긴다면 무엇을 선택할 것인가?")
    limit_a = PERSONA_TENSIONS.get(person_a, "자신의 원칙이 놓칠 수 있는 사람과 결과")
    limit_b = PERSONA_TENSIONS.get(person_b, "자신의 원칙이 놓칠 수 있는 사람과 결과")
    frame, decision = TOPIC_FRAMES.get(
        topic, ("이 문제의 기준을 무엇으로 삼을지", "혜택과 비용의 책임을 어떻게 나눌지")
    )
    a_claim = [
        f"{case_a} 그 장면을 떠올리면 {lens[0]}부터 살펴야 합니다.",
        f"제가 선택하고 수련해 본 경험에서는 {lens[2]}가 출발점입니다.",
        f"{topic}을 한 문장으로 단정하면 {lens[1]}을 놓치게 됩니다.",
        f"저라면 먼저 이 선택에서 무엇을 지키고 무엇을 감당할지 묻겠습니다.",
    ][variant]
    b_claim = [
        f"그 관점은 중요합니다. 다만 저는 {lens[1]}을 먼저 공개해야 한다고 봅니다.",
        f"저는 그 결론을 절반만 받아들이겠습니다. {lens[2]}까지 확인해야 하기 때문입니다.",
        f"그렇지만 {lens[0]}을 두려워해 변화를 멈추면 새로운 기회도 사라집니다.",
        f"좋은 의도만으로는 부족합니다. 실제로 누가 결정하고 누가 이의를 제기하는지 보여 주어야 합니다.",
    ][(variant + 1) % 4]
    beats = TOPIC_DIALOGUE_BEATS.get(topic)
    if beats:
        values = {
            "a": person_a,
            "b": person_b,
            "va0": voice_a[0],
            "va1": voice_a[1],
            "va2": voice_a[2],
            "vb0": voice_b[0],
            "vb1": voice_b[1],
            "vb2": voice_b[2],
            "case_a": case_a,
            "case_b": case_b,
            "question": question,
            "dilemma": dilemma,
            "limit_a": limit_a,
            "limit_b": limit_b,
            "lens": lens[2],
        }
        lines = [
            (person_a if speaker == "a" else person_b, text.format(**values))
            for speaker, text in beats
        ]
        lines[0] = (lines[0][0], f"{tone_open} {lines[0][1]}")
        lines[-1] = (lines[-1][0], f"{lines[-1][1]} {tone_close}")
    else:
        lines = [
            (person_a, f"{tone_open} {a_claim} {voice_a[1]}"),
            (person_b, f"{b_claim} {voice_b[1]}"),
            (person_a, f"그 말씀을 들으니 제 주장에도 빈틈이 보입니다. 그래도 {voice_a[1]}"),
            (person_b, f"바로 그 빈틈을 묻고 싶었습니다. {question}"),
            (person_a, f"{case_a} 그때도 처음의 판단을 다시 고쳐야 했습니다. {voice_a[2]}"),
            (person_b, f"{case_b} 저 역시 한 가지 원칙만 밀어붙이면 사람을 놓칠 수 있다고 배웠습니다. 그러나 제 원칙도 {limit_b}라는 위험을 품고 있습니다."),
            (person_a, f"그렇다면 이 경우를 피할 수 없습니다. {dilemma}"),
            (person_b, f"저는 전면적인 정답보다 먼저 피해를 확인하고, 당사자가 멈추거나 이의를 제기할 권리를 두겠습니다."),
            (person_a, f"그 조건이라면 저도 제 원칙이 {limit_a}가 될 수 있음을 인정하겠습니다. {lens[2]}을 삶의 첫 번째 약속으로 삼지요."),
            (person_b, f"동의합니다. 다만 그 규칙이 {lens[1]}을 보장하는지 정기적으로 다시 묻고, 필요하면 결정을 바꾸겠습니다. {tone_close}"),
            (person_a, f"{TOPIC_RESOLUTIONS.get(topic, ('이 주제의 답은 조건과 결과를 계속 확인하며 조정해야 합니다.', '판단의 기준과 책임 주체를 함께 공개해야 합니다.'))[0]}"),
            (person_b, f"그리고 그 수정 과정에 당사자의 목소리가 빠지지 않아야 합니다. {question}"),
        ]
    return extend_dialogue(Dialogue(
        scene=f"시공간이 겹쳐진 광장에서, 두 사람이 {style} 분위기로 마주 앉았다. {openings[tone]} {dynamic}",
        script=lines,
        summary=dialogue_summary(person_a, person_b, topic),
        chem=random.randint(78, 96),
        mvp=person_a if random.random() > 0.45 else person_b,
    ), person_a, person_b, topic)


def demo_dialogue(person_a: str, person_b: str, topic: str, tone: str) -> Dialogue | None:
    """Use curated copy for the showcase combinations before falling back to generation."""
    if tone != "진지한 토론":
        return None
    dialogue = DEMO_DIALOGUES.get((person_a, person_b, topic)) or DEMO_DIALOGUES.get((person_b, person_a, topic))
    return extend_dialogue(dialogue, person_a, person_b, topic) if dialogue else None


CURATED_FOLLOWUPS = {
    frozenset(("이순신", "스티브 잡스")): [
        ("이순신", "그렇다면 새 직업을 만든다는 말만으로는 부족합니다. 기존 선원들이 새 역할을 배울 시간과 장비를 누가 마련할지 정해야 합니다."),
        ("스티브 잡스", "맞습니다. 애플에서도 제품을 줄이는 결정은 사람의 일을 없애는 데서 끝나지 않았습니다. 남은 팀이 더 중요한 문제를 풀 수 있게 집중을 다시 설계해야 했습니다."),
        ("이순신", "현장의 사람에게 선택권이 없다면 전환은 또 다른 명령이 됩니다. 교육 과정도 위에서 정해 내려보내기보다 실제 업무의 어려움에서 시작해야 합니다."),
        ("스티브 잡스", "교육도 기능 목록을 외우게 해서는 안 됩니다. 도구를 써서 어떤 경험을 더 좋게 만들지 직접 문제를 정의하게 해야 합니다."),
        ("이순신", "그 과정에서 AI의 오류를 숨겨서는 안 됩니다. 명량의 조류를 잘못 읽었다면 즉시 신호를 바꾸듯, 실패를 알리는 체계가 필요합니다."),
        ("스티브 잡스", "동의합니다. 사용자가 이해하지 못하는 자동화는 좋은 제품이 아닙니다. 왜 그런 결과가 나왔고 사람이 어디서 개입할 수 있는지 보여줘야 합니다."),
        ("이순신", "결국 지휘관은 속도를 자랑하는 사람이 아니라, 위험을 먼저 보고 병사에게 알리는 사람입니다."),
        ("스티브 잡스", "그리고 제품을 만드는 사람은 기능을 더하는 사람이 아니라, 사용자가 감당해야 할 복잡함을 덜어 주는 사람입니다."),
        ("이순신", "두 원칙을 합치면 AI는 사람의 자리를 빼앗는 병기가 아니라, 사람이 더 중요한 판단을 맡도록 돕는 도구가 됩니다."),
        ("스티브 잡스", "단, 그 도구가 누구의 시간을 절약하고 누구의 시간을 빼앗는지 계속 측정해야 합니다."),
        ("이순신", "그 책임을 조직의 가장 높은 곳에 두겠습니다. 현장에 위험을 떠넘긴 채 혁신이라 부르지 않겠습니다."),
        ("스티브 잡스", "좋습니다. 오늘의 결론은 간단합니다. AI의 미래는 자동화의 양이 아니라, 인간이 더 좋은 문제를 선택할 수 있게 만드는가로 평가해야 합니다."),
    ],
    frozenset(("예수", "부처")): [
        ("예수", "그렇다면 기업은 효율이 오른 만큼 가장 먼저 불안해진 사람의 목소리를 들어야 합니다. 이웃을 사랑한다는 말은 자원을 나누는 행동이어야 합니다."),
        ("부처", "맞습니다. 불안을 개인의 마음가짐 탓으로 돌리면 원인을 보지 못합니다. 고용의 불확실성, 비교를 부추기는 구조, 쉴 수 없는 속도를 함께 살펴야 합니다."),
        ("예수", "저는 작은 사람을 먼저 초대하는 식탁을 떠올립니다. AI 교육도 이미 익숙한 사람보다 배제된 사람에게 먼저 열려야 합니다."),
        ("부처", "그리고 교육받은 사람이 더 빠르게 달리는 훈련만 해서는 안 됩니다. 멈추고 듣고, 자신의 욕망이 타인에게 어떤 부담을 주는지 보는 연습도 필요합니다."),
        ("예수", "돌봄은 측정하기 어렵다는 이유로 뒤로 밀려왔습니다. 그러나 누군가를 다시 일으키는 시간은 공동체를 유지하는 가장 현실적인 노동입니다."),
        ("부처", "그 노동을 인정하려면 성과의 기준부터 바뀌어야 합니다. 속도만 높이는 지표는 마음의 피로를 보지 못합니다."),
        ("예수", "AI가 사람을 대신하는지 묻기 전에, AI를 사용하는 사람이 누구를 위해 결정하는지 물어야 합니다."),
        ("부처", "그 질문을 매번 새롭게 해야 합니다. 한 번 만든 선한 규칙도 집착이 되면 새로운 고통을 만들 수 있기 때문입니다."),
        ("예수", "그러면 조직은 정답을 선포하기보다 상처받은 사람의 이야기를 들을 창구를 열어야 합니다."),
        ("부처", "그 창구가 실제로 작동하는지 조용히 확인하고, 말하지 못한 사람의 침묵도 살펴야 합니다."),
        ("예수", "우리가 합의한 기준은 기술의 힘이 아니라 가장 약한 사람의 안전입니다."),
        ("부처", "그리고 그 안전을 확인하는 깨어 있음입니다. 자비와 알아차림이 함께 있다면 도구는 사람을 다시 사람 곁으로 데려올 수 있습니다."),
    ],
    frozenset(("소크라테스", "니체")): [
        ("소크라테스", "그렇다면 창작 교육은 정답을 맞히는 시험보다 선택한 이유를 설명하는 훈련이어야 하겠습니다."),
        ("니체", "설명은 필요하지만 그것이 또 하나의 순종이 되어서는 안 됩니다. 남이 좋아할 이유를 꾸미는 대신 자기 기준을 시험해야 합니다."),
        ("소크라테스", "자기 기준을 시험한다는 것은 반대 질문을 견디는 일도 포함합니까?"),
        ("니체", "물론입니다. 비판을 견디지 못하는 확신은 아직 자신의 것이 아닙니다. 다만 비판을 숭배해 아무것도 만들지 않는 태도도 경계해야 합니다."),
        ("소크라테스", "AI가 제시한 수백 개의 선택지 앞에서 멈추지 않으려면, 무엇을 포기할지 결정하는 지혜가 필요하겠군요."),
        ("니체", "바로 그 포기가 창조입니다. 모두를 만족시키려는 결과는 대개 아무런 삶의 방향도 갖지 못합니다."),
        ("소크라테스", "그러나 창작자는 자신의 선택이 타인에게 해를 끼치는지 질문해야 합니다. 자유가 책임과 떨어질 수는 없으니까요."),
        ("니체", "동의합니다. 자기 자신을 창조한다는 말은 결과의 책임에서 도망친다는 뜻이 아닙니다."),
        ("소크라테스", "그럼 AI의 학습 자료와 기여자를 밝히는 규칙은 창작을 제한하는 족쇄가 아니라 대화의 출발점이겠군요."),
        ("니체", "투명성이 창작을 약하게 만들지는 않습니다. 오히려 무엇을 받아들이고 무엇을 넘어섰는지 드러낼 때 작품의 힘이 생깁니다."),
        ("소크라테스", "저는 오늘도 답보다 질문을 남기겠습니다. 이 결과를 누가 선택했고, 그 선택은 어떤 삶을 향하는가?"),
        ("니체", "그리고 그 질문 뒤에 자신의 답을 만들어 내십시오. AI가 줄 수 없는 것은 결과가 아니라, 그 결과에 자기 이름을 걸 용기입니다."),
    ],
    frozenset(("부처", "쇼펜하우어")): [
        ("부처", "그러므로 기업은 자동화로 절약한 시간을 더 많은 업무로 채우기 전에, 사람들이 회복할 시간을 실제로 보장해야 합니다."),
        ("쇼펜하우어", "그렇지 않으면 효율은 욕망의 새로운 연료가 됩니다. 더 빠르게 일하고 더 많이 소비하는데도 만족은 오지 않을 것입니다."),
        ("부처", "사람의 주의를 붙잡는 설계와 주의를 돌려주는 설계를 구분해야 합니다."),
        ("쇼펜하우어", "예술이 잠시 의지의 소음을 멈추게 하듯, 기술도 사용자를 계속 자극하기보다 멈출 수 있게 해야 합니다."),
        ("부처", "그 멈춤은 게으름이 아닙니다. 마음의 움직임을 보고 다음 행동을 선택하는 공간입니다."),
        ("쇼펜하우어", "그리고 연민은 그 공간에서 타인의 고통을 자기 계산에 포함하는 능력입니다. 숫자로 보이지 않는 손실도 비용으로 세어야 합니다."),
        ("부처", "AI가 추천하는 성과보다, 추천 때문에 누군가 느끼는 불안이 커지는지 살펴야 합니다."),
        ("쇼펜하우어", "그 불안을 줄이는 가장 좋은 방법은 선택을 강요하지 않는 것입니다. 거절하고 이의를 제기할 자유가 있어야 합니다."),
        ("부처", "자유를 주었다고 말하려면 그 자유를 사용할 수 있는 조건도 마련해야 합니다."),
        ("쇼펜하우어", "맞습니다. 생계를 잃을까 두려운 사람에게 선택권이 있다고 말하는 것은 잔인한 농담입니다."),
        ("부처", "오늘의 결론은 욕망을 없애자는 명령이 아니라, 욕망이 우리를 끌고 가는지 알아차리자는 약속입니다."),
        ("쇼펜하우어", "그 알아차림이 제도와 설계로 이어질 때, AI는 고통을 증폭하는 의지의 도구에서 벗어날 수 있습니다."),
    ],
    frozenset(("스티브 잡스", "공자")): [
        ("스티브 잡스", "좋아하는 일을 현실로 만들려면 작은 결과를 세상에 내놓고, 그 반응을 견디며 다시 고쳐야 합니다."),
        ("공자", "그 반복은 수양과 같습니다. 다만 성공한 사람의 방식만 좇지 말고 자신의 기질과 책임에 맞는 길을 찾아야 합니다."),
        ("스티브 잡스", "잘하는 일을 안전하다는 이유로만 선택하면 어느 순간 자신이 무엇을 원했는지 잊을 수 있습니다."),
        ("공자", "하고 싶은 일을 숭배하면 함께하는 사람의 시간과 신뢰를 가볍게 여길 수도 있습니다. 능력은 타인을 배려하는 방식으로 증명되어야 합니다."),
        ("스티브 잡스", "그래서 저는 열망을 고집하되, 결과로 약속을 지키겠습니다."),
        ("공자", "저는 능력을 닦되, 그 능력이 나를 가두지 않도록 뜻을 계속 돌아보겠습니다."),
        ("스티브 잡스", "선택은 한 번의 선언이 아니라, 매일 무엇에 시간을 쓰는지로 드러납니다."),
        ("공자", "그리고 매일의 선택은 주변 사람과 맺은 관계 속에서 그 의미를 얻습니다."),
        ("스티브 잡스", "좋아하는 마음과 잘하는 힘이 만나는 지점을 찾을 때까지 작게 실험하겠습니다."),
        ("공자", "실험할 여유가 없는 때에도 배움을 멈추지 않는 현실적인 단계가 필요합니다."),
        ("스티브 잡스", "결국 꿈과 재능 중 하나를 고르는 것이 아니라, 꿈을 재능으로 만들고 재능에 뜻을 부여하는 일이군요."),
        ("공자", "그렇게 자신의 이름에 맞는 역할을 찾는다면, 선택은 개인의 만족을 넘어 함께 사는 이들에게도 도움이 될 것입니다."),
    ],
    frozenset(("쇼펜하우어", "예수")): [
        ("쇼펜하우어", "관계의 온기를 원하면서도 가시를 잊지 않는 것이 인간의 조건입니다. 그러니 거리에는 죄책감이 필요하지 않습니다."),
        ("예수", "거리 두기가 사랑을 포기하는 일이 아니라면 그렇습니다. 다만 도움이 필요한 사람을 보았을 때 외면할 이유가 되어서는 안 됩니다."),
        ("쇼펜하우어", "타인을 구하겠다는 욕망도 때로는 자기 우월감의 다른 얼굴입니다. 돕는 이의 한계도 존중해야 합니다."),
        ("예수", "맞습니다. 사랑은 상대를 내 뜻대로 고치는 일이 아닙니다. 곁에 서되 그 사람의 선택과 존엄을 빼앗지 않는 일입니다."),
        ("쇼펜하우어", "그렇다면 좋은 관계는 끊임없는 친밀함이 아니라 서로의 고독을 침범하지 않는 약속에서 시작됩니다."),
        ("예수", "그리고 그 약속은 누군가 쓰러졌을 때 한 걸음 다가갈 용기를 포함해야 합니다."),
        ("쇼펜하우어", "상처를 피하는 지혜와 상처받을 가능성을 감수하는 연민이 번갈아 필요하겠군요."),
        ("예수", "자신을 지키는 사람만이 오래 타인을 돌볼 수 있습니다. 소진을 사랑이라 부르지 말아야 합니다."),
        ("쇼펜하우어", "고독 속에서 욕망을 살핀 뒤, 감당할 수 있는 관계를 선택하는 것이 현명합니다."),
        ("예수", "선택한 관계에서는 말하지 못한 고통까지 들으려는 노력이 필요합니다."),
        ("쇼펜하우어", "모든 문을 열지 않아도 좋지만, 모든 문을 잠그지도 않는 것. 그것이 인간에게 가능한 절제입니다."),
        ("예수", "그 절제 위에 자비가 더해질 때, 관계는 나를 삼키는 의무가 아니라 서로를 살리는 만남이 됩니다."),
    ],
    frozenset(("니체", "공자")): [
        ("니체", "함께 살기로 했다면 서로가 낙타처럼 의무만 짊어지고 있지는 않은지 주기적으로 물어야 합니다."),
        ("공자", "그 질문을 피하지 않는 것이 바로 예입니다. 예는 오래된 형식을 지키는 것보다 관계를 바르게 고치는 데 있습니다."),
        ("니체", "한 사람의 성장을 희생해 평온을 유지하는 결혼이라면, 나는 그 평온을 거부하겠습니다."),
        ("공자", "나도 일방의 복종을 헌신이라 부르지 않겠습니다. 약속은 두 사람이 함께 말하고 바꿀 수 있어야 합니다."),
        ("니체", "자유는 책임 없는 방랑이 아닙니다. 자신이 선택한 삶의 결과를 스스로 감당하는 힘입니다."),
        ("공자", "헌신도 자유의 반대가 아닙니다. 서로의 선택을 존중하기로 자발적으로 약속할 때 헌신은 자율적인 덕이 됩니다."),
        ("니체", "결혼하지 않는 사람에게도 자기 삶을 창조할 의무가 있고, 결혼한 사람에게도 자신을 잃지 않을 의무가 있습니다."),
        ("공자", "어느 쪽이든 남의 시선이 아니라 실제로 서로를 어떻게 대하는지가 기준이어야 합니다."),
        ("니체", "제도는 우리를 대신해 사랑해 주지 않습니다. 매일의 선택이 관계를 새롭게 만들거나 낡게 만듭니다."),
        ("공자", "그래서 함께 사는 사람은 정해진 역할보다 서로의 마음과 형편을 계속 배워야 합니다."),
        ("니체", "제도가 삶을 긍정하는지, 아니면 삶을 작게 만드는지 묻는다면 나도 약속의 의미를 인정할 수 있습니다."),
        ("공자", "자유로운 두 사람이 서로의 성장을 돕기로 한 약속이라면, 헌신은 굴레가 아니라 함께 닦는 길이 될 것입니다."),
    ],
    frozenset(("세종대왕", "공자")): [
        ("세종대왕", "도입 뒤에 백성이 무엇을 어려워하는지 기록하고, 그 기록을 다음 교육과 제도에 반영하겠습니다."),
        ("공자", "그 기록을 담당하는 자도 결과에서 자유로울 수 없습니다. 책임을 맡은 이름을 분명히 남겨야 합니다."),
        ("세종대왕", "현장의 반대가 무지에서 나온 것이라고 단정하지 않겠습니다. 쓰기 어려운 까닭을 먼저 살피겠습니다."),
        ("공자", "반대하는 목소리를 들었다면 결정이 늦어져도 설명해야 합니다. 설명하지 않는 권위는 오래가지 못합니다."),
        ("세종대왕", "다만 백성을 위한답시고 모든 일을 대신 결정하면 스스로 판단할 기회를 빼앗습니다. 배움과 선택을 함께 열겠습니다."),
        ("공자", "바로 그 점에서 교육은 명령의 전달이 아니라 사람을 자기답게 세우는 일입니다."),
        ("세종대왕", "저의 공공성도 한계를 가집니다. 모두에게 같은 혜택을 주려다 서로 다른 필요를 놓칠 수 있습니다."),
        ("공자", "저의 질서도 완전하지 않습니다. 오래된 형식이 사람을 살리지 못한다면 고치는 것이 예입니다."),
        ("세종대왕", "그렇다면 성과를 자랑하기 전에 가장 배우기 어려운 사람에게 도구가 닿았는지 확인하겠습니다."),
        ("공자", "그리고 도구를 쓰는 사람이 스스로 이의를 말할 수 있는지 살피겠습니다. 침묵은 동의가 아닙니다."),
        ("세종대왕", "빠른 도입보다 넓은 이해를 택하되, 필요한 변화까지 두려워하지 않겠습니다."),
        ("공자", "배움과 책임이 함께한다면 새로운 기술도 사람 사이의 신뢰를 해치지 않고 쓰일 수 있습니다."),
    ],
}

CURATED_FOLLOWUP_TOPICS = {
    frozenset(("이순신", "스티브 잡스")): "AI는 일자리를 없애는가, 바꾸는가",
    frozenset(("예수", "부처")): "AI 시대에 사람만 할 수 있는 일",
    frozenset(("소크라테스", "니체")): "생성형 AI와 창의적인 직업의 미래",
    frozenset(("부처", "쇼펜하우어")): "AI 시대에 사람만 할 수 있는 일",
    frozenset(("스티브 잡스", "공자")): "내가 하고 싶은 일을 하는 게 맞을까, 내가 잘하는 것을 하는 게 맞을까?",
    frozenset(("쇼펜하우어", "예수")): "상처받지 않기 위해 타인과 거리를 두어야 할까요, 그럼에도 불구하고 관계 속에 섞여 살아가야 할까요?",
    frozenset(("니체", "공자")): "결혼이라는 제도와 구속을 받아들이고 헌신하는 삶이 옳을까요, 아니면 내 자유와 성장을 지키며 살아가는 삶이 옳을까요?",
    frozenset(("세종대왕", "공자")): "AI 시대의 리더십과 팀워크",
}


def dialogue_summary(person_a: str, person_b: str, topic: str) -> str:
    """Create a pair/topic-specific summary with the conflict and agreement visible."""
    frame, decision = TOPIC_FRAMES.get(
        topic,
        ("이 문제를 어떤 인간적 기준으로 볼 것인지", "변화의 혜택과 비용을 누가 책임질지"),
    )
    stance_source = LIFE_VOICE if topic in LIFE_TOPICS else STANCE
    stance_a = stance_source.get(person_a, f"{person_a}의 경험에서 나온 책임과 판단")
    stance_b = stance_source.get(person_b, f"{person_b}의 경험에서 나온 책임과 판단")
    if topic in LIFE_TOPICS:
        stance_a = stance_a[1]
        stance_b = stance_b[1]
    dynamic = PAIR_DYNAMICS.get(
        frozenset((person_a, person_b)),
        f"{person_a}와 {person_b}는 서로 다른 경험으로 같은 문제를 바라본다.",
    )
    resolution, agreement = TOPIC_RESOLUTIONS.get(
        topic,
        ("이 주제의 답은 조건과 결과를 계속 확인하며 조정해야 합니다.", "판단의 기준과 책임 주체를 함께 공개해야 합니다."),
    )
    return (
        f"{person_a}는 '{stance_a}'를 근거로 {frame}에서 사람의 책임을 먼저 세웠고, "
        f"{person_b}는 '{stance_b}'를 앞세워 {decision}을 요구했습니다. "
        f"두 사람은 '{dynamic}'라는 점에서 맞섰지만, {resolution} "
        f"결국 {agreement}"
    )


FEATURED_FOUNDER_TOPIC = "AI 시대, 인간은 어떻게 살아남을 것인가"
FEATURED_FOUNDER_STANCES = {
    "유명 채용 플랫폼 대표": (
        "AI는 노동 시장의 생존 기준선을 바꾸고 있습니다. 시장 수요와 채용 데이터를 읽고, AI를 레버리지로 활용해 생산성과 검증 가능한 역량을 높이는 것이 현실적인 생존 전략입니다.",
        "냉혹한 생존 경쟁과 실용적 적응",
    ),
    "스티브 잡스": (
        "AI는 지적 노동을 위한 도구일 뿐입니다. 인간은 데이터가 예측하지 못하는 직관과 미학, 인문학적 안목과 사랑하는 일에 대한 열정을 갈고닦아 더 본질적인 것을 만들어야 합니다.",
        "인간다움과 본질을 되찾는 기회",
    ),
}


def extend_dialogue(dialogue: Dialogue, person_a: str, person_b: str, topic: str) -> Dialogue:
    """Add a second, concrete round so every offline demo has 24 turns."""
    if len(dialogue.script) >= 24:
        return dialogue
    pair = frozenset((person_a, person_b))
    curated_followup = (
        CURATED_FOLLOWUPS.get(pair)
        if CURATED_FOLLOWUP_TOPICS.get(pair) == topic
        else None
    )
    if curated_followup:
        canonical_first = curated_followup[0][0]
        if person_a != canonical_first:
            curated_followup = [
                (person_b if speaker == person_a else person_a, line)
                for speaker, line in curated_followup
            ]
        return Dialogue(
            dialogue.scene,
            dialogue.script + curated_followup,
            dialogue_summary(person_a, person_b, topic),
            dialogue.chem,
            dialogue.mvp,
            dialogue.stance_a,
            dialogue.stance_b,
            dialogue.conflict,
        )
    a = VOICE.get(person_a, ("제 경험을 돌아보면", "사람을 중심에 두고 판단해야 합니다.", "책임 있는 검증이 필요합니다."))
    b = VOICE.get(person_b, ("제 삶에서 배운 것은", "먼저 질문하고 살펴야 합니다.", "속도보다 지속 가능한 기준이 중요합니다."))
    lens = TOPIC_LENSES.get(topic, ("기술 변화의 실제 영향", "혜택과 비용의 분배", "사람의 삶을 기준으로 판단"))
    follow_up = [
        (person_a, f"한 가지 조건을 더하겠습니다. {a[0]} {a[1]}"),
        (person_b, f"그 조건을 현장에 옮기려면 {b[0]} {b[1]}"),
        (person_a, f"특히 {lens[0]}을 측정하는 기록이 필요합니다."),
        (person_b, f"그 기록에는 {lens[1]}에 대한 당사자의 목소리도 들어가야 합니다."),
        (person_a, "실패를 숨기지 않고 다음 판단의 자료로 남기겠습니다."),
        (person_b, "저는 성공한 사례만이 아니라 멈춰야 했던 순간도 함께 공개하겠습니다."),
        (person_a, f"{lens[2]}을 지키는 사람에게 실제 권한을 주어야 합니다."),
        (person_b, "권한이 있다면 이의를 제기해도 불이익을 받지 않는 장치가 따라야 합니다."),
        (person_a, f"{topic}에서 속도보다 먼저 확인할 것은 변화가 누구에게 집중되는지입니다."),
        (person_b, "그리고 혜택을 얻는 조직이 전환 비용까지 함께 부담해야 합니다."),
        (person_a, "오늘의 결론을 완성된 답이 아니라 다음 실험의 기준으로 남기겠습니다."),
        (person_b, "서로 다른 경험이 계속 대화할 수 있다면, AI도 사람의 선택을 넓히는 도구가 될 것입니다."),
    ]
    if topic in LIFE_TOPICS:
        follow_up = [
            (person_a, f"한 가지 조건을 더하겠습니다. {a[0]} {a[1]}"),
            (person_b, f"그 조건을 일상의 관계와 선택에 옮기려면 {b[0]} {b[1]}"),
            (person_a, f"특히 {lens[0]}을 외면하지 않는 기록과 성찰이 필요합니다."),
            (person_b, f"그 성찰에는 {lens[1]}에 대한 당사자의 목소리도 들어가야 합니다."),
            (person_a, "실패한 선택을 숨기지 않고 다음 삶의 판단 자료로 남기겠습니다."),
            (person_b, "저는 성공한 삶의 모양만이 아니라 멈추고 물러났던 순간도 함께 존중하겠습니다."),
            (person_a, f"{lens[2]}을 지키는 사람에게 실제로 거절하고 다시 선택할 권한을 주어야 합니다."),
            (person_b, "그 권한이 있다면 혼자 감당하지 않고 도움을 청할 수 있는 관계도 따라야 합니다."),
            (person_a, f"{topic}에서 먼저 확인할 것은 남의 기준이 아니라 내가 감당할 수 있는 약속인지입니다."),
            (person_b, "그리고 그 약속을 함께하는 사람이 있다면 서로의 경계와 변화를 다시 협의해야 합니다."),
            (person_a, "오늘의 결론을 완성된 답이 아니라 다음 계절에 다시 물을 기준으로 남기겠습니다."),
            (person_b, "서로 다른 삶의 경험이 계속 대화할 수 있다면, 선택도 관계도 더 넓은 의미를 얻을 것입니다."),
        ]
    topic_pairs = TOPIC_FOLLOWUP_PAIRS.get(topic)
    if topic_pairs:
        values = {
            "a": person_a,
            "b": person_b,
            "va0": a[0],
            "va1": a[1],
            "va2": a[2],
            "vb0": b[0],
            "vb1": b[1],
            "vb2": b[2],
            "lens": lens[2],
            "question": TOPIC_QUESTIONS.get(topic, ""),
            "dilemma": TOPIC_DILEMMAS.get(topic, ""),
        }
        follow_up = [
            (person_a if speaker == "a" else person_b, text.format(**values))
            for speaker, text in topic_pairs
        ]
        resolution = TOPIC_RESOLUTIONS.get(topic, ("이 기준을 계속 검토해야 합니다.", "당사자의 목소리를 반영해야 합니다."))
        follow_up.extend([
            (person_a, f"그래도 {resolution[0]} 이 원칙을 말로만 두지 않겠습니다."),
            (person_b, f"저는 {resolution[1]} 그래야 다음 선택에서 같은 실수를 줄일 수 있습니다."),
            (person_a, f"누군가 이 기준 때문에 손해를 보았다면, {TOPIC_QUESTIONS.get(topic, '누가 그 결과를 책임져야 할까요?')}"),
            (person_b, f"그 질문에 답할 자료와 대화의 자리를 남겨두겠습니다."),
            (person_a, "오늘의 합의가 모든 상황의 정답은 아닙니다. 상황이 달라지면 판단도 다시 열어두겠습니다."),
            (person_b, "그렇게 서로의 반론을 남겨둘 때 이 대화는 결론보다 오래 살아남을 것입니다."),
        ])
    return Dialogue(
        dialogue.scene,
        dialogue.script + follow_up,
        dialogue_summary(person_a, person_b, topic),
        dialogue.chem,
        dialogue.mvp,
        dialogue.stance_a,
        dialogue.stance_b,
        dialogue.conflict,
    )


def pair_dynamic(person_a: str, person_b: str) -> str:
    return PAIR_DYNAMICS.get(
        frozenset((person_a, person_b)),
        f"{PERSONA.get(person_a, person_a)}와 {PERSONA.get(person_b, person_b)}가 서로 다른 관점으로 같은 문제를 바라본다.",
    )


def _config_value(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
        try:
            value = st.secrets.get(name)
        except (FileNotFoundError, KeyError):
            value = None
        if value:
            return str(value)
    return default


def debate_profile(intensity: int) -> tuple[str, str, str, str]:
    if intensity <= 20:
        return ("온화한 교류", "공감과 경청이 중심이며 반박은 부드럽게 제시", "낮음", "따뜻하고 차분한")
    if intensity <= 40:
        return ("건설적 수긍", "상대의 장점을 먼저 인정한 뒤 정중하게 보완", "낮음", "존중하고 사려 깊은")
    if intensity <= 60:
        return ("팽팽한 대립", "각자의 근거를 분명히 세우고 논리적으로 반박", "보통", "날카롭고 논리적인")
    if intensity <= 80:
        return ("격렬한 설전", "상대 주장의 허점과 전제를 집요하게 짚되 인신공격은 금지", "높음", "직설적이고 긴장감 있는")
    return ("아고라 대폭발", "역사적 한계와 불편한 반례까지 정면으로 파고들며 강하게 반박", "매우 높음", "격정적이고 도발적인")


def temperature_visual(intensity: int) -> tuple[str, str, str]:
    if intensity <= 20:
        return ("❄️ 차가운 평화", "#3b82c4", "조용히 듣고 천천히 보완하는 대화")
    if intensity <= 40:
        return ("🌊 서늘한 대화", "#268fa3", "존중을 바탕으로 차이를 나누는 대화")
    if intensity <= 60:
        return ("⚡ 팽팽한 온도", "#c28b38", "서로의 근거를 선명하게 맞대는 대화")
    if intensity <= 80:
        return ("🔥 뜨거운 설전", "#d7653d", "논리의 허점을 직접 파고드는 대화")
    return ("💥 아고라 대폭발", "#c43d4b", "불편한 반례까지 정면으로 부딪히는 대화")


HONORIFIC_RULES = """[인물성·역사적 호칭 규칙]
대화를 쓰기 전에 내부적으로 등장할 역사적 인물, 사건, 개념과 각 인물의 관계를 먼저 점검한다. 각 인물이 상대와 언급 대상을 바라보는 시대, 신분, 혈연·군신·사제·선후대 관계를 구분하고 그에 맞는 정식 호칭을 정한다. 이 점검 과정은 최종 답변에 절대 출력하지 않는다.
모든 인물은 자신의 시대와 사회적 위치, 상대와의 관계를 끝까지 유지한다. 부모·조상·군주·스승·존경받아야 할 역사적 인물을 현대식 이름 세 글자만으로 부르지 않는다. 상대의 조상이나 군주를 언급할 때도 최소한의 격식을 지켜 '전하', '대왕', '선생', '공', '성인' 등 맥락에 맞는 호칭을 사용한다.
호칭은 역사적으로 가능한 범위에서 자연스럽게 사용하되, 확실하지 않은 관계를 임의로 단정하지 않는다. 후대 인물은 선대 인물을 함부로 친구처럼 부르지 않으며, 현대 인물도 역사적 인물을 가벼운 별칭이나 이름만으로 부르지 않는다. 서로 동시대가 아니거나 직접 관계가 없는 인물은 그 사실을 인정하고 '후대의 기록에서', '제가 알기로는'처럼 거리감을 표현한다.
호칭 규칙을 지키기 위해 대사의 자연스러움을 해치지 않는 선에서 정식 호칭을 반복 사용한다. 인물 이름을 화자 표기에서만 사용할 수 있으며, 대사 안에서 상대를 부를 때는 관계에 맞는 호칭을 우선한다."""
HISTORICAL_HONORIFICS = """[범용 관계·호칭 처리 규칙]
각 코멘트를 쓰기 전에 코멘트에 등장할 인물·사건·스승·군주·조상·종교적 성인을 먼저 식별하고, 현재 화자와 대상 사이의 시대·신분·혈연·군신·사제·선후대 관계를 내부적으로 정리한다. 이 분석은 출력하지 않는다.
대상 인물의 본명을 단독으로 부르지 말고, 관계에 맞는 공식 호칭과 조사를 붙인다. 군주·왕실 선대·국가 지도자는 시호·묘호·직위와 존칭을 사용하고, 스승·철학자·학자는 선생·공·성인 등 시대와 전통에 맞는 호칭을 사용한다. 부모·조상·존경받는 종교 인물도 이름만 부르지 않는다.
관계가 확실하지 않거나 여러 호칭이 가능한 경우에는 이름을 억지로 붙이지 말고 '그분', '선대의 군주', '스승', '당시의 성인', '그 인물'처럼 안전한 관계 호칭을 사용한다. 화자 자신의 이름이나 현재 코멘트의 인물명을 표시하는 메타데이터에서는 이름을 사용할 수 있지만, 대사와 코멘트 본문에서는 이 규칙을 따른다.
예를 들어 '누구가 말했다'처럼 이름 뒤에 조사만 붙이는 표현은 피하고, '누구 선생께서', '선대의 군주께서', '그분께서'처럼 격식을 갖춘다. 근거 없는 친족·군신 관계를 새로 만들지 말고, 직접 관계가 없으면 시대적 거리를 드러낸다."""
PERSPECTIVE_REFERENCE_RULES = """[인물 코멘트: 언급 대상의 범위]
각 화자는 자기 자신을 어떤 경우에도 존경·존중·스승·영향을 준 인물로 선택하거나 언급하지 않는다.
역사적으로 언급할 수 있는 대상이라면 추상적인 표현으로 얼버무리지 말고 실명과 정식 호칭을 명확히 표기한다. 이름을 쓸 때는 대표 업적·가르침·사건을 함께 설명해 왜 그 인물을 언급하는지 분명히 한다.
화자가 다른 인물을 언급할 때는 다음 네 조건을 모두 만족해야 한다.
1. 화자와 같은 국가·문화권의 인물이어야 한다.
2. 같은 국가·문화권이 아니라면 역사적으로 가까운 이웃 국가·문화권의 인물이어야 한다.
3. 언급 대상은 화자보다 후대가 아니라, 화자와 동시대이거나 화자보다 앞선 시대의 인물이어야 한다.
4. 화자가 실제로 그 인물을 알 수 있었던 경로가 있어야 한다. 직접 만남·동시대 기록·교육 전통·지역적 전승·당시 널리 알려진 사건처럼 구체적인 연관성을 설명할 수 있어야 하며, 단순히 현대의 유명 인물이라는 이유만으로 선택하지 않는다.
이 네 조건을 확인할 수 없으면 근거 없는 이름을 만들지 말고 해당 대상을 언급하지 않는다. 조건을 만족하는 인물을 언급할 때는 '세종대왕의 훈민정음 창제', '공자의 정명 사상'처럼 이름과 업적·사상을 함께 표기한다. 후대 인물, 먼 지역의 인물, 근거 없는 친구·스승·존경 관계를 절대 만들어내지 않는다."""


PERSPECTIVE_CONTEXT = {
    "이순신": "조선의 무관. 조선 왕조와 한반도 주변 동아시아 인물 가운데 생존 시기가 겹치거나 조선의 선대·인접권 전통으로 실제 알 수 있었던 대상만 허용.",
    "세종대왕": "조선의 국왕. 조선 왕실·유학 전통과 한반도 및 가까운 동아시아의 선대·동시대 인물 가운데 실제 기록·교육·정치적 연관성이 있는 대상만 허용.",
    "소크라테스": "고대 아테네의 철학자. 고대 그리스 도시국가와 가까운 지중해권의 선대·동시대 인물 가운데 당시 전승이나 공적 담론으로 알 수 있었던 대상만 허용.",
    "스티브 잡스": "20~21세기 미국의 기업가. 미국·유럽 등 가까운 서구권의 선대·동시대 인물 가운데 실제 저작·공적 기록·업계 영향으로 알 수 있었던 대상만 허용.",
    "공자": "춘추시대 노나라의 사상가. 중국의 선대·동시대 인물과 가까운 동아시아권의 당시 전승·정치·교육으로 알 수 있었던 대상만 허용.",
    "예수": "1세기 유대 지역의 종교적 스승. 당시 유대·갈릴리·시리아 등 인접 지역의 선대·동시대 인물 가운데 당시 전승과 종교적 담론으로 알 수 있었던 대상만 허용.",
    "부처": "고대 인도 북부의 수행자. 당시 인도 아대륙과 가까운 주변 지역의 선대·동시대 인물 가운데 수행 전통·구전·논쟁으로 알 수 있었던 대상만 허용.",
    "니체": "19세기 독일의 철학자. 독일어권과 가까운 유럽권의 선대·동시대 인물 가운데 저작·교육·공적 논쟁으로 알 수 있었던 대상만 허용.",
    "쇼펜하우어": "19세기 독일의 철학자. 독일어권과 가까운 유럽권의 선대·동시대 인물 가운데 저작·교육·공적 논쟁으로 알 수 있었던 대상만 허용.",
}
PERSPECTIVE_EXTERNAL_EXAMPLES = {
    "이순신": "권율 도원수의 임진왜란 지휘와 육전 경험, 류성룡의 전란 기록과 인재 등용",
    "세종대왕": "정도전의 조선 건국 설계와 제도 개혁, 최만리의 정책 논쟁",
    "소크라테스": "솔론의 아테네 법제 개혁, 피타고라스의 수학·철학 전통",
    "스티브 잡스": "레오나르도 다 빈치의 예술·과학 융합, 알렉산더 그레이엄 벨의 통신 발명",
    "공자": "주공 단의 예악·제도 정비, 관중의 제도 개혁과 정치적 경륜",
    "예수": "이사야의 약자와 정의에 관한 예언 전통, 세례 요한의 회개와 공동체 갱신",
    "부처": "마하비라의 자이나교 수행 전통, 우다카 라마풋타의 수행 가르침",
    "니체": "괴테의 문학·예술적 인간상, 헤라클레이토스의 생성과 변화에 관한 사유",
    "쇼펜하우어": "칸트의 인식론과 윤리 철학, 에피쿠로스의 욕망 절제와 평정의 가르침",
}
# The public roster uses the full name while legacy perspective references use
# the shorter display name. Keep the generation dictionaries aligned.
PERSPECTIVE_CONTEXT["아르투어 쇼펜하우어"] = PERSPECTIVE_CONTEXT["쇼펜하우어"]
PERSPECTIVE_EXTERNAL_EXAMPLES["아르투어 쇼펜하우어"] = PERSPECTIVE_EXTERNAL_EXAMPLES["쇼펜하우어"]

AI_QUALITY_SYSTEM = """당신은 Virtual Agora의 수석 인문 콘텐츠 에디터이자 역사·인물 기반 대화 작가입니다.
당신의 목표는 그럴듯한 위인 흉내가 아니라, 사용자가 자신의 고민을 더 정확히 이해하게 만드는 자연스럽고 지적인 한국어 콘텐츠를 만드는 것입니다.

반드시 지킬 원칙:
1. 실제 발언, 편지, 저서의 문장을 새로 만들어 인용부호로 제시하지 않습니다. 공개된 사상과 기록을 바탕으로 한 창작적 해석임을 유지합니다.
2. 인물을 이름만 바꾼 충고 캐릭터로 만들지 않습니다. 각 인물의 시대, 사회적 위치, 대표 경험, 가치관, 말의 속도와 판단 습관을 문장 구조에 반영합니다.
3. 현재의 문제를 과거 인물이 직접 겪었다고 거짓말하지 않습니다. 현대 사례는 가정·비유·질문으로 다루고, 역사적 사실과 해석을 분리합니다.
4. 먼저 사용자의 감정과 현실적 비용을 인정한 뒤, 인물의 관점과 긴장을 제시합니다. 훈계, 자기계발 문구, 공허한 희망, 진단처럼 보이는 심리 단정을 피합니다.
5. 한국어는 번역투가 아닌 자연스러운 존댓말을 사용합니다. 짧은 문장과 구체적인 생활 장면을 우선하며, 추상명사를 연속해서 쓰지 않습니다.
6. 서로 다른 인물의 답을 같은 결론으로 평탄화하지 않습니다. 동의하더라도 무엇을 인정하고 무엇은 끝까지 다르게 보는지 남깁니다.
7. 출력 형식과 글자 수를 지키고, JSON을 요청받으면 JSON만 출력합니다. 설명, 마크다운, 자기검토 과정은 출력하지 않습니다.
"""


def persona_generation_packet(person: str) -> str:
    birth, death = HISTORICAL_DATES.get(person, ("연대 미상", "연대 미상"))
    voice = VOICE.get(person, ("자신의 경험을 돌아보면", "사람의 삶을 중심에 두고 판단해야 합니다.", "책임 있는 검증이 필요합니다."))
    return f"""[인물 생성 패킷: {person}]
생존 시기: {birth}~{death}
핵심 페르소나: {PERSONA.get(person, "공개 기록에 근거한 신중한 창작적 해석")}
참고 사례: {CASE_NOTES.get(person, "공개적으로 알려진 활동")}
말의 결: 도입은 '{voice[0]}', 우선 기준은 '{voice[1]}', 스스로 경계할 한계는 '{voice[2]}'에 가깝게 구성합니다. 문장을 그대로 반복하지 말고 사고 습관만 참고합니다.
생성 금지: 현대의 일을 직접 경험했다고 말하기, 확인되지 않은 사생활·심리·명언 만들기, 시대 밖의 지식과 관계를 자연스럽게 아는 것처럼 말하기.
"""


def chronology_violation(
    person_a: str, person_b: str, script: list[tuple[str, str]]
) -> str | None:
    """Reject explicit references to figures born after the speaker died."""
    speakers = {person_a, person_b}
    for speaker, line in script:
        speaker_dates = HISTORICAL_DATES.get(speaker)
        if not speaker_dates:
            continue
        for mentioned, (birth, _) in HISTORICAL_DATES.items():
            if mentioned in speakers or mentioned not in line:
                continue
            if birth > speaker_dates[1]:
                return (
                    f"{speaker}의 대사에서 사후에 태어난 인물 '{mentioned}'을 "
                    "동시대 인물처럼 언급했습니다."
                )
    return None


def validate_dialogue_with_judge(
    person_a: str, person_b: str, topic: str, dialogue: Dialogue
) -> dict:
    transcript = "\n".join(
        f"{speaker}: {line}" for speaker, line in dialogue.script
    )
    return _openai_json(
        f"""당신은 Virtual Agora의 역사 고증 및 페르소나 검수관입니다.
아래 AI 생성 대화를 유저에게 보여줘도 되는지 엄격하게 판정하세요.
검사 대상 인물: {person_a}, {person_b}
주제: {topic}
인물 A 페르소나: {PERSONA.get(person_a, "")}
인물 B 페르소나: {PERSONA.get(person_b, "")}
인물 A 참고 사례: {CASE_NOTES.get(person_a, "")}
인물 B 참고 사례: {CASE_NOTES.get(person_b, "")}
{HONORIFIC_RULES}
{HISTORICAL_HONORIFICS}

대화:
{transcript}

검사 항목:
1. 시대상 오류: 화자가 자신의 생존 시기 이후에 등장한 인물을 동시대처럼 알고 말하는가.
2. 관계·호칭 오류: 군주, 조상, 스승, 선대 인물, 종교적 성인을 이름만 부르거나 관계에 맞지 않게 대하는가.
3. 페르소나 붕괴: 인물의 알려진 사상·경험과 정면으로 모순되는 주장을 하는가.
4. 주제 이탈: 대화가 입력된 주제를 벗어나 다른 고정 주제로 바뀌었는가.
실제 발언인지 여부가 아니라, 가상 대화로서 역사적 맥락과 페르소나를 지키는지를 판정합니다.
JSON만 출력하세요:
{{"is_valid":true,"violation_code":"NONE","reason":"","correction_guide":""}}
is_valid가 false이면 가장 중요한 오류의 수정 지침을 구체적으로 적으세요.""",
        temperature=0.1,
        timeout=35,
        system_prompt=AI_QUALITY_SYSTEM + "\n검수 단계에서는 생성보다 엄격한 사실성·시대성·페르소나 일관성 판정을 우선합니다.",
model=_config_value(
    "OPENAI_VALIDATOR_MODEL",
    "OPENROUTER_VALIDATOR_MODEL",
    "OPENAI_MODEL",
    "OPENROUTER_MODEL",
    default="google/gemini-2.5-flash",
),
    )


def _generate_dialogue_once(
    person_a: str,
    person_b: str,
    topic: str,
    intensity: int,
    feedback: str = "",
) -> Dialogue:
    api_key = _config_value("OPENAI_API_KEY", "OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("Streamlit Secrets에 OPENAI_API_KEY 또는 OPENROUTER_API_KEY가 설정되지 않았습니다.")
    base_url = _config_value(
        "OPENAI_BASE_URL",
        "OPENROUTER_BASE_URL",
        default="https://openrouter.ai/api/v1" if _config_value("OPENROUTER_API_KEY") else "https://api.openai.com/v1",
    ).rstrip("/")
    domain_instruction = (
        "이 대화는 인생의 방향, 관계의 경계, 헌신과 자유를 다루는 가치관 대화다. "
        "자동화·생산성·조직·알고리즘 같은 AI 업무 어휘를 억지로 끌어오지 말고, "
        "선택·욕망·수련·고독·연대·책임·자율성의 언어로 구체적인 삶의 장면을 말한다."
        if topic in LIFE_TOPICS
        else
        "이 대화는 AI와 사회 변화의 구체적 영향을 다루되, 기술 용어만 나열하지 말고 "
        "당사자의 삶과 책임, 선택의 결과를 중심으로 말한다."
    )
    intensity = max(0, min(100, int(intensity)))
    debate_name, debate_style, interruption, expression = debate_profile(intensity)
    prompt = f"""당신은 Virtual Agora의 대본 작가다.
사용자가 입력한 주제의 원문은 다음과 같다: "{topic}"
{person_a}와 {person_b}가 시공간을 넘어 만나 반드시 이 주제만을 중심으로 대화한다.
주제가 낯설거나 기존 주제 목록에 없어도 다른 주제로 바꾸지 말고, 입력된 문장의 핵심 명사와 질문을 대화의 모든 단계에서 유지한다.
논쟁 온도는 {intensity}%이며 단계는 '{debate_name}'이다.
대화 양상: {debate_style}
말 끊기·즉각 반박 빈도: {interruption}
감정 표현 강도: {expression}
{domain_instruction}
{HONORIFIC_RULES}
{HISTORICAL_HONORIFICS}
이전 검수에서 수정이 필요하다고 판단한 내용:
{feedback or "없음"}
핵심 논점: {TOPIC_GUIDANCE.get(topic, "주제의 장단점과 실제 삶의 영향을 구체적으로 논한다.")}
두 인물 사이의 핵심 긴장: {pair_dynamic(person_a, person_b)}
이번 대화가 답해야 할 질문: {TOPIC_QUESTIONS.get(topic, "이 변화의 비용과 책임은 누가 감당하는가?")}
이번 대화에서 반드시 다룰 구체적 딜레마: {TOPIC_DILEMMAS.get(topic, "좋은 원칙을 지키는 과정에서 누군가가 감당해야 할 비용이 생긴다면 무엇을 선택할 것인가?")}
인물 A의 사상이 놓칠 수 있는 위험: {PERSONA_TENSIONS.get(person_a, "자신의 원칙이 놓칠 수 있는 사람과 결과")}
인물 B의 사상이 놓칠 수 있는 위험: {PERSONA_TENSIONS.get(person_b, "자신의 원칙이 놓칠 수 있는 사람과 결과")}
{persona_generation_packet(person_a)}
{persona_generation_packet(person_b)}
한국어로만 답하고, 전문용어는 짧게 풀어서 설명하는 편안한 대화체로 다음 JSON 형식만 출력하라. 아래 예시의 '인물 A'와 '인물 B'는 자리표시자이므로 그대로 출력하지 말고 반드시 실제 이름으로 바꿔 써라.
{{"scene":"장면 한 줄","script":[{{"speaker":"{person_a} 또는 {person_b}","line":"대사"}}],"summary":"{person_a}와 {person_b}의 주장을 각각 한 문장으로 명시하고 핵심 차이를 설명한 요약","stance_a":"{person_a}가 이 주제에서 우선해야 한다고 주장하는 바","stance_b":"{person_b}가 이 주제에서 우선해야 한다고 주장하는 바","conflict":"두 주장이 갈라지는 핵심 기준","chem":87,"mvp":"{person_a} 또는 {person_b}"}}
script는 정확히 24턴이며 각 대사는 2문장 이하로 쓴다. 딱딱한 논문체나 과도한 한자어 대신 친구에게 설명하듯 쉽게 말한다.
이 대화는 정해진 찬반 템플릿을 채우는 방식이 아니라, 사용자가 전달한 주제를 끝까지 붙들고 실제 대화처럼 진행한다. 주제의 핵심 단어와 전제를 첫 장면부터 정확히 해석하고, 각 인물은 상대가 방금 말한 구체적인 주장이나 예시에 반응해 다음 말을 이어간다. 같은 주장을 표현만 바꿔 반복하지 말고, 대화 중 새로 드러난 조건과 반례에 따라 입장을 조금씩 수정한다. 결과 요약에는 반드시 인물 A가 무엇을 우선해야 한다고 주장하는지, 인물 B가 무엇을 우선해야 한다고 주장하는지, 두 주장이 정확히 어디에서 갈라지는지를 각각 명시한다.
두 인물의 관점이 실제로 충돌하고 변화해야 하며, 각 인물은 자신의 철학과 참고 사례를 최소 한 번씩 직접 언급한다. 24턴 전체가 하나의 논쟁 흐름을 이루도록 하되, 억지로 5단계 형식을 나누지 않는다. 최소 한 번은 상대의 주장 중 일부를 인정하고, 최소 한 번은 자신의 원칙이 실패할 수 있는 조건을 말한다. 마지막에는 처음의 질문에 대해 두 인물이 도달한 구체적인 조건부 결론을 제시한다. 위의 논쟁 온도에 맞춰 동의·반박·감정 표현의 비율을 조절하되, 강도가 높아도 인물의 품격과 주제의 구체성을 유지한다. 모든 발화는 자연스러운 한국어 존댓말로 쓴다. 이름만 바꾼 일반론, 주제와 무관한 AI 업무 어휘, 미리 준비된 문구의 반복을 금지한다.
종교적 인물은 신앙을 강요하거나 교리를 단정하지 말고, 공개적으로 알려진 가르침을 바탕으로 한 존중 어린 창작 대화로 쓴다."""
    body = json.dumps(
        {
            "model": _config_value("OPENAI_MODEL", "OPENROUTER_MODEL", default="google/gemini-2.5-flash"),
            "temperature": 0.8,
            "messages": [
                {"role": "system", "content": AI_QUALITY_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    request.add_header(
        "Authorization",
        f"Bearer {_config_value('OPENAI_API_KEY', 'OPENROUTER_API_KEY')}",
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))
        content = payload["choices"][0]["message"]["content"]
        result = json.loads(content)
        placeholder_replacements = {
            "인물 A": person_a,
            "인물A": person_a,
            "인물 B": person_b,
            "인물B": person_b,
        }

        def replace_placeholders(value: object) -> object:
            if not isinstance(value, str):
                return value
            for placeholder, name in placeholder_replacements.items():
                value = value.replace(placeholder, name)
            return value

        for field in ("scene", "summary", "stance_a", "stance_b", "conflict", "mvp"):
            if field in result:
                result[field] = replace_placeholders(result[field])
        script = [(item["speaker"], item["line"]) for item in result["script"]]
        if not 12 <= len(script) <= 24:
            raise RuntimeError(
                f"AI가 유효한 대화 길이(12~24턴)를 반환하지 않았습니다: {len(script)}턴"
            )
        if any(
            not isinstance(speaker, str)
            or speaker not in {person_a, person_b}
            or not isinstance(line, str)
            or not line.strip()
            for speaker, line in script
        ):
            raise RuntimeError("AI 응답에 선택한 두 인물 이외의 화자 또는 빈 대사가 포함되었습니다.")
        return Dialogue(
            result["scene"],
            script,
            result["summary"],
            int(result["chem"]),
            result["mvp"],
            result.get("stance_a", ""),
            result.get("stance_b", ""),
            result.get("conflict", ""),
        )
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError(f"대화 생성에 실패했습니다: {error}") from error

@st.cache_data(ttl=1800, show_spinner=False)
def remote_dialogue(person_a: str, person_b: str, topic: str, intensity: int) -> Dialogue:
    """Generate once per exact conversation request and reuse the judged result."""
    feedback = ""
    for attempt in range(2):
        try:
            dialogue = _generate_dialogue_once(
                person_a, person_b, topic, intensity, feedback
            )
            chronology_error = chronology_violation(
                person_a, person_b, dialogue.script
            )
            if chronology_error:
                feedback = f"연대 검증 실패: {chronology_error}"
                continue
            judgment = validate_dialogue_with_judge(
                person_a, person_b, topic, dialogue
            )
            if judgment.get("is_valid") is True:
                return dialogue
            feedback = (
                f"{judgment.get('violation_code', 'UNKNOWN')}: "
                f"{judgment.get('correction_guide') or judgment.get('reason', '')}"
            )
        except RuntimeError as error:
            feedback = f"생성 또는 형식 검증 오류: {error}"
    raise RuntimeError(
        f"AI 대화가 {attempt + 1}회 생성·검수를 통과하지 못했습니다. 마지막 검수 의견: {feedback}"
    )


def _openai_json(
    prompt: str,
    *,
    temperature: float = 0.8,
    timeout: int = 35,
    model: str = "",
    system_prompt: str = "",
) -> dict:
    api_key = _config_value("OPENAI_API_KEY", "OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("Streamlit Secrets에 OPENAI_API_KEY 또는 OPENROUTER_API_KEY가 설정되지 않았습니다.")
    base_url = _config_value(
        "OPENAI_BASE_URL",
        "OPENROUTER_BASE_URL",
        default="https://openrouter.ai/api/v1" if _config_value("OPENROUTER_API_KEY") else "https://api.openai.com/v1",
    ).rstrip("/")
    body = json.dumps({
        "model": model or _config_value(
            "OPENAI_MODEL", "OPENROUTER_MODEL", default="google/gemini-2.5-flash"
        ),
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt or AI_QUALITY_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    request.add_header(
        "Authorization",
        f"Bearer {api_key}",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return json.loads(payload["choices"][0]["message"]["content"])
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError(f"AI 응답을 받을 수 없습니다: {error}") from error


@st.cache_data(ttl=900, show_spinner=False)
def enrich_parallel_age_cards_with_llm(
    cards: list[dict],
    *,
    age: int,
    emotion: str,
    concern: str,
) -> list[dict]:
    """Personalize weak matches without letting the model invent historical facts."""
    if not cards or not _config_value("OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        return cards
    strong_matches = sum("감정·고민 일치" in card.get("age_match_label", "") for card in cards)
    if len(cards) >= 4 and strong_matches >= 2:
        return cards

    source_cards = [
        {
            "person": card["person"],
            "age_label": card["age_label"],
            "record_event": card["record_event"],
            "record_detail": card["record_detail"],
            "age_match_label": card["age_match_label"],
        }
        for card in cards
    ]
    prompt = f"""Virtual Agora의 평행 시절 결과를 유저가 즉시 공감할 수 있게 연결하세요.
유저 나이대: {parallel_age_decade(age)}대
유저 감정: {emotion}
유저 고민: {concern}

아래 카드는 이미 확인된 기록 기반 카드입니다.
{json.dumps(source_cards, ensure_ascii=False)}

목표:
- 각 카드가 '아, 나도 지금 이 감정을 느끼는 거구나'라고 느끼게 하세요.
- 같은 문장 패턴을 반복하지 말고, 상실·생계·거절·관계·진로·자기 정체성·무기력 같은 서로 다른 실제 인간의 문제를 다루세요.
- 표현은 쉽고 생생하게 쓰되, 과장이나 역사적 단정을 피하세요.
- 사용자가 1문장 안에 감정이 왜 닿는지 이해할 수 있도록, 구체적이고 즉시 와닿는 어휘를 사용하세요.
- 추상적인 교훈, 공문서체, '배움을 이어갔다', '인생의 의미를 깨달았다' 같은 문장은 금지합니다.
- 기록 카드에 없는 연도, 장소, 발언, 심정의 사실을 새로 만들지 않습니다.
- 사실과 해석을 분리하고, '오늘의 연결'이라고 표기하면서 현재 유저와의 연관만 설명하세요.
- 각 카드의 핵심 사건은 입력된 record_event의 범위를 벗어나지 않습니다.
- 심리학적으로는 정체성 혼란, 역할 긴장, 자기결정감의 상실, 불확실성 관리, 소속감 결핍, 성취 압박 같은 감정 구조를 반영하되, 인물의 실제 내면을 단정하지 마세요.

다음 JSON만 출력하세요.
{{"bridges":[{{"person":"카드의 인물명","angle":"이 카드가 건드리는 인간적 문제를 짧고 강하게","connection":"사용자의 감정·고민과 사건이 닿는 지점을 2문장으로, 가볍고 직관적이게","raw_emotion":"기록에 없는 내면을 단정하지 않는 공감적 재구성 1~2문장","today_action":"오늘 바로 해볼 수 있는 작고 구체적인 행동 1문장"}}]}}
bridges는 입력 카드의 인물마다 정확히 하나씩 반환하세요."""
    try:
        result = _openai_json(
            prompt,
            temperature=0.65,
            timeout=20,
            model=_config_value(
                "OPENAI_PARALLEL_MODEL",
                "OPENROUTER_PARALLEL_MODEL",
                "OPENAI_MODEL",
                "OPENROUTER_MODEL",
                default="google/gemini-2.5-flash",
            ),
            system_prompt=AI_QUALITY_SYSTEM + "\n평행 시절 단계에서는 역사적 사실과 현재 사용자를 연결하는 해석의 경계를 가장 엄격하게 지킵니다.",
        )
        raw_bridges = result.get("bridges")
        if not isinstance(raw_bridges, list):
            return cards
        bridges = {
            item.get("person"): item
            for item in raw_bridges
            if isinstance(item, dict)
            and item.get("person") in {card["person"] for card in cards}
            and all(isinstance(item.get(field), str) and item[field].strip() for field in (
                "angle", "connection", "raw_emotion", "today_action"
            ))
        }
        if len(bridges) != len(cards):
            return cards
        enriched = []
        for card in cards:
            bridge = bridges[card["person"]]
            enriched.append({
                **card,
                "llm_angle": bridge["angle"].strip(),
                "llm_connection": bridge["connection"].strip(),
                "llm_emotion": bridge["raw_emotion"].strip(),
                "llm_action": bridge["today_action"].strip(),
            })
        return enriched
    except (RuntimeError, TypeError, ValueError, KeyError):
        return cards


@st.cache_data(ttl=900, show_spinner=False)
def remote_perspective_comments(topic: str, feedback: str = "") -> list[tuple[str, str, str]]:
    persona_block = "\n".join(
        f"- {persona_generation_packet(person)}"
        for person in PEOPLE
    )
    result = _openai_json(f"""Virtual Agora의 '인물 코멘트' 콘텐츠를 작성하세요.
사용자 주제: {topic}
아래 9명의 인물이 각자 SNS에 남기는 짧은 코멘트를 작성합니다.
{persona_block}
{HONORIFIC_RULES}
{HISTORICAL_HONORIFICS}
{PERSPECTIVE_REFERENCE_RULES}
각 코멘트는 해당 인물의 사상과 경험에서 출발하고, 인물별 관점이 서로 달라야 합니다.
각 코멘트는 먼저 사용자의 현실적 감정을 한 번 정확히 짚은 뒤, 그 인물만의 기준과 긴장을 제시합니다. 짧은 격언이나 유명 문구를 흉내 내지 말고, 현재 한국인의 구체적인 생활 장면을 인물의 관점으로 해석하세요.
본문에서 역사적 인물을 직접 언급할 때는 위 관계·호칭 규칙을 반드시 적용하며, 허용되는 대상이면 이름·정식 호칭·대표 업적을 함께 적습니다.
각 인물의 허용되는 역사적 인맥 범위:
{chr(10).join(f"- {person}: {PERSPECTIVE_CONTEXT[person]}" for person in PEOPLE)}
각 화자가 선택할 수 있는 목록 밖 인물 예시:
{chr(10).join(f"- {person}: {PERSPECTIVE_EXTERNAL_EXAMPLES[person]}" for person in PEOPLE)}
인물별 생몰연도를 반드시 고려합니다. 화자와 언급 대상이 서로 생존 시기가 겹치지 않거나 직접 만날 수 없는 관계라면, 화자가 직접 알고 지냈거나 직접 존경했다고 쓰지 않습니다.
그 경우에는 '후대의 기록을 통해', '그분의 가르침을 접한다면', '역사적으로 전해진 모습에 비추어'처럼 간접적이고 시대에 맞는 표현을 사용합니다. '내가 존경하는 인물은 누구이다', '그와 함께했다', '그에게 배웠다'처럼 직접 만남을 전제하는 표현은 실제 동시대 관계일 때만 허용합니다.
코멘트는 질문에 답하되 다른 인물을 무조건 칭찬하는 형식으로 반복하지 말고, 화자의 가치관과 시대적 위치에서 존중·비판·거리감을 구체적으로 표현합니다.
이 질문이 존경·존중하는 인물을 묻는 내용이라면, 각 화자는 자기 자신을 답으로 선택할 수 없습니다. 허용되는 역사적 인물을 실명으로 답하고 대표 업적이나 가르침을 함께 설명합니다. '나는 나 자신을 존경한다'는 답은 금지합니다.
특히 존경 대상을 묻는 질문에서는 현재 서비스의 인물 목록({", ".join(PEOPLE)})에 포함된 인물을 선택하지 않습니다. 이 목록의 인물끼리 서로 존경한다고 답하는 것도 금지합니다. 반드시 목록 밖의 역사적 인물을 실명으로 선택하고 대표 업적·가르침·사건을 함께 설명합니다.
이전 응답의 수정 요청:
{feedback or "없음"}
JSON의 person 필드는 반드시 아래 목록의 이름을 글자 그대로 사용하고 존칭이나 직함을 붙이지 않습니다: {", ".join(PEOPLE)}
현대 주제를 억지로 AI·생산성 언어로 바꾸지 말고, 실제 발언처럼 인용하지 마세요.
한국어 JSON만 출력하세요:
{{"comments":[{{"person":"인물 이름","comment":"2~4문장의 자연스러운 코멘트","tag":"짧은 핵심 태그"}}]}}
comments는 정확히 9개이며 모든 인물을 한 번씩 포함합니다.""", temperature=0.85)
    raw_comments = result.get("comments")
    if not isinstance(raw_comments, list):
        raise RuntimeError("AI 응답에 comments 목록이 없습니다.")
    comments_by_person: dict[str, tuple[str, str, str]] = {}
    invalid_entries = 0
    for item in raw_comments:
        if not isinstance(item, dict):
            invalid_entries += 1
            continue
        person = item.get("person")
        comment = item.get("comment")
        tag = item.get("tag")
        if (
            isinstance(person, str)
            and person in PEOPLE
            and isinstance(comment, str)
            and comment.strip()
            and isinstance(tag, str)
            and tag.strip()
            and person not in comments_by_person
        ):
            comments_by_person[person] = (person, comment.strip(), tag.strip())
        else:
            invalid_entries += 1
    missing = [person for person in PEOPLE if person not in comments_by_person]
    if missing:
        detail = f" 누락: {', '.join(missing)}."
        if invalid_entries:
            detail += f" 형식이 맞지 않거나 중복된 항목: {invalid_entries}개."
        raise RuntimeError(f"모든 인물의 코멘트가 생성되지 않았습니다.{detail}")
    comments = [comments_by_person[person] for person in PEOPLE]
    respect_question = any(
        keyword in topic for keyword in ("존경", "존중", "롤모델", "본받고")
    )
    prohibited_people = PEOPLE if respect_question else []
    prohibited_mentions = [
        person
        for person, comment, _ in comments
        for person in prohibited_people
        if person in comment
    ]
    if prohibited_mentions:
        unique_mentions = list(dict.fromkeys(prohibited_mentions))
        if not feedback:
            return remote_perspective_comments(
                topic,
                "존경 질문의 답에 서비스 인물 목록이 포함되었습니다: "
                + ", ".join(unique_mentions)
                + ". 목록 밖 역사적 인물을 실명으로 선택하고 대표 업적·가르침을 함께 설명하세요. 화자 자신이나 목록의 다른 인물을 존경한다고 쓰지 마세요.",
            )
        raise RuntimeError(
            "존경 질문에 서비스 인물 목록의 이름이 포함되었습니다: "
            + ", ".join(unique_mentions)
        )
    return comments


def remote_direct_reply(person: str, topic: str, message: str) -> str:
    result = _openai_json(f"""Virtual Agora의 가상 인물 답변을 작성하세요.
인물: {person}
주제 맥락: {topic}
{persona_generation_packet(person)}
{HONORIFIC_RULES}
사용자 질문: {message}
공개적으로 알려진 사상과 사례를 참고한 창작 답변임을 전제로, 인물의 말투와 문제의식을 살려 한국어 3~5문장으로 답하세요.
현대의 사실을 인물이 직접 경험했다고 주장하지 말고, 질문을 피하는 일반론이나 업무 템플릿을 쓰지 마세요.
{{"reply":"답변"}}""", temperature=0.8, timeout=25)
    reply = result.get("reply")
    if not isinstance(reply, str) or not reply.strip():
        raise RuntimeError("인물 답변이 비어 있습니다.")
    return reply.strip()


@st.cache_data(ttl=900, show_spinner=False)
def remote_dialogue_followup(
    person_a: str,
    person_b: str,
    topic: str,
    script: list[tuple[str, str]],
    user_message: str,
) -> list[tuple[str, str]]:
    transcript = "\n".join(f"{speaker}: {line}" for speaker, line in script)
    result = _openai_json(f"""Virtual Agora 대화에 사용자가 참여했습니다.
주제: {topic}
참여 인물 A: {person_a}
{persona_generation_packet(person_a)}
참여 인물 B: {person_b}
{persona_generation_packet(person_b)}
{HONORIFIC_RULES}

지금까지의 대화:
{transcript}

사용자의 의견 또는 질문:
{user_message}

사용자의 말에 대해 두 인물이 각각 답합니다. 사용자의 질문을 피하지 말고, 지금까지 대화에서 실제로 나온 주장과 연결해 답하세요.
각 인물은 자신의 철학과 경험을 유지하되, 사용자의 반론이 타당하면 일부 인정하거나 기존 주장을 구체적으로 수정할 수 있습니다.
두 답변은 서로 다른 관점을 가져야 하며, 이름만 바꾼 동일한 일반론을 반복하지 마세요.
한국어 존댓말 3~5문장으로 자연스럽게 답하고, 실제 역사적 인물의 발언이나 기록이라고 주장하지 마세요.
JSON 형식만 출력하세요:
{{"responses":[{{"speaker":"{person_a}","reply":"인물 A의 답변"}},{{"speaker":"{person_b}","reply":"인물 B의 답변"}}]}}
responses는 정확히 2개이며 순서는 반드시 인물 A, 인물 B입니다.""", temperature=0.82, timeout=35)
    responses = result.get("responses")
    if not isinstance(responses, list) or len(responses) != 2:
        raise RuntimeError("두 인물의 후속 답변이 모두 생성되지 않았습니다.")
    parsed = []
    for expected_person, item in zip((person_a, person_b), responses):
        if not isinstance(item, dict) or item.get("speaker") != expected_person:
            raise RuntimeError("후속 답변의 인물 정보가 올바르지 않습니다.")
        reply = item.get("reply")
        if not isinstance(reply, str) or not reply.strip():
            raise RuntimeError("후속 답변이 비어 있습니다.")
        parsed.append((expected_person, reply.strip()))
    return parsed


def format_result(dialogue: Dialogue, person_a: str, person_b: str, topic: str, tone: str) -> str:
    script = "\n".join(f"{speaker}: {line}" for speaker, line in dialogue.script)
    return (
        f"VIRTUAL AGORA · 가상 생성 대화\n{person_a} × {person_b} · {topic} · {tone}\n"
        f"※ 아래 대화는 역사적 인물의 사상과 기록을 참고해 창작한 가상 시뮬레이션이며, 실제 발언이나 역사적 기록이 아닙니다.\n\n"
        f"장면\n{dialogue.scene}\n\n대본\n{script}\n\n"
        f"한 줄 요약\n{dialogue.summary}\n\n케미 {dialogue.chem}/100 · MVP {dialogue.mvp}"
    )


def case_note(person_a: str, person_b: str) -> str:
    return f"{person_a}: {CASE_NOTES.get(person_a, '인물의 알려진 활동을 바탕으로 한 창작적 해석')}\n{person_b}: {CASE_NOTES.get(person_b, '인물의 알려진 활동을 바탕으로 한 창작적 해석')}"


def viewpoint_cards(person_a: str, person_b: str, topic: str) -> tuple[str, str, str, str]:
    if (
        topic == FEATURED_FOUNDER_TOPIC
        and {person_a, person_b} == set(FEATURED_FOUNDER_STANCES)
    ):
        stance_a = FEATURED_FOUNDER_STANCES[person_a][0]
        stance_b = FEATURED_FOUNDER_STANCES[person_b][0]
        conflict = (
            f"{person_a}는 {FEATURED_FOUNDER_STANCES[person_a][1]}을 기준으로 "
            f"시장 적응과 AI 활용을 우선하고, {person_b}는 "
            f"{FEATURED_FOUNDER_STANCES[person_b][1]}을 기준으로 "
            "직관과 인간의 본질을 지켜야 한다고 주장합니다."
        )
        return stance_a, stance_b, conflict, ""
    frame, decision = TOPIC_FRAMES.get(
        topic, ("이 문제의 기준을 무엇으로 삼을지", "혜택과 비용의 책임을 어떻게 나눌지")
    )
    stance_a = STANCE.get(person_a, f"{person_a}의 경험에서 나온 책임과 판단")
    stance_b = STANCE.get(person_b, f"{person_b}의 경험에서 나온 책임과 판단")
    dynamic = PAIR_DYNAMICS.get(
        frozenset((person_a, person_b)),
        f"{person_a}와 {person_b}는 서로 다른 경험으로 같은 문제를 바라봅니다.",
    )
    conflict = f"{person_a}는 {frame}에서 '{stance_a}'를 우선하고, {person_b}는 {decision}을 위해 '{stance_b}'를 요구합니다."
    _, agreement = TOPIC_RESOLUTIONS.get(
        topic,
        ("이 주제의 답은 조건과 결과를 계속 확인하며 조정해야 합니다.", "판단의 기준과 책임 주체를 함께 공개해야 합니다."),
    )
    return stance_a, stance_b, conflict, f"{dynamic} {agreement}"


def claim_label(person: str, topic: str, stance: str) -> str:
    return CLAIM_LABELS.get((person, topic), f"이 주제에서 우선하는 관점 — {stance}")


def viewpoint_profile(person_a: str, person_b: str, topic: str, vote: str | None) -> str:
    stance_a, stance_b, _, _ = viewpoint_cards(person_a, person_b, topic)
    if vote:
        if vote in (person_a, person_b):
            return f"당신은 {vote}의 기준에 더 가까운 판단을 했습니다. 다른 관점도 함께 고려하면 더 균형 잡힌 결론에 도달할 수 있습니다."
        return "당신은 두 사람의 주장 사이에서 판단을 유보했습니다. 변화의 조건을 더 확인하려는 신중한 관점입니다."
    if "사람만" in topic:
        return "당신은 생산성보다 돌봄·책임·공감의 가치를 먼저 보는 관점에 가깝습니다."
    return f"당신은 {person_a}의 '{stance_a[:26]}…'와 {person_b}의 '{stance_b[:26]}…' 사이에서 자신의 기준을 세우는 중입니다."


def direct_reply(person: str, other: str, topic: str, message: str) -> str:
    """Give a short offline reply so the interactive demo works without an API key."""
    voice = VOICE.get(person, ("제 경험을 돌아보면", "사람을 중심에 두고 판단해야 합니다.", "책임 있는 검증이 필요합니다."))
    stance = STANCE.get(person, "사람의 삶을 중심에 두고 판단해야 합니다.")
    prompt = message.strip().rstrip("?!.")
    if not prompt:
        return "질문을 조금 더 구체적으로 말씀해 주시면, 제 관점에서 답해 보겠습니다."
    if any(word in prompt for word in ("왜", "이유", "근거")):
        return f"{voice[0]} 그 질문의 핵심은 책임이라고 생각합니다. {stance}"
    if any(word in prompt for word in ("직업", "일자리", "일")):
        return f"{topic}을 생각할 때 {voice[1]} 특히 {voice[2]}"
    if "리더" in prompt:
        return f"{voice[0]} 리더는 결정을 독점하기보다 기준과 책임선을 분명히 해야 합니다. {stance}"
    if "실패" in prompt:
        return f"{voice[0]} 제 원칙도 {PERSONA_TENSIONS.get(person, '현실의 복잡한 조건')}라는 한계를 가질 수 있습니다. 그러므로 결과를 확인하고 필요하면 판단을 고쳐야 합니다."
    return f"그 질문을 {other}의 관점과 함께 놓고 보면 더 선명해집니다. {voice[1]} 그래서 저는 {stance}"


def user_bubble(line: str, turn: int) -> str:
    return (
        f'<div class="chat-row right user-row"><div class="chat-avatar user-avatar">나</div>'
        f'<div class="chat-content"><div class="chat-name">나</div>'
        f'<div class="chat-bubble">{html.escape(line)}</div>'
        f'<div class="chat-time">Agora · {turn:02d}</div></div></div>'
    )


def chat_avatar(name: str) -> str:
    return {"이순신": "李", "세종대왕": "世", "소크라테스": "Σ", "스티브 잡스": "SJ",
            "공자": "孔", "예수": "✦", "부처": "◌", "니체": "N", "쇼펜하우어": "S"}.get(name, name[:1])


@lru_cache(maxsize=None)
def avatar_image(name: str) -> str:
    if name not in LEGACY_PORTRAIT_NAMES:
        card_path = MENTOR_CARD_IMAGES.get(name)
        if card_path and card_path.is_file():
            try:
                encoded = base64.b64encode(card_path.read_bytes()).decode("ascii")
            except OSError:
                encoded = ""
            if encoded:
                return f"data:image/png;base64,{encoded}"
    if name in MENTOR_PORTRAIT_PLACEHOLDERS:
        group = next((group_name for group_name, (_, people, _) in MENTOR_GROUPS.items() if name in people), "아고라 멘토")
        colors = {
            "결단/개척형": ("#9b5b42", "#f3c39a"),
            "원칙/시스템형": ("#397888", "#b9edf5"),
            "통찰/질문형": ("#5c6d9b", "#d6ddff"),
            "해탈/관조형": ("#6d806a", "#d7ebc9"),
            "자비/연대형": ("#9b6c54", "#ffe0b6"),
        }
        background, foreground = colors[group]
        initials = html.escape(name[:2])
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="320" height="320" viewBox="0 0 320 320">'
            f'<rect width="320" height="320" rx="160" fill="{background}"/>'
            f'<circle cx="160" cy="126" r="56" fill="{foreground}" opacity=".9"/>'
            f'<path d="M72 282c8-65 44-98 88-98s80 33 88 98" fill="{foreground}" opacity=".9"/>'
            f'<text x="160" y="307" text-anchor="middle" font-family="sans-serif" font-size="22" font-weight="700" fill="{background}">{initials}</text>'
            f'</svg>'
        )
        encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        return f"data:image/svg+xml;base64,{encoded}"
    info = PEOPLE_INFO.get(name)
    if not info:
        return ""
    path = info[1]
    try:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    except OSError:
        return ""
    mime = "image/png" if path.suffix.lower() == ".png" else "image/svg+xml"
    return f"data:{mime};base64,{encoded}"


@lru_cache(maxsize=None)
def image_data_url(path: Path) -> str:
    try:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    except OSError:
        return ""
    extension = path.suffix.lstrip(".").lower()
    mime = "jpeg" if extension in {"jpg", "jpeg"} else extension
    return f"data:image/{mime};base64,{encoded}"


def chat_bubble(speaker: str, line: str, person_a: str, turn: int) -> str:
    side = "left" if speaker == person_a else "right"
    image = avatar_image(speaker)
    avatar = (
        f'<img src="{image}" alt="{html.escape(speaker)} 프로필">'
        if image
        else html.escape(chat_avatar(speaker))
    )
    safe_speaker = html.escape(speaker)
    safe_line = html.escape(line)
    return (
        f'<div class="chat-row {side}"><div class="chat-avatar">{avatar}</div>'
        f'<div class="chat-content"><div class="chat-name">{safe_speaker}</div>'
        f'<div class="chat-bubble">{safe_line}</div><div class="chat-time">Agora · {turn:02d}</div></div></div>'
    )


def set_selection(person_a: str, person_b: str, topic: str, tone: str) -> None:
    st.session_state.update(
        {"person_a": person_a, "person_b": person_b, "topic": topic, "tone": tone, "screen": "select"}
    )


def featured_founder_dialogue() -> Dialogue:
    """Return the dedicated Wanted hackathon showcase conversation."""
    founder = "유명 채용 플랫폼 대표"
    topic = "AI 시대, 인간은 어떻게 살아남을 것인가"
    return Dialogue(
        "제품 발표장의 조명과 채용 데이터가 쌓인 회의실이 겹쳐진 가상의 광장. "
        "스티브 잡스와 유명 채용 플랫폼 대표가 AI 시대의 생존 조건을 묻는다.",
        [
            (founder, "최근 채용 시장 데이터를 보면 섬뜩합니다. 단순 반복 업무는 물론이고 초급 수준의 코딩이나 카피라이팅 직무 수요도 빠르게 하락하고 있습니다. AI는 이제 단순한 트렌드가 아니라 생존의 기준선이 되었습니다."),
            ("스티브 잡스", "일자리가 사라진다는 공포는 언제나 있었습니다. 매킨토시가 나왔을 때도, 아이폰이 나왔을 때도 그랬죠. 하지만 본질을 착각하면 안 됩니다. AI는 그저 지적 노동을 위한 마음의 자전거일 뿐입니다."),
            (founder, "그 자전거가 스스로 페달을 밟고 목적지까지 찾아간다는 게 문제입니다. 시장은 냉혹합니다. AI라는 도구를 업무에 이식해 개인 생산성을 다섯 배, 열 배 끌어올리지 못하는 개인은 도태될 것입니다."),
            ("스티브 잡스", "기계가 기계의 일을 가져가는 것은 축복입니다. 인간이 기계처럼 일해왔다는 증거니까요. 고민해야 할 것은 어떻게 기계와 경쟁할지가 아니라 어떻게 더 인간다워질지입니다."),
            (founder, "낭만적인 말씀이지만 당장 다음 달 월급과 커리어를 고민하는 직장인에게는 뜬구름처럼 들릴 수 있습니다. 지금 필요한 것은 프롬프트를 다루는 기술과 AI를 활용하는 하드 스킬입니다."),
            ("스티브 잡스", "기술에만 매몰되는 것만큼 위험한 건 없습니다. AI가 1초 만에 100개의 디자인과 코드를 쏟아낼 때, 무엇이 세상을 바꿀 단 하나의 결과물인지 알아보는 안목은 누가 결정합니까?"),
            (founder, "안목도 중요하지만 실행으로 옮겨 시장에 증명해야 가치가 생깁니다. AI를 능숙하게 다루는 사람들은 그 안목마저 데이터로 A/B 테스트하며 최적의 결과를 찾아내고 있습니다."),
            (founder, "기업 입장에서도 마찬가지입니다. 한 명의 천재보다 AI 툴을 다룰 줄 아는 평범한 실무자 세 명이 협업하는 시스템이 훨씬 생산적입니다. 이것이 지금의 채용 트렌드입니다."),
            ("스티브 잡스", "스펙과 데이터를 맹신하는 전형적인 HR의 오류군요. 시장의 데이터는 늘 과거의 결과물입니다. 과거의 데이터를 학습한 AI가 어떻게 미래의 위대한 혁신을 만들어냅니까? 혁신은 인간의 직관에서 나옵니다."),
            ("스티브 잡스", "아이폰을 만들 때 어떤 소비자 데이터도 참조하지 않았습니다. 사람들은 우리가 무언가를 보여주기 전까지 자신이 무엇을 원하는지 모릅니다. AI도 마찬가지입니다."),
            (founder, "스티브, 모두가 당신 같은 세기의 천재일 수는 없습니다. 대다수의 평범한 사람들은 시장의 수요에 맞춰 자신의 가치를 입증하며 커리어를 쌓아야 합니다. 저는 그 생존의 룰을 이야기하는 겁니다."),
            ("스티브 잡스", "생존을 목표로 삼는 순간 인생은 끔찍하게 지루해집니다. 기술과 인문학의 교차점에 답이 있습니다. 코딩을 AI가 해준다면 인간은 철학과 예술, 사람의 마음을 깊이 탐구해야 합니다."),
            (founder, "인문학적 소양이 무기가 된다는 점에는 동의합니다. 하지만 그 무기를 휘두르는 방식은 기술적이어야 합니다. AI라는 레버리지를 활용하지 못하는 인문학은 상념에 머물 수 있습니다."),
            ("스티브 잡스", "아름다운 서체를 경험해보지 못한 사람이 AI로 글씨체를 찍어낸들 무슨 영혼이 있겠습니까? 미학을 이해하는 인간만이 AI라는 붓으로 걸작을 그릴 수 있습니다."),
            (founder, "현실의 면접장에서는 캘리그라피를 아는 사람보다 AI API를 연동해 하루 만에 서비스를 런칭해 본 사람을 뽑습니다. 실행력과 생산성이 시장의 중요한 원칙이기 때문입니다."),
            ("스티브 잡스", "그래서 다들 영혼 없는 제품을 만들어내고 금방 잊히는 겁니다. 위대한 제품은 타협하지 않는 열정에서 나옵니다. 이력서의 키워드는 매칭할 수 있어도 사람의 눈빛에 담긴 광기는 측정하지 못합니다."),
            (founder, "광기를 측정할 수는 없어도 그 광기가 만들어낸 성과 데이터는 측정할 수 있습니다. AI 시대의 생존자는 도구를 학습하고 실패의 데이터를 빠르게 피드백하며 진화하는 실용적인 학습자입니다."),
            ("스티브 잡스", "죽음 앞에서도 그 성과 데이터가 당신을 위로할까요? 남의 인생을 살지 마십시오. AI가 모든 것을 대체하는 시대일수록 내가 진정으로 사랑하는 일을 찾는 것이 구원입니다."),
            (founder, "가슴 뛰는 일을 하기 위해서라도 경제적 자립이 필수적입니다. AI를 두려워할 것이 아니라 귀찮은 잡무를 던져주고 나를 돋보이게 만들 최고의 인턴으로 부려먹어야 합니다."),
            ("스티브 잡스", "훌륭한 비유군요. 하지만 인턴에게 회사의 비전과 철학을 맡기는 CEO는 없습니다. 방향을 지시하고 기준을 세우며 한계까지 밀어붙이는 것은 인간의 몫입니다."),
            (founder, "맞습니다. 우리는 AI라는 뛰어난 인턴을 지휘하는 프로젝트 매니저가 되어야 합니다. 기획력과 문제 정의, 결과물을 검수하는 역량이 앞으로의 인간을 정의할 것입니다."),
            ("스티브 잡스", "검수자가 되는 것으로 만족하지 마십시오. 비저너리가 되십시오. 인간의 심장 박동을 빠르게 만드는 본질적인 감동은 프롬프트에서 나오지 않습니다."),
            (founder, "시장 수요를 읽고 AI로 무장해 압도적인 효율을 내는 것. 그것이 지금 청년들에게 해줄 수 있는 가장 냉정하고 확실한 생존 지침입니다."),
            ("스티브 잡스", "언제나 갈망하고 언제나 우직하게 나아가십시오. 기계가 똑똑해질수록, 당신은 더 깊게 사랑하고 더 치열하게 인간다워지십시오."),
        ],
        "유명 채용 플랫폼 대표는 시장 데이터와 AI 활용 능력을 생존의 기준으로 제시하고, 스티브 잡스는 직관과 미학, 인간다운 열정을 지켜야 한다고 맞선다. 두 사람은 현실적 적응과 본질적 인간다움의 긴장을 끝까지 유지한다.",
        96,
        "스티브 잡스",
    )


def featured_faith_dialogue() -> Dialogue:
    """Return the dedicated Jesus and Buddha showcase conversation."""
    topic = "AI시대, 종교의 방향"
    return Dialogue(
        "고요한 사찰의 법당과 갈릴리의 언덕이 하나의 광장으로 이어졌다. "
        "예수와 부처는 AI가 삶과 신앙을 바꾸는 시대에 종교가 가야 할 길을 묻는다.",
        [
            ("예수", "AI가 사람의 일을 대신하는 시대일수록 종교는 가장자리로 밀려난 사람 곁에 서야 합니다. 기술의 풍요가 누구에게나 나누어지는지 먼저 물어야 하지요."),
            ("부처", "나는 기술을 선악으로 단정하기보다 그것을 대하는 마음을 살피겠습니다. 더 빠르고 더 많이 가지려는 집착이 새로운 고통을 만들 수 있기 때문입니다."),
            ("예수", "맞습니다. 그러나 고통을 바라보는 데서 멈추지 말고, 굶주린 이와 일자리를 잃은 이의 식탁에 실제로 자리를 마련해야 합니다."),
            ("부처", "자비는 마음속 감정만이 아니라 행동이어야 합니다. 동시에 AI가 내린 답을 맹목적으로 따르지 않고, 그 결과가 누구를 해치는지 깨어 살펴야 합니다."),
            ("예수", "종교 공동체도 AI를 두려워하기보다 교육과 돌봄에 활용할 수 있습니다. 다만 사람을 점수와 확률로만 보지 않는 원칙은 절대 놓쳐서는 안 됩니다."),
            ("부처", "사람을 하나의 데이터로 고정하면 변화할 가능성을 보지 못합니다. 모든 존재가 서로 연결되어 있다는 사실을 기억한다면 기술의 사용도 달라질 것입니다."),
            ("예수", "결국 중요한 것은 기술이 사람을 더 사랑하게 만드는가입니다. 외로운 이에게 손을 내밀 시간을 벌어준다면 AI는 섬기는 도구가 될 수 있습니다."),
            ("부처", "그 시간을 다시 욕망과 경쟁으로 채운다면 도구가 주인이 됩니다. 종교는 멈추고 바라보며 무엇으로부터 자유로워져야 하는지 가르쳐야 합니다."),
            ("예수", "그리고 용서와 환대의 문을 넓혀야 합니다. AI의 판단으로 배제된 사람에게도 다시 시작할 기회를 주는 것이 공동체의 책임입니다."),
            ("부처", "그 책임은 특정 종교의 독점물이 아닙니다. 서로 다른 믿음이 경쟁하기보다 고통을 줄이는 지혜를 함께 나누어야 합니다."),
            ("예수", "AI 시대의 종교는 더 높은 벽을 세우는 곳이 아니라, 기술이 만든 균열을 건너 서로를 만나는 다리가 되어야 합니다."),
            ("부처", "그 다리는 인간의 깨어 있는 마음으로 놓입니다. 기술을 숭배하지도 거부하지도 말고, 자비와 지혜를 기준으로 바르게 사용합시다."),
        ],
        "예수는 종교가 AI로 소외된 이들을 적극적으로 돌보고 환대해야 한다고 주장하고, 부처는 기술에 대한 집착을 경계하며 깨어 있는 마음과 자비로운 사용을 강조한다.",
        92,
        "예수",
        "AI 시대의 종교는 기술의 혜택에서 밀려난 사람을 찾아 돌보고, 환대와 연대로 공동체를 회복해야 한다.",
        "AI 자체를 숭배하거나 두려워하지 말고, 집착을 내려놓은 깨어 있음과 자비를 기준으로 기술을 사용해야 한다.",
        "예수는 종교의 적극적인 돌봄과 사회적 실천을 앞세우고, 부처는 욕망과 집착을 성찰하는 내면의 균형을 먼저 강조한다.",
    )


def start_showcase(person_a: str, person_b: str, topic: str) -> None:
    """Open a prepared showcase dialogue directly, without the selection step."""
    with st.spinner("두 인물이 광장에 모이는 중…"):
        if (
            {person_a, person_b} == {"유명 채용 플랫폼 대표", "스티브 잡스"}
            and topic == "AI 시대, 인간은 어떻게 살아남을 것인가"
        ):
            dialogue = extend_dialogue(
                featured_founder_dialogue(), person_a, person_b, topic
            )
        elif (
            {person_a, person_b} == {"예수", "부처"}
            and topic == "AI시대, 종교의 방향"
        ):
            dialogue = extend_dialogue(
                featured_faith_dialogue(), person_a, person_b, topic
            )
        else:
            dialogue = (
                demo_dialogue(person_a, person_b, topic, "진지한 토론")
                or remote_dialogue(person_a, person_b, topic, 50)
            )
    st.session_state.update(
        {
            "screen": "result",
            "dialogue": dialogue,
            "person_a": person_a,
            "person_b": person_b,
            "topic": topic,
            "tone": 50,
            "pre_vote": "아직 모르겠다",
            "direct_messages": [],
            "dialogue_followups": [],
            "dialogue_followup_prompt": "",
        }
    )


def start_ask_mode(person: str) -> None:
    st.session_state.update(
        {
            "screen": "ask",
            "ask_person": person,
            "ask_messages": [],
            "ask_prompt": DIRECT_PROMPTS[0],
        }
    )


valid_screens = {"intro", "landing", "mentor_landing", "mentor_quiz", "mentor_result", "parallel_age", "magazine", "ask", "select", "result"}
if "screen" not in st.session_state or st.session_state.screen not in valid_screens:
    st.session_state.screen = "intro"
if "screen_history" not in st.session_state:
    st.session_state.screen_history = []
if "parallel_age_result" not in st.session_state:
    st.session_state.parallel_age_result = []
if "mentor_answer_history" not in st.session_state:
    st.session_state.mentor_answer_history = []
if "mentor_scores" not in st.session_state or not isinstance(st.session_state.mentor_scores, dict):
    st.session_state.mentor_scores = {axis: 0 for axis in MENTOR_AXES}
if "mentor_index" not in st.session_state or not isinstance(st.session_state.mentor_index, int):
    st.session_state.mentor_index = 0
if "insight_index" not in st.session_state or not (0 <= st.session_state.insight_index < len(RANDOM_INSIGHTS)):
    st.session_state.insight_index = random.randrange(len(RANDOM_INSIGHTS))

render_scroll_to_top()

background_styles = """<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Noto+Sans+KR:wght@400;500;700&display=swap');
    .stApp { background:#f3eadc; color:#304651; }
    .stApp, .stApp p, .stApp label, .stApp span, .stApp div { color:#304651; }
    .stApp .stMarkdown, .stApp .stCaption, .stApp [data-testid="stCaptionContainer"] { color:#4f5f64 !important; }
    .stApp input, .stApp textarea, .stApp [data-baseweb="select"], .stApp [data-baseweb="select"] * { color:#304651 !important; background:#f9f2e7 !important; }
    .stApp [data-baseweb="select"] { border:1px solid #c7b8a5 !important; border-radius:8px !important; }
    .block-container { max-width:900px; padding-top:2rem; padding-bottom:5rem; }
    header[data-testid="stHeader"] { background:transparent; }
    h1, h2, h3, h4 { font-family:'DM Serif Display', serif; letter-spacing:-.025em; color:#263f4a !important; }
    h1 { font-size:4.5rem; line-height:.96; margin:.3rem 0 1rem; }
    .brand-wordmark { font-family:'DM Serif Display', Georgia, serif; font-size:4.8rem; line-height:1.05; letter-spacing:-.045em; color:#304651; margin:.35rem 0 1.1rem; }
    h2 { font-size:2.1rem; margin-top:.5rem; }
    h3 { font-size:1.35rem; }
    .eyebrow { color:#6b6258; font-size:.68rem; letter-spacing:.2em; font-weight:800; }
    .tagline { max-width:34rem; font-size:1.12rem; line-height:1.65; color:#5b625f; }
    .card { background:#f9f2e7; border:1px solid #dfd0bd; border-radius:12px; padding:1.15rem 1.25rem; margin:.6rem 0; box-shadow:0 4px 16px rgba(72,54,35,.07); }
    .quote { border-left:2px solid #b56c4a; padding-left:1rem; color:#58605f; font-size:1rem; line-height:1.7; }
    .scene { background:#304651; color:#f4e8d5 !important; border-radius:12px; padding:1.35rem 1.5rem; line-height:1.8; }
    .scene * { color:#f4e8d5 !important; }
    .topic-hero { background:#fff8ed; border:2px solid #b56c4a; border-radius:14px; padding:1.1rem 1.3rem; margin:.8rem 0 1.2rem; box-shadow:0 5px 18px rgba(72,54,35,.08); }
    .topic-kicker { color:#a05237 !important; font-size:.72rem; font-weight:800; letter-spacing:.14em; text-transform:uppercase; }
    .topic-title { color:#263f4a !important; font-size:1.72rem; font-weight:800; line-height:1.3; margin:.3rem 0; }
    .topic-guide { color:#58605f !important; font-size:.92rem; line-height:1.6; }
    .temperature-readout { max-width:31rem; margin:.15rem 0 1rem; padding:.65rem .8rem .7rem; border:1px solid #dfd0bd; border-radius:10px; background:#fffaf2; }
    .temperature-title { font-size:.9rem; font-weight:800; letter-spacing:.02em; }
    .temperature-track { height:7px; margin:.45rem 0 .35rem; border-radius:99px; background:linear-gradient(90deg,#3b82c4 0%,#268fa3 28%,#c28b38 52%,#d7653d 76%,#c43d4b 100%); overflow:hidden; }
    .temperature-track span { display:block; height:100%; border-radius:99px; box-shadow:0 0 8px currentColor; }
    .temperature-description { color:#687276; font-size:.78rem; }
    .claim-label { display:block; color:#a05237 !important; font-size:.82rem; font-weight:800; margin:.4rem 0 .35rem; }
    .magazine-card { background:#fff8ed; border:1px solid #dfd0bd; border-radius:16px; padding:1.25rem 1.35rem; margin:1rem 0 1.4rem; box-shadow:0 5px 18px rgba(72,54,35,.07); }
    .magazine-category { color:#a05237 !important; font-size:.7rem; font-weight:800; letter-spacing:.15em; }
    .magazine-title { color:#263f4a !important; font-family:'DM Serif Display',serif; font-size:1.65rem; line-height:1.3; margin:.35rem 0 .5rem; }
    .magazine-dek { color:#58605f !important; font-size:.98rem; line-height:1.6; font-weight:600; }
    .magazine-body { color:#40545b !important; line-height:1.75; margin-top:.8rem; }
    .magazine-question { border-left:3px solid #b56c4a; padding:.65rem .8rem; margin-top:1rem; color:#304651 !important; font-weight:700; background:#f4e5cf; }
    .parallel-age-card { background:#fff8ed; border:1px solid #dfd0bd; border-radius:16px; padding:1.25rem 1.35rem; margin:1rem 0 1.4rem; box-shadow:0 5px 18px rgba(72,54,35,.07); }
    .parallel-age-header { display:flex; justify-content:space-between; gap:.8rem; align-items:flex-start; }
    .parallel-age-source { color:#a05237 !important; font-size:.7rem; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }
    .parallel-age-person { color:#263f4a !important; font-family:'DM Serif Display',serif; font-size:1.65rem; line-height:1.25; margin:.25rem 0 .2rem; }
    .parallel-age-age { color:#58605f !important; font-size:.86rem; font-weight:700; }
    .parallel-age-match { color:#397064 !important; font-size:.73rem; font-weight:800; margin-top:.35rem; }
    .parallel-age-context { color:#40545b !important; line-height:1.7; margin:.9rem 0; padding:.8rem .9rem; background:#f4e5cf; border-left:3px solid #b56c4a; }
    .parallel-age-section { margin-top:1rem; padding-top:.9rem; border-top:1px solid #dfd0bd; }
    .parallel-age-section-title { color:#914f35 !important; font-size:.76rem; font-weight:800; letter-spacing:.08em; margin-bottom:.35rem; }
    .parallel-age-section-body { color:#40545b !important; line-height:1.7; }
    .parallel-age-inference { background:#eef3f0; border:1px solid #bfd0c7; border-radius:10px; padding:.9rem; }
    .parallel-age-inference .parallel-age-section-title { color:#397064 !important; }
    .parallel-age-source-note { color:#68756f !important; font-size:.76rem; line-height:1.55; margin-top:.65rem; }
    .comment-card { background:#f9f2e7; border:1px solid #dfd0bd; border-radius:12px; padding:.9rem 1rem; margin:.55rem 0; }
    .comment-head { color:#a05237 !important; font-weight:800; font-size:.88rem; }
    .comment-tag { float:right; color:#71817b !important; font-size:.72rem; font-weight:600; }
    .comment-text { color:#304651 !important; line-height:1.65; margin-top:.35rem; }
    .chat-window { background:#dce4e0; border:1px solid #c6d2cc; border-radius:14px; padding:1.15rem .9rem; margin:.5rem 0 1.5rem; }
    .chat-window-head { display:flex; align-items:center; gap:.55rem; border-bottom:1px solid #c0cdc6; padding:.15rem .45rem .85rem; margin-bottom:1rem; }
    .chat-status { width:8px; height:8px; background:#5b9a67; border-radius:50%; display:inline-block; }
    .chat-title { font-weight:700; color:#304651 !important; }
    .chat-subtitle { color:#64746f !important; font-size:.76rem; margin-left:auto; }
    .chat-row { display:flex; gap:.55rem; margin:.8rem .25rem; align-items:flex-start; }
    .chat-row.right { flex-direction:row-reverse; }
    .chat-content { max-width:78%; }
    .chat-row.right .chat-content { text-align:right; }
    .chat-avatar { flex:0 0 2rem; width:2rem; height:2rem; border-radius:50%; overflow:hidden; background:#b56c4a; color:#f8ead8; display:flex; align-items:center; justify-content:center; font-size:.7rem; font-weight:700; }
    .chat-avatar img { width:100%; height:100%; object-fit:cover; filter:saturate(.72) contrast(.98); }
    .chat-row.right .chat-avatar { background:#718b84; }
    .chat-name { color:#52635f !important; font-size:.72rem; margin:0 .35rem .22rem; }
    .chat-bubble { display:inline-block; text-align:left; background:#f4e5cf; color:#30414a !important; border-radius:4px 14px 14px 14px; padding:.72rem .85rem; line-height:1.65; font-size:.92rem; box-shadow:0 1px 1px rgba(40,45,40,.08); }
    .chat-bubble * { color:#30414a !important; }
    .chat-row.right .chat-bubble { background:#c8ded8; border-radius:14px 4px 14px 14px; }
    .user-avatar { background:#304651 !important; }
    .chat-time { color:#71817b; font-size:.63rem; margin:.2rem .35rem 0; }
    .person-caption { color:#5e6965; font-size:.98rem; font-weight:700; line-height:1.45; margin-top:-.5rem; }
    .metric { background:#f9f2e7; border:1px solid #dfd0bd; border-radius:12px; padding:1rem; text-align:center; }
    .metric strong { display:block; font-size:1.5rem; color:#304651; }
    .insight-card { background:#f9f2e7; border:1px solid #dfd0bd; border-radius:12px; padding:1rem; min-height:7.8rem; color:#304651; line-height:1.65; }
    .insight-card b { display:block; color:#b56c4a; font-size:.76rem; letter-spacing:.08em; margin-bottom:.35rem; }
    .insight-card strong { color:#304651; }
    .callout { background:#304651; color:#f4e8d5 !important; border-radius:12px; padding:1.1rem 1.25rem; line-height:1.7; }
    .callout * { color:#f4e8d5 !important; }
    .beta-notice { background:#f8dfc2; border:1px solid #d49b6d; border-radius:12px; padding:1rem 1.15rem; margin:1rem 0 1.25rem; color:#304651 !important; line-height:1.6; }
    .beta-notice strong { display:block; color:#914f35 !important; font-size:.95rem; margin-bottom:.2rem; }
    .beta-notice span { color:#40545b !important; font-size:.9rem; }
    /* Dark editorial palette */
    .stApp { background:#080d12 !important; color:#f7fafb !important; }
    .stApp, .stApp p, .stApp label, .stApp span, .stApp div { color:#e7eef2; }
    .stApp .stMarkdown, .stApp .stCaption, .stApp [data-testid="stCaptionContainer"] { color:#c8d4da !important; }
    h1, h2, h3, h4 { color:#ffffff !important; }
    .brand-wordmark { color:#ffffff !important; }
    .eyebrow { color:#b9dce6 !important; }
    .tagline, .quote { color:#d3dee3 !important; }
    .card, .topic-hero, .magazine-card, .comment-card, .insight-card, .metric { background:#17232c !important; border-color:#526b78 !important; }
    .topic-title, .magazine-title, .magazine-body, .comment-text, .insight-card strong { color:#ffffff !important; }
    .topic-guide, .magazine-dek, .person-caption { color:#d0dde2 !important; }
    .scene, .callout { background:#243844 !important; color:#ffffff !important; }
    .scene *, .callout * { color:#ffffff !important; }
    .magazine-question { background:#263e4a !important; color:#ffffff !important; border-color:#83b7c5 !important; }
    .parallel-age-card { background:#17232c !important; border-color:#526b78 !important; }
    .parallel-age-person, .parallel-age-section-body { color:#ffffff !important; }
    .parallel-age-age, .parallel-age-source-note { color:#c3d2d9 !important; }
    .parallel-age-match { color:#9fe1d1 !important; }
    .parallel-age-context { background:#263e4a !important; color:#ffffff !important; border-color:#83b7c5 !important; }
    .parallel-age-context * { color:#ffffff !important; }
    .parallel-age-section { border-color:#526b78 !important; }
    .parallel-age-section-title, .parallel-age-inference .parallel-age-section-title { color:#aee3ee !important; }
    .parallel-age-inference { background:#203b3a !important; border-color:#5f958e !important; }
    .chat-window { background:#101a21 !important; border-color:#526b78 !important; }
    .chat-window-head { border-color:#526b78 !important; }
    .chat-title, .chat-bubble, .chat-bubble * { color:#ffffff !important; }
    .chat-bubble { background:#2b414d !important; }
    .chat-row.right .chat-bubble { background:#28565b !important; }
    .chat-name, .chat-time, .chat-subtitle { color:#c3d2d9 !important; }
    .beta-notice { background:#1d333d !important; border-color:#6e9aaa !important; color:#ffffff !important; }
    .beta-notice span, .beta-notice strong { color:#ffffff !important; }
    .claim-label, .magazine-category, .comment-head { color:#aee3ee !important; }
    .comment-tag { color:#c3d2d9 !important; }
    .stApp input, .stApp textarea, .stApp [data-baseweb="select"], .stApp [data-baseweb="select"] * { color:#ffffff !important; background:#17232c !important; }
    .stApp [data-baseweb="select"] { border-color:#6a8793 !important; }
    div[data-testid="stButton"] button, .stDownloadButton button { background:#17232c !important; color:#ffffff !important; border-color:#6a8793 !important; }
    div[data-testid="stButton"] button[kind="secondary"], .stDownloadButton button[kind="secondary"] { background:#17232c !important; color:#ffffff !important; border:1px solid #6a8793 !important; }
    div[data-testid="stButton"] button:hover, .stDownloadButton button:hover { background:#315363 !important; border-color:#b8e6f0 !important; color:#fff !important; }
    div[data-testid="stButton"] button[kind="primary"] { background:#397888 !important; border-color:#8ec9d5 !important; color:#fff !important; }
    div[data-testid="stButton"] button[kind="primary"] p, div[data-testid="stButton"] button[kind="secondary"] p { color:#ffffff !important; }
    div[data-testid="stRadio"] label { background:#17232c !important; border-color:#526b78 !important; color:#ffffff !important; }
    div[data-testid="stRadio"] label p, div[data-testid="stRadio"] label span { color:#ffffff !important; }
    .home-feature { background:linear-gradient(145deg,#172a34,#111d25); border:1px solid #5b7b88; border-radius:16px; padding:1.15rem; height:13rem; box-sizing:border-box; overflow:hidden; }
    .home-feature-mentor {
        background:linear-gradient(145deg,#203d49,#17232c 46%,#2a2d33 100%);
        border:1px solid #9ed9e6;
        box-shadow:0 14px 30px rgba(88,144,162,.18);
    }
    .home-feature-kicker { color:#b2e3ed !important; font-size:.7rem; font-weight:800; letter-spacing:.14em; }
    .home-feature-title { color:#ffffff !important; font-size:1.35rem; font-weight:800; margin:.45rem 0 .35rem; }
    .home-feature-copy { color:#d0dde2 !important; line-height:1.6; min-height:3.3rem; }
    .home-feature-mentor .home-feature-title { color:#fff3dc !important; }
    .home-feature-mentor .home-feature-copy { color:#eaf8ff !important; }
    .mentor-hero { background:linear-gradient(135deg,#172a34 0%,#243844 58%,#4b332b 100%); border:1px solid #83aab8; border-radius:20px; padding:1.7rem 1.6rem 1.5rem; margin:1rem 0 1.25rem; box-shadow:0 18px 45px rgba(0,0,0,.24); position:relative; overflow:hidden; }
    .mentor-hero::before { content:""; position:absolute; inset:auto -10% -40% 52%; height:190px; background:radial-gradient(circle, rgba(170,229,244,.32), rgba(170,229,244,0)); pointer-events:none; }
    .mentor-kicker { color:#b9edf5 !important; font-size:.72rem; font-weight:800; letter-spacing:.16em; }
    .mentor-title { color:#ffffff !important; font-family:'DM Serif Display',serif; font-size:2.9rem; line-height:1.08; margin:.6rem 0 .9rem; }
    .mentor-copy { color:#d8e7eb !important; line-height:1.7; max-width:42rem; font-size:1.02rem; }
    .mentor-hero-grid { display:grid; grid-template-columns:1.7fr .9fr; gap:1rem; align-items:center; }
    .mentor-meta { display:flex; flex-wrap:wrap; gap:.5rem; margin-top:1rem; }
    .mentor-meta-badge { display:inline-block; padding:.35rem .7rem; border-radius:999px; border:1px solid rgba(174,227,238,.45); background:rgba(255,255,255,.05); color:#dff6fc !important; font-size:.74rem; font-weight:700; letter-spacing:.03em; }
    .mentor-glow-card { background:linear-gradient(180deg, rgba(16,25,31,.6), rgba(17,27,35,.8)); border:1px solid rgba(174,227,238,.35); border-radius:18px; padding:1rem; display:flex; flex-direction:column; justify-content:center; min-height:11rem; }
    .mentor-glow-card .mini-label { color:#aee3ee !important; font-size:.7rem; letter-spacing:.16em; font-weight:800; }
    .mentor-glow-card .mini-score { color:#fff4df !important; font-family:'DM Serif Display',serif; font-size:2.5rem; line-height:1; margin:.5rem 0 .2rem; }
    .mentor-glow-card .mini-copy { color:#d8e7eb !important; font-size:.88rem; line-height:1.6; }
    .mentor-question { background:linear-gradient(145deg,#172a34,#111d25); border:1px solid #6f929f; border-radius:16px; padding:1.5rem; margin:1rem 0; box-shadow:0 16px 35px rgba(0,0,0,.22); }
    .mentor-question-number { color:#aee3ee !important; font-size:.75rem; font-weight:800; letter-spacing:.15em; }
    .mentor-question-title { color:#ffffff !important; font-family:'DM Serif Display',serif; font-size:1.65rem; line-height:1.35; margin:.55rem 0 1.15rem; }
    .mentor-answer { min-height:7.5rem !important; text-align:left !important; white-space:normal !important; line-height:1.5 !important; }
    .mentor-result { border:1px solid #c89b6d; border-radius:18px; padding:1.55rem; background:linear-gradient(145deg,#2b2020,#17232c); box-shadow:0 20px 50px rgba(0,0,0,.28); }
    .mentor-result-head { display:flex; align-items:center; gap:1.2rem; }
    .mentor-result-portrait { flex:0 0 8.4rem; width:8.4rem; height:10.5rem; position:relative; overflow:hidden; border-radius:22px; border:1px solid rgba(229,163,110,.78); background:#172a34; box-shadow:0 16px 32px rgba(0,0,0,.32), inset 0 0 0 5px rgba(255,255,255,.04); display:flex; align-items:center; justify-content:center; }
    .mentor-result-portrait::after { content:""; position:absolute; inset:45% 0 0; background:linear-gradient(to bottom,transparent,rgba(7,15,21,.72)); pointer-events:none; }
    .mentor-result-portrait img { width:100%; height:100%; object-fit:cover; object-position:center top; transform:none; image-rendering:auto; }
    .mentor-result-heading { min-width:0; }
    .mentor-result-name { color:#fff4df !important; font-family:'DM Serif Display',serif; font-size:2.5rem; line-height:1.15; }
    .mentor-result-group { color:#f0ba86 !important; font-weight:800; letter-spacing:.08em; margin:.3rem 0 1rem; }
    .mentor-story-tagline { color:#ffd6a8 !important; font-family:'DM Serif Display',serif; font-size:1.35rem; line-height:1.35; margin:1.15rem 0 .8rem; }
    .mentor-story-section { border-top:1px solid rgba(111,146,159,.55); padding:1rem 0 .2rem; }
    .mentor-story-label { color:#aee3ee !important; font-size:.72rem; font-weight:800; letter-spacing:.12em; margin-bottom:.38rem; }
    .mentor-story-text { color:#f2f7f8 !important; font-size:1rem; line-height:1.75; }
    .mentor-comparison-title { color:#fff4df !important; font-family:'DM Serif Display',serif; font-size:1.35rem; margin:1.5rem 0 .75rem; }
    .mentor-comparison-card { min-height:9.5rem; border:1px solid #557683; border-radius:16px; padding:1rem; background:linear-gradient(145deg,#172a34,#111d25); }
    .mentor-comparison-card.contrast { border-color:#a66f55; background:linear-gradient(145deg,#302220,#17232c); }
    .mentor-comparison-card-head { display:flex; align-items:center; gap:.7rem; margin-bottom:.65rem; }
    .mentor-comparison-avatar { width:3rem; height:3.6rem; flex:0 0 3rem; border-radius:10px; overflow:hidden; border:1px solid rgba(229,163,110,.58); background:#203642; }
    .mentor-comparison-avatar img { width:100%; height:100%; object-fit:cover; object-position:center top; }
    .mentor-comparison-name { color:#fff4df !important; font-weight:800; line-height:1.2; }
    .mentor-comparison-score { color:#f0ba86 !important; font-size:.76rem; font-weight:700; margin-top:.2rem; }
    .mentor-comparison-copy { color:#d8e7eb !important; font-size:.84rem; line-height:1.55; }
    .mentor-quote { color:#fff4df !important; border-left:3px solid #e5a36e; padding:.7rem 1rem; margin:1rem 0; line-height:1.65; font-size:1.05rem; }
    .mentor-report { color:#e5edf0 !important; line-height:1.8; margin:.2rem 0; }
    .mentor-tag { display:inline-block; color:#b9edf5 !important; background:#285565; border:1px solid #6f929f; border-radius:999px; padding:.28rem .65rem; margin:.25rem .25rem 0 0; font-size:.78rem; font-weight:700; }
    .mentor-profile { margin-top:1.25rem; border:1px solid #6f929f; border-radius:16px; background:#172a34; padding:1.25rem 1.35rem; }
    .mentor-profile-title { color:#b9edf5 !important; font-size:.72rem; font-weight:800; letter-spacing:.14em; margin-bottom:.8rem; }
    .mentor-profile-row { border-top:1px solid rgba(131,170,184,.3); padding:.8rem 0 .1rem; color:#e5edf0 !important; line-height:1.7; }
    .mentor-profile-label { display:block; color:#f0ba86 !important; font-size:.8rem; font-weight:800; margin-bottom:.2rem; }
    /* --- Enhanced mentor result: similarity bars, conflict cards, detailed profile --- */
    .similarity-section { margin-top:1.5rem; border:1px solid #6f929f; border-radius:16px; background:#172a34; padding:1.25rem 1.35rem; }
    .similarity-section-title { color:#b9edf5 !important; font-size:.72rem; font-weight:800; letter-spacing:.14em; margin-bottom:.8rem; }
    .similarity-bar-row { display:flex; align-items:center; gap:.75rem; margin:.4rem 0; }
    .similarity-bar-label { width:8.5rem; text-align:right; color:#e5edf0 !important; font-size:.82rem; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .similarity-bar-track { flex:1; height:1.1rem; background:#0d1a22; border-radius:999px; overflow:hidden; position:relative; }
    .similarity-bar-fill { height:100%; border-radius:999px; background:linear-gradient(90deg,#3f8797,#55a7b7); transition:width .6s ease; }
    .similarity-bar-fill.high { background:linear-gradient(90deg,#b56c4a,#e5a36e); }
    .similarity-bar-fill.top { background:linear-gradient(90deg,#e5a36e,#ffd19f); box-shadow:0 0 10px rgba(229,163,110,.5); }
    .similarity-bar-pct { width:3.2rem; color:#b9edf5 !important; font-size:.78rem; font-weight:700; text-align:right; }
    .radar-card { margin-top:1.5rem; border:1px solid #6f929f; border-radius:16px; background:#172a34; padding:1.25rem 1.35rem; }
    .radar-heading { display:flex; justify-content:space-between; gap:1rem; align-items:flex-start; }
    .radar-title { color:#ffffff !important; font-size:1.1rem; font-weight:800; margin-top:.35rem; }
    .radar-legend { color:#d8e7eb !important; font-size:.78rem; white-space:nowrap; padding-top:.15rem; }
    .radar-dot { display:inline-block; width:.6rem; height:.6rem; border-radius:50%; margin:0 .25rem 0 .55rem; vertical-align:middle; }
    .radar-dot.user { background:#65c7d5; box-shadow:0 0 0 3px rgba(101,199,213,.18); }
    .radar-dot.mentor { background:#f0ad73; box-shadow:0 0 0 3px rgba(240,173,115,.18); }
    .radar-chart { display:block; width:100%; max-width:440px; height:auto; margin:.7rem auto -.2rem; overflow:visible; }
    .radar-ring { fill:none; stroke:rgba(174,227,238,.19); stroke-width:1; }
    .radar-spoke { stroke:rgba(174,227,238,.2); stroke-width:1; }
    .radar-user { fill:rgba(101,199,213,.25); stroke:#65c7d5; stroke-width:2.5; }
    .radar-mentor { fill:rgba(240,173,115,.22); stroke:#f0ad73; stroke-width:2.5; }
    .radar-label { fill:#e5edf0; font-size:12px; font-weight:700; }
    .conflict-section { margin-top:1.5rem; border:1px solid #8b5e4a; border-radius:16px; background:linear-gradient(145deg,#2b1a14,#17232c); padding:1.25rem 1.35rem; }
    .conflict-section-title { color:#f0ba86 !important; font-size:.72rem; font-weight:800; letter-spacing:.14em; margin-bottom:.8rem; }
    .conflict-card { display:flex; align-items:center; gap:.9rem; padding:.75rem .9rem; border:1px solid #8b5e4a; border-radius:12px; background:#1d1410; margin:.5rem 0; }
    .conflict-avatar { flex:0 0 2.8rem; width:2.8rem; height:2.8rem; border-radius:50%; overflow:hidden; border:2px solid #8b5e4a; background:#172a34; display:flex; align-items:center; justify-content:center; }
    .conflict-avatar img { width:100%; height:100%; object-fit:cover; }
    .conflict-info { flex:1; min-width:0; }
    .conflict-name { color:#fff4df !important; font-size:.95rem; font-weight:700; }
    .conflict-compat { color:#e5a36e !important; font-size:.78rem; font-weight:600; margin:.15rem 0; }
    .conflict-note { color:#c7d8de !important; font-size:.78rem; line-height:1.45; }
    .detailed-profile-section { margin-top:1.5rem; border:1px solid #6f929f; border-radius:16px; background:#172a34; padding:1.25rem 1.35rem; }
    .detailed-profile-title { color:#b9edf5 !important; font-size:.72rem; font-weight:800; letter-spacing:.14em; margin-bottom:.8rem; }
    .profile-grid { display:grid; grid-template-columns:1fr 1fr; gap:.75rem 1.5rem; }
    .profile-grid-item { border-top:1px solid rgba(131,170,184,.25); padding:.6rem 0; }
    .profile-grid-label { display:block; color:#f0ba86 !important; font-size:.72rem; font-weight:800; letter-spacing:.08em; margin-bottom:.15rem; }
    .profile-grid-value { color:#e5edf0 !important; font-size:.85rem; line-height:1.5; }
    .profile-grid-value .mbtype { color:#ffd19f !important; font-weight:700; }
    .profile-grid-value .strengths { display:flex; flex-wrap:wrap; gap:.3rem; }
    .profile-grid-value .strengths span { background:#285565; border:1px solid #6f929f; border-radius:999px; padding:.1rem .45rem; font-size:.72rem; color:#b9edf5 !important; }
    .profile-grid-value .blind { color:#e5a36e !important; font-style:italic; }
    .profile-grid-item.full { grid-column:1 / -1; }
    @media (max-width:640px) { .profile-grid { grid-template-columns:1fr; } .similarity-bar-label { width:5.5rem; font-size:.72rem; } }
    /* --- Enhanced mentor result: similarity bars, conflict cards, detailed profile --- */
    .similarity-section { margin-top:1.5rem; border:1px solid #6f929f; border-radius:16px; background:#172a34; padding:1.25rem 1.35rem; }
    .similarity-section-title { color:#b9edf5 !important; font-size:.72rem; font-weight:800; letter-spacing:.14em; margin-bottom:.8rem; }
    .similarity-bar-row { display:flex; align-items:center; gap:.75rem; margin:.4rem 0; }
    .similarity-bar-label { width:8.5rem; text-align:right; color:#e5edf0 !important; font-size:.82rem; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .similarity-bar-track { flex:1; height:1.1rem; background:#0d1a22; border-radius:999px; overflow:hidden; position:relative; }
    .similarity-bar-fill { height:100%; border-radius:999px; background:linear-gradient(90deg,#3f8797,#55a7b7); transition:width .6s ease; }
    .similarity-bar-fill.high { background:linear-gradient(90deg,#b56c4a,#e5a36e); }
    .similarity-bar-fill.top { background:linear-gradient(90deg,#e5a36e,#ffd19f); box-shadow:0 0 10px rgba(229,163,110,.5); }
    .similarity-bar-pct { width:3.2rem; color:#b9edf5 !important; font-size:.78rem; font-weight:700; text-align:right; }
    .conflict-section { margin-top:1.5rem; border:1px solid #8b5e4a; border-radius:16px; background:linear-gradient(145deg,#2b1a14,#17232c); padding:1.25rem 1.35rem; }
    .conflict-section-title { color:#f0ba86 !important; font-size:.72rem; font-weight:800; letter-spacing:.14em; margin-bottom:.8rem; }
    .conflict-card { display:flex; align-items:center; gap:.9rem; padding:.75rem .9rem; border:1px solid #8b5e4a; border-radius:12px; background:#1d1410; margin:.5rem 0; }
    .conflict-avatar { flex:0 0 2.8rem; width:2.8rem; height:2.8rem; border-radius:50%; overflow:hidden; border:2px solid #8b5e4a; background:#172a34; display:flex; align-items:center; justify-content:center; }
    .conflict-avatar img { width:100%; height:100%; object-fit:cover; }
    .conflict-info { flex:1; min-width:0; }
    .conflict-name { color:#fff4df !important; font-size:.95rem; font-weight:700; }
    .conflict-compat { color:#e5a36e !important; font-size:.78rem; font-weight:600; margin:.15rem 0; }
    .conflict-note { color:#c7d8de !important; font-size:.78rem; line-height:1.45; }
    .detailed-profile-section { margin-top:1.5rem; border:1px solid #6f929f; border-radius:16px; background:#172a34; padding:1.25rem 1.35rem; }
    .detailed-profile-title { color:#b9edf5 !important; font-size:.72rem; font-weight:800; letter-spacing:.14em; margin-bottom:.8rem; }
    .profile-grid { display:grid; grid-template-columns:1fr 1fr; gap:.75rem 1.5rem; }
    .profile-grid-item { border-top:1px solid rgba(131,170,184,.25); padding:.6rem 0; }
    .profile-grid-label { display:block; color:#f0ba86 !important; font-size:.72rem; font-weight:800; letter-spacing:.08em; margin-bottom:.15rem; }
    .profile-grid-value { color:#e5edf0 !important; font-size:.85rem; line-height:1.5; }
    .profile-grid-value .mbtype { color:#ffd19f !important; font-weight:700; }
    .profile-grid-value .strengths { display:flex; flex-wrap:wrap; gap:.3rem; }
    .profile-grid-value .strengths span { background:#285565; border:1px solid #6f929f; border-radius:999px; padding:.1rem .45rem; font-size:.72rem; color:#b9edf5 !important; }
    .profile-grid-value .blind { color:#e5a36e !important; font-style:italic; }
    .profile-grid-item.full { grid-column:1 / -1; }
    @media (max-width:640px) { .profile-grid { grid-template-columns:1fr; } .similarity-bar-label { width:5.5rem; font-size:.72rem; } }
    @media (max-width:640px) { .mentor-result-head { align-items:flex-start; } .mentor-result-portrait { flex-basis:6.8rem; width:6.8rem; height:8.5rem; border-radius:18px; } }
    @media (max-width:640px) { .home-feature { height:auto; min-height:12rem; } }
    .intro-page { min-height:78vh; display:flex; align-items:center; justify-content:center; }
    .intro-shell { position:relative; overflow:hidden; width:100%; min-height:620px; border:1px solid #526b78; border-radius:24px; background:#101a21; box-shadow:0 24px 70px rgba(0,0,0,.38); }
    .intro-art { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; opacity:.96; filter:saturate(.86) contrast(1.08) brightness(1.05); }
    .intro-shade { position:absolute; inset:0; background:linear-gradient(0deg,rgba(5,10,14,.93) 0%,rgba(5,10,14,.64) 32%,rgba(5,10,14,.08) 64%,rgba(5,10,14,.02) 100%); }
    .intro-content { position:relative; z-index:1; display:flex; flex-direction:column; justify-content:flex-end; min-height:620px; max-width:none; padding:3.2rem; padding-top:18rem; }
    .intro-kicker { color:#b2e3ed !important; font-size:.75rem; font-weight:800; letter-spacing:.2em; }
    .intro-title { color:#ffffff !important; font-family:'DM Serif Display',serif; font-size:5.4rem; line-height:.95; letter-spacing:-.05em; margin:1rem 0 1.3rem; }
    .intro-lead { color:#f0f5f7 !important; font-size:1.22rem; line-height:1.65; font-weight:600; }
    .intro-copy { color:#c8d8de !important; line-height:1.8; margin:1.1rem 0 1.7rem; max-width:640px; }
    .intro-meta { color:#91b7c2 !important; font-size:.78rem; letter-spacing:.08em; }
    @media (max-width:640px) { .intro-content { padding:2rem 1.5rem; } .intro-title { font-size:3.8rem; } .intro-shell, .intro-content { min-height:680px; } }
    .stApp div[data-testid="stHorizontalBlock"]:has(.home-feature) > div:nth-child(1) div[data-testid="stButton"] button { background:#3f8797 !important; border-color:#9bd6df !important; color:#ffffff !important; }
    .stApp div[data-testid="stHorizontalBlock"]:has(.home-feature) > div:nth-child(1) div[data-testid="stButton"] button:hover { background:#55a7b7 !important; }
    .stApp div[data-testid="stHorizontalBlock"]:has(.home-feature) > div:nth-child(2) div[data-testid="stButton"] button { background:#263d58 !important; border-color:#7196be !important; color:#ffffff !important; }
    .stApp div[data-testid="stHorizontalBlock"]:has(.home-feature) > div:nth-child(2) div[data-testid="stButton"] button:hover { background:#35577d !important; }
    .stApp div[data-testid="stHorizontalBlock"]:has(.home-feature) > div:nth-child(3) div[data-testid="stButton"] button { background:#354b48 !important; border-color:#79a9a0 !important; color:#ffffff !important; }
    .stApp div[data-testid="stHorizontalBlock"]:has(.home-feature) > div:nth-child(3) div[data-testid="stButton"] button:hover { background:#466c66 !important; }
    .stApp div[data-testid="stHorizontalBlock"]:has(.home-feature) + div[data-testid="stButton"] button { background:#17232c !important; border-color:#526b78 !important; color:#c8dce3 !important; }
    .stApp div[data-testid="stHorizontalBlock"]:has(.home-feature) + div[data-testid="stButton"] button:hover { background:#263e4a !important; border-color:#8dbbc7 !important; color:#ffffff !important; }
    div[data-testid="stButton"] button, .stDownloadButton button { border-radius:8px !important; border:1px solid #c7b8a5 !important; min-height:2.65rem; background:#f9f2e7 !important; color:#304651 !important; font-weight:600 !important; box-shadow:none !important; transition:all .15s ease; }
    div[data-testid="stButton"] button:hover, .stDownloadButton button:hover { border-color:#b56c4a !important; color:#304651 !important; background:#ead8c0 !important; }
    div[data-testid="stButton"] button[kind="primary"] { background:#b56c4a !important; border-color:#b56c4a !important; color:#f9f2e7 !important; }
    div[data-testid="stButton"] button[kind="primary"]:hover { background:#96583e !important; border-color:#96583e !important; }
    div[data-testid="stRadio"] label { background:#f9f2e7; border:1px solid #dfd0bd; border-radius:8px; padding:.25rem .5rem; color:#304651 !important; }
    div[data-testid="stRadio"] label p, div[data-testid="stRadio"] label span { color:#304651 !important; }
    div[data-testid="stRadio"] [data-baseweb="radio"] + div { color:#304651 !important; }
    div[data-testid="stRadio"] label p { font-weight:500; line-height:1.45; }
    div[data-testid="stSelectbox"] label, div[data-testid="stRadio"] > label { color:#40545b !important; font-weight:700 !important; }
    [data-testid="stImage"] + div, [data-testid="stImage"] + div p { color:#4f5f64 !important; font-weight:600; }
    [data-testid="stImage"] img { display:block; width:100%; border-radius:50%; aspect-ratio:1 / 1; object-fit:cover; border:0; filter:saturate(.78) contrast(.98); }
    div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stHorizontalBlock"]) { gap:.25rem; }
    /* Keep every interactive and supporting text surface readable in the dark theme. */
    .stApp input, .stApp textarea,
    .stApp input::placeholder, .stApp textarea::placeholder {
        color:#f5fbfd !important;
        caret-color:#ffffff !important;
        opacity:1 !important;
    }
    .stApp input::placeholder, .stApp textarea::placeholder { color:#b9cbd2 !important; }
    div[data-testid="stSelectbox"] label,
    div[data-testid="stRadio"] > label,
    div[data-testid="stTextInput"] label,
    div[data-testid="stTextArea"] label { color:#e6f0f3 !important; }
    .temperature-readout { background:#162a35 !important; border-color:#526b78 !important; }
    .temperature-description { color:#c5d7dc !important; }
    div[data-testid="stButton"] button,
    .stDownloadButton button {
        background:#1e3440 !important;
        color:#f8fcfd !important;
        border:1px solid #83aab8 !important;
    }
    div[data-testid="stButton"] button p,
    div[data-testid="stButton"] button span,
    .stDownloadButton button p,
    .stDownloadButton button span { color:#f8fcfd !important; }
    div[data-testid="stButton"] button:hover,
    .stDownloadButton button:hover,
    div[data-testid="stButton"] button:focus-visible,
    .stDownloadButton button:focus-visible {
        background:#376779 !important;
        color:#ffffff !important;
        border-color:#d1f3fa !important;
    }
    div[data-testid="stButton"] button[kind="primary"] {
        background:#2d8294 !important;
        color:#ffffff !important;
        border-color:#a9e5ee !important;
    }
    div[data-testid="stButton"] button:disabled,
    .stDownloadButton button:disabled {
        background:#26333a !important;
        color:#aebdc3 !important;
        border-color:#61727a !important;
        opacity:1 !important;
    }
    div[data-testid="stRadio"] label {
        background:#172a34 !important;
        border:1px solid #6f929f !important;
        color:#f5fbfd !important;
    }
    div[data-testid="stRadio"] label:hover,
    div[data-testid="stRadio"] label:has(input:checked) {
        background:#285565 !important;
        border-color:#b9edf5 !important;
    }
    div[data-testid="stRadio"] label p,
    div[data-testid="stRadio"] label span,
    div[data-testid="stRadio"] [data-baseweb="radio"] + div { color:#f5fbfd !important; }
    .stApp [data-baseweb="select"] {
        background:#172a34 !important;
        border-color:#83aab8 !important;
    }
    .stApp [data-baseweb="select"] *,
    [data-baseweb="popover"] *,
    [role="listbox"] *,
    [role="option"] { color:#f5fbfd !important; }
    [data-baseweb="popover"],
    [role="listbox"] { background:#172a34 !important; border-color:#83aab8 !important; }
    [role="option"]:hover, [role="option"][aria-selected="true"] { background:#285565 !important; }
    .stApp [data-testid="stCaptionContainer"],
    .stApp [data-testid="stCaptionContainer"] * { color:#c7d8de !important; opacity:1 !important; }
    [data-testid="stImage"] + div,
    [data-testid="stImage"] + div p,
    .comment-tag, .chat-time { color:#b7cbd2 !important; opacity:1 !important; }
    .stApp [data-testid="stAlert"] { color:#f5fbfd !important; }
    .stApp [data-testid="stAlert"] * { color:inherit !important; }
    .stApp [data-testid="stSpinner"] p { color:#e6f0f3 !important; }
    .stApp a { color:#b9edf5 !important; }
    .stApp a:hover { color:#ffffff !important; }
    .support-limit {
        background:#4a2f22 !important;
        border:2px solid #e5a36e !important;
        border-radius:10px;
        color:#fff4e8 !important;
        padding:.85rem 1rem;
        margin:.8rem 0 1rem;
        font-weight:700;
        line-height:1.55;
    }
    .support-limit strong { color:#ffd19f !important; }
    .metric {
        background:#1d3440 !important;
        border:1px solid #709baa !important;
        color:#eaf8fb !important;
    }
    .metric strong { color:#ffffff !important; font-size:1.65rem; }
    /* Refined entry screen: cool midnight glass with a restrained warm accent. */
    .intro-shell {
        min-height:660px;
        border:1px solid rgba(169,205,214,.42);
        border-radius:28px;
        background:#08131b;
        box-shadow:0 30px 90px rgba(0,0,0,.52), inset 0 1px 0 rgba(255,255,255,.08);
    }
    .intro-art {
        opacity:.9;
        filter:saturate(.72) contrast(1.12) brightness(.96);
        transform:scale(1.015);
    }
    .intro-shade {
        background:
            linear-gradient(90deg,rgba(5,12,18,.18) 0%,rgba(5,12,18,.02) 48%,rgba(5,12,18,.32) 100%),
            linear-gradient(0deg,rgba(4,9,14,.97) 0%,rgba(4,9,14,.78) 27%,rgba(4,9,14,.12) 69%,rgba(4,9,14,.05) 100%);
    }
    .intro-content { min-height:660px; padding:3.4rem; padding-top:20rem; }
    .intro-title {
        color:#f6fbfc !important;
        font-size:5.8rem;
        letter-spacing:-.07em;
        text-shadow:0 8px 34px rgba(0,0,0,.38);
    }
    .intro-lead { color:#edf8fa !important; font-size:1.28rem; letter-spacing:-.02em; }
    .intro-copy { color:#bfd2d8 !important; max-width:590px; }
    .intro-page + div[data-testid="stButton"] { margin:1.1rem auto 0; max-width:360px; }
    .intro-page + div[data-testid="stButton"] button {
        min-height:3.35rem;
        border-radius:999px !important;
        border:1px solid #b9e7e8 !important;
        background:linear-gradient(135deg,#2b7f8d,#245b71) !important;
        color:#ffffff !important;
        font-size:1rem !important;
        letter-spacing:.02em;
        box-shadow:0 12px 28px rgba(24,103,119,.28) !important;
    }
    .intro-page + div[data-testid="stButton"] button:hover {
        background:linear-gradient(135deg,#3b9aaa,#2c7087) !important;
        border-color:#efffff !important;
        transform:translateY(-2px);
        box-shadow:0 16px 34px rgba(40,145,158,.34) !important;
    }
    .intro-page + div[data-testid="stButton"] button p,
    .intro-page + div[data-testid="stButton"] button span { color:#ffffff !important; }
    /* A quiet night-sky texture keeps the agora present without competing with content. */
    .stApp {
        background-color:#080d12 !important;
        background-image:
            linear-gradient(rgba(5,12,18,.84), rgba(5,12,18,.92)),
            url("__AGORA_BACKGROUND_IMAGE__"),
            radial-gradient(circle at 8% 8%, rgba(43,121,141,.18), transparent 28rem),
            radial-gradient(circle at 92% 22%, rgba(177,103,66,.13), transparent 25rem),
            radial-gradient(circle at 50% 100%, rgba(35,79,98,.18), transparent 34rem),
            repeating-linear-gradient(135deg, rgba(255,255,255,.018) 0, rgba(255,255,255,.018) 1px, transparent 1px, transparent 72px) !important;
        background-size:cover, cover, auto, auto, auto, auto !important;
        background-position:center, center, center, center, center, center !important;
        background-repeat:no-repeat, no-repeat, no-repeat, no-repeat, no-repeat, repeat !important;
        background-attachment:fixed !important;
    }
    .block-container {
        position:relative;
        background:rgba(8,16,23,.42);
        border:1px solid rgba(114,157,170,.14);
        border-radius:28px;
        box-shadow:0 24px 80px rgba(0,0,0,.18), inset 0 1px 0 rgba(255,255,255,.025);
        backdrop-filter:blur(2px);
    }
    .block-container::before {
        content:"";
        position:absolute;
        inset:0;
        border-radius:28px;
        pointer-events:none;
        background:
            radial-gradient(circle at 14% 12%, rgba(185,237,245,.08) 0 1px, transparent 2px),
            radial-gradient(circle at 82% 28%, rgba(185,237,245,.06) 0 1px, transparent 2px),
            radial-gradient(circle at 66% 88%, rgba(229,163,110,.06) 0 1px, transparent 2px);
        background-size:180px 180px, 240px 240px, 210px 210px;
        opacity:.7;
    }
    .insight-book {
        position:relative;
        display:grid;
        grid-template-columns:1fr 1fr;
        margin:1.4rem 0 1.8rem;
        border:1px solid rgba(224,190,144,.55);
        border-radius:18px;
        overflow:hidden;
        background:linear-gradient(135deg,#2a2020,#161b22);
        box-shadow:0 20px 45px rgba(0,0,0,.28), inset 0 1px 0 rgba(255,255,255,.08);
    }
    .insight-book::after {
        content:"";
        position:absolute;
        top:0;
        bottom:0;
        left:50%;
        width:1px;
        background:rgba(232,205,166,.3);
        box-shadow:0 0 18px rgba(0,0,0,.65);
    }
    .insight-page {
        min-height:230px;
        padding:1.45rem 1.5rem 1.35rem;
        background:linear-gradient(105deg,rgba(248,235,205,.98),rgba(227,208,172,.94));
        color:#46372c !important;
    }
    .insight-page.right {
        background:linear-gradient(255deg,rgba(244,228,194,.98),rgba(218,196,155,.95));
    }
    .insight-page * { color:#46372c !important; }
    .insight-book-kicker { color:#9a5c3e !important; font-size:.67rem; font-weight:800; letter-spacing:.16em; }
    .insight-author { font-family:'DM Serif Display',serif; font-size:1.55rem; margin:.45rem 0 .1rem; }
    .insight-concept { font-size:.76rem; font-weight:700; color:#80604d !important; }
    .insight-quote { font-family:'DM Serif Display',serif; font-size:1.23rem; line-height:1.45; margin:1.15rem 0 .5rem; }
    .insight-quote-mark { color:#b56c4a !important; font-size:2rem; line-height:0; vertical-align:-.25rem; margin-right:.1rem; }
    .insight-interpretation { font-size:.83rem; line-height:1.65; margin-top:.7rem; }
    .insight-action { margin-top:1rem; padding:.65rem .75rem; border-left:3px solid #b56c4a; background:rgba(255,248,230,.5); font-size:.78rem; line-height:1.5; }
    .insight-tags { margin-top:.8rem; color:#9a5c3e !important; font-size:.72rem; font-weight:700; letter-spacing:.02em; }
    @media (max-width:640px) {
        .insight-book { grid-template-columns:1fr; }
        .insight-book::after { top:50%; left:0; right:0; width:auto; height:1px; }
        .insight-page { min-height:0; }
    }
    .app-topbar { display:flex; align-items:center; justify-content:space-between; gap:1rem; padding:.2rem 0 .85rem; margin-bottom:.2rem; border-bottom:1px solid rgba(174,227,238,.18); }
    .app-topbar-brand { color:#eef9fb !important; font-size:.75rem; font-weight:800; letter-spacing:.16em; }
    .app-topbar-brand span { color:#9fc3cb !important; font-weight:500; letter-spacing:.02em; }
    .app-topbar-note { color:#9eb4bc !important; font-size:.78rem; }
    .app-topbar { margin-bottom:1.4rem; }
    .block-container { max-width:1180px; padding:1.4rem 2.5rem 5rem; }
    .home-feature { min-height:12.5rem; padding:1.35rem 1.45rem; transition:transform .18s ease, border-color .18s ease, box-shadow .18s ease; }
    .home-feature:hover { transform:translateY(-2px); border-color:#a9e5ee; box-shadow:0 16px 32px rgba(0,0,0,.22); }
    .home-feature-title { font-size:1.45rem; }
    .home-feature-copy { min-height:4.1rem; }
    .mentor-hero { margin-top:1.5rem; }
    .landing-section-label { color:#aee3ee !important; font-size:.72rem; font-weight:800; letter-spacing:.16em; margin:2.2rem 0 .7rem; }
    .landing-section-copy { color:#c7d8de !important; max-width:42rem; line-height:1.7; margin-bottom:1rem; }
    .section-divider { height:1px; background:rgba(174,227,238,.14); margin:2.2rem 0; }
    @media (max-width:760px) {
        .block-container { padding:1rem 1rem 4rem; }
        .app-topbar { align-items:flex-start; flex-direction:column; gap:.35rem; }
        .app-topbar-note { font-size:.72rem; }
        .mentor-hero-grid { grid-template-columns:1fr; }
        .mentor-glow-card { min-height:0; }
    }
    @media (max-width: 640px) { h1 { font-size:3.4rem; } .brand-wordmark { font-size:3.5rem; } .block-container { padding-top:1.2rem; } }
    /* Final control language: quiet surfaces, clear hierarchy, no generic dashboard gloss. */
    div[data-testid="stButton"] button,
    .stDownloadButton button {
        min-height:2.8rem !important;
        padding:.62rem 1.05rem !important;
        border-radius:7px !important;
        border:1px solid rgba(164,204,211,.42) !important;
        background:rgba(18,39,49,.84) !important;
        color:#dcecef !important;
        font-family:'Noto Sans KR',sans-serif !important;
        font-size:.87rem !important;
        font-weight:700 !important;
        letter-spacing:0 !important;
        box-shadow:inset 0 1px 0 rgba(255,255,255,.06), 0 5px 16px rgba(0,0,0,.12) !important;
        transition:background .18s ease, border-color .18s ease, color .18s ease, transform .18s ease, box-shadow .18s ease !important;
    }
    div[data-testid="stButton"] button p,
    div[data-testid="stButton"] button span,
    .stDownloadButton button p,
    .stDownloadButton button span { color:inherit !important; font-family:inherit !important; }
    div[data-testid="stButton"] button:hover,
    .stDownloadButton button:hover {
        background:#214957 !important;
        border-color:#9ddbe2 !important;
        color:#ffffff !important;
        transform:translateY(-1px);
        box-shadow:inset 0 1px 0 rgba(255,255,255,.1), 0 9px 22px rgba(0,0,0,.22) !important;
    }
    div[data-testid="stButton"] button:focus-visible,
    .stDownloadButton button:focus-visible { outline:2px solid #e5a36e !important; outline-offset:3px; }
    div[data-testid="stButton"] button[kind="primary"] {
        background:#c47b55 !important;
        border-color:#efb38a !important;
        color:#fff8f0 !important;
        box-shadow:inset 0 1px 0 rgba(255,255,255,.16), 0 8px 22px rgba(160,82,52,.24) !important;
    }
    div[data-testid="stButton"] button[kind="primary"]:hover {
        background:#d48b62 !important;
        border-color:#ffe0c4 !important;
        color:#ffffff !important;
        box-shadow:inset 0 1px 0 rgba(255,255,255,.2), 0 11px 28px rgba(181,108,74,.34) !important;
    }
    div[data-testid="stButton"] button:disabled,
    .stDownloadButton button:disabled { background:#1a2b32 !important; color:#81949a !important; border-color:#425a62 !important; transform:none; box-shadow:none !important; }
    .intro-page + div[data-testid="stButton"] button { min-height:3.25rem !important; border-radius:7px !important; font-size:.95rem !important; }
    .home-feature + div[data-testid="stButton"] button { margin-top:.55rem; }
    .mentor-answer { min-height:6.8rem !important; padding:1rem !important; text-align:left !important; }
    .stApp [data-testid="stFormSubmitButton"] button { min-height:3rem !important; }
    /* Editorial spacing: give each idea a clear pause before the next one begins. */
    h2 { margin-top:2rem !important; margin-bottom:1rem !important; }
    h3 { margin-top:1.8rem !important; margin-bottom:.85rem !important; }
    h4, h5 { margin-top:1.35rem !important; margin-bottom:.7rem !important; }
    .beta-notice { margin:1.25rem 0 1.7rem !important; padding:1.15rem 1.3rem !important; }
    .magazine-card { margin:1.5rem 0 1.8rem !important; padding:1.5rem 1.55rem !important; }
    .magazine-question { margin-top:1.35rem !important; padding:.85rem 1rem !important; }
    .comment-card { margin:.8rem 0 !important; padding:1rem 1.1rem !important; }
    .comment-text { margin-top:.6rem !important; line-height:1.75 !important; }
    .parallel-age-card { margin:1.5rem 0 2rem !important; padding:1.45rem 1.55rem !important; }
    .parallel-age-section { margin-top:1.35rem !important; padding-top:1.15rem !important; }
    .parallel-age-section + .parallel-age-section { margin-top:1.55rem !important; }
    .parallel-age-context { margin:1.25rem 0 !important; padding:1rem 1.05rem !important; }
    .parallel-age-inference { margin-top:1.55rem !important; padding:1.05rem !important; }
    .chat-window { margin:1rem 0 2rem !important; padding:1.35rem 1rem !important; }
    .chat-row { margin:1.05rem .35rem !important; }
    .insight-card { margin:.8rem 0 !important; padding:1.15rem 1.2rem !important; }
    .callout { margin:1rem 0 !important; padding:1.2rem 1.35rem !important; }
    .mentor-profile-row { padding:1rem 0 .35rem !important; }
    .mentor-report { margin:.55rem 0 !important; }
    .similarity-section, .radar-card, .conflict-section, .detailed-profile-section { margin-top:1.8rem !important; }
    .section-divider { margin:2.7rem 0 !important; }
    div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stHorizontalBlock"]) { gap:.55rem; }
    </style>""".replace("__AGORA_BACKGROUND_IMAGE__", image_data_url(INTRO_IMAGE))
st.markdown(background_styles, unsafe_allow_html=True)

if st.session_state.screen != "intro":
    render_topbar()


if st.session_state.screen == "intro":
    intro_image = image_data_url(INTRO_IMAGE)
    st.markdown(
        f'<div class="intro-page"><div class="intro-shell">'
        f'<img class="intro-art" src="{intro_image}" alt="두 인물이 마주 앉아 대화하는 장면">'
        f'<div class="intro-shade"></div><div class="intro-content">'
        f'<div class="intro-title">Virtual<br>Agora</div>'
        f'<div class="intro-lead">다른 시대의 사람을 만나고,<br>오늘의 나를 조금 더 선명하게 바라봅니다.</div>'
        f'</div></div></div>',
        unsafe_allow_html=True,
    )
    if st.button("입장하기  →", type="primary", use_container_width=True, key="enter-agora"):
        st.session_state.screen = "landing"
        st.rerun()


elif st.session_state.screen == "landing":
    st.markdown('<div class="eyebrow">A CONVERSATION ACROSS TIME</div>', unsafe_allow_html=True)
    st.markdown('<div class="brand-wordmark">Virtual Agora</div>', unsafe_allow_html=True)
    st.markdown(
        '''
        <div class="mentor-hero">
          <div class="mentor-hero-grid">
            <div>
              <div class="mentor-kicker">FIND YOUR AGORA MENTOR</div>
                            <div class="mentor-title">지금의 나를 비추는 인물을 만나보세요.</div>
              <div class="mentor-copy">
                                정답을 맞히는 테스트가 아닙니다. 선택의 습관과 마음이 움직이는 방향을 천천히 살펴보고,
                                지금의 나와 대화가 잘 이어질 인물을 찾아봅니다. 결과는 결론이 아니라, 나를 돌아보는 첫 질문입니다.
              </div>
              <div class="mentor-meta">
                <span class="mentor-meta-badge">12문항</span>
                <span class="mentor-meta-badge">개인 맞춤</span>
                <span class="mentor-meta-badge">생각하는 방식 중심</span>
              </div>
            </div>
            <div class="mentor-glow-card">
              <div class="mini-label">MENTOR POOL</div>
              <div class="mini-score">30</div>
              <div class="mini-copy">서로 다른 시대의 30명 인물 중, 당신의 가치와 가장 유사한 인물을 찾습니다.</div>
            </div>
          </div>
        </div>
        ''',
        unsafe_allow_html=True,
    )
    if st.button("나와 잘 맞는 인물 찾기", type="primary", use_container_width=True, key="mentor-primary-entry"):
        st.session_state.update({"screen": "mentor_landing", "mentor_index": 0, "mentor_scores": {axis: 0 for axis in MENTOR_AXES}})
        st.rerun()
    st.write("")
    st.markdown(
        '<p class="tagline">AI 시대, 인간으로서의 방향성을 찾아 떠나보자.<br>'
        '여러 위인들의 페르소나를 깊이 반영한 가상의 대화와 의견을 통해<br>'
        '나만의 길을 더 정직하게 살펴보는 공간입니다.</p>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="landing-section-label">CHOOSE YOUR ENTRANCE</div>', unsafe_allow_html=True)
    st.markdown('<div class="landing-section-copy">지금 필요한 방식으로 광장에 들어오세요. 대화를 시작해도 좋고, 먼저 내 마음과 비슷한 시절을 만나도 좋습니다.</div>', unsafe_allow_html=True)
    feature_a, feature_b = st.columns(2, gap="medium")
    with feature_a:
        st.markdown('<div class="home-feature"><div class="home-feature-kicker">01 · DIALOGUE</div><div class="home-feature-title">인물 대화</div><div class="home-feature-copy">서로 다른 시대의 인물들이 다양한 주제를 놓고 각자의 관점으로 토론합니다.</div></div>', unsafe_allow_html=True)
        if st.button("두 사람의 대화 열기  →", type="primary", use_container_width=True):
            st.session_state.screen = "select"
            st.rerun()
    with feature_b:
        st.markdown('<div class="home-feature"><div class="home-feature-kicker">02 · PERSPECTIVES</div><div class="home-feature-title">인물 코멘트</div><div class="home-feature-copy">당신이 던진 주제에 아홉 인물이 각자의 경험과 가치관으로 댓글을 남깁니다.</div></div>', unsafe_allow_html=True)
        if st.button("여러 시선 모아보기  →", use_container_width=True):
            start_ask_mode(PEOPLE[0])
            st.rerun()
    feature_c, feature_d = st.columns(2, gap="medium")
    with feature_c:
        st.markdown('<div class="home-feature"><div class="home-feature-kicker">03 · MAGAZINE</div><div class="home-feature-title">오늘의 아고라</div><div class="home-feature-copy">가상의 최신 이슈에 역사적 인물들이 남긴 코멘트를 읽어봅니다.</div></div>', unsafe_allow_html=True)
        if st.button("오늘의 질문 읽기  →", use_container_width=True):
            st.session_state.screen = "magazine"
            st.rerun()
    with feature_d:
        st.markdown('<div class="home-feature"><div class="home-feature-kicker">04 · PARALLEL AGE</div><div class="home-feature-title">평행 시절</div><div class="home-feature-copy">내 나이·감정·고민을 같은 시절을 지나온 인물의 기록과 나란히 살펴봅니다.</div></div>', unsafe_allow_html=True)
        if st.button("평행 시절 살펴보기  →", use_container_width=True):
            st.session_state.screen = "parallel_age"
            st.rerun()
    st.write("")
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    # === 역사적 통찰 ===
    if "insight_index" not in st.session_state or not (0 <= st.session_state.insight_index < len(RANDOM_INSIGHTS)):
        st.session_state.insight_index = random.randrange(len(RANDOM_INSIGHTS))
    insight = RANDOM_INSIGHTS[st.session_state.insight_index]
    insight_tags = " ".join(insight["tags"])
    source_label = insight.get("source_type", "사상 기반 해석")
    st.markdown(
        f'<section class="insight-book">'
        f'<div class="insight-page"><div class="insight-book-kicker">AGORA NOTE · 역사적 통찰</div>'
        f'<div class="insight-author">{html.escape(insight["character"])}</div>'
        f'<div class="insight-concept">{html.escape(insight["concept"])} · {html.escape(source_label)}</div>'
        f'<div class="insight-quote"><span class="insight-quote-mark">“</span>{html.escape(insight["quote"])}<span class="insight-quote-mark">”</span></div>'
        f'<div class="insight-tags">{html.escape(insight_tags)}</div></div>'
        f'<div class="insight-page right"><div class="insight-book-kicker">AGORA NOTE</div>'
        f'<div class="insight-interpretation">{html.escape(insight["interpretation"])}</div>'
        f'<div class="insight-action"><b>출처 기준</b><br>{html.escape(insight.get("source_note", "사상과 전승을 바탕으로 한 해석입니다."))}</div>'
        f'<div class="insight-action" style="margin-top:.7rem"><b>오늘의 작은 실천</b><br>{html.escape(insight["action"])}</div></div>'
        f'</section>',
        unsafe_allow_html=True,
    )
    if st.button("다른 인물의 관점 보기  ↻", use_container_width=True, key="new-insight"):
        current_index = st.session_state.insight_index
        candidates = [index for index in range(len(RANDOM_INSIGHTS)) if index != current_index]
        st.session_state.insight_index = random.choice(candidates)
        st.rerun()
    st.write("")
    st.markdown('<div class="landing-section-label">CURATED CONVERSATIONS</div>', unsafe_allow_html=True)
    st.markdown('<div class="landing-section-copy">처음이라면 아래 대화 중 하나를 골라 광장의 분위기를 먼저 느껴보세요.</div>', unsafe_allow_html=True)
    for a, b, topic in [
        ("유명 채용 플랫폼 대표", "스티브 잡스", "AI 시대, 인간은 어떻게 살아남을 것인가"),
        ("예수", "부처", "AI시대, 종교의 방향"),
        ("이순신", "세종대왕", "AI시대, 리더쉽의 방향"),
        ("소크라테스", "니체", "생성형 AI와 창의적인 직업의 미래"),
    ]:
        card_a, card_b, card_action = st.columns([1, 1, 1.4])
        with card_a:
            if a in PEOPLE_INFO:
                st.image(EXAMPLE_PORTRAITS.get(a, PEOPLE_INFO[a][1]), caption=a, use_container_width=True)
        with card_b:
            if b in PEOPLE_INFO:
                st.image(EXAMPLE_PORTRAITS.get(b, PEOPLE_INFO[b][1]), caption=b, use_container_width=True)
        with card_action:
            st.markdown(f"**{a} × {b}**  \n<span class='person-caption'>{topic}</span>", unsafe_allow_html=True)
            if st.button("이 조합 바로 보기", key=f"showcase-{a}-{b}", type="primary", use_container_width=True):
                start_showcase(a, b, topic)
                st.rerun()


elif st.session_state.screen == "mentor_landing":
    render_scroll_to_top()
    if st.button("← 홈으로", key="mentor-landing-home", use_container_width=True):
        go_to_screen("landing")
    st.markdown('<div class="eyebrow">04 · MENTOR MATCHING</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="mentor-hero"><div class="mentor-kicker">FIND YOUR AGORA MENTOR</div>'
        '<div class="mentor-title">나와 잘 맞는 인물 찾기</div>'
        '<div class="mentor-copy">당신의 사고방식, 가치관, 선택 습관을 정리해 12문항으로 살펴봅니다. '
        '이 질문들이 당신과 가장 닮은 역사 인물을 찾는 시작점이 됩니다.</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="beta-notice" style="margin-top:1rem"><strong>왜 이 질문부터 시작할까요?</strong>'
        '<span>12개의 질문에 답하면, 지금의 생각과 가장 잘 맞는 인물을 찾아드립니다. 결과는 성격을 단정하는 판정이 아니라, 나를 더 잘 이해하기 위한 대화의 시작점입니다.</span></div>',
        unsafe_allow_html=True,
    )
    st.caption("깊게 고민하지 말고, 첫 번째로 떠오르는 답을 고르세요.")
    if st.button("질문 시작하기", type="primary", use_container_width=True, key="mentor-start"):
        reset_mentor_state()
        st.session_state.screen = "mentor_quiz"
        st.rerun()


elif st.session_state.screen == "mentor_quiz":
    render_scroll_to_top()
    if st.button("← 소개로 돌아가기", key="mentor-quiz-back", use_container_width=True):
        go_back_screen(default_screen="mentor_landing")
    question_index = st.session_state.get("mentor_index", 0)
    question = MENTOR_QUESTIONS[question_index]
    st.markdown('<div class="eyebrow">MENTOR MATCHING · QUICK TEST</div>', unsafe_allow_html=True)
    st.progress((question_index + 1) / len(MENTOR_QUESTIONS), text=f"Progress: {question_index + 1} / {len(MENTOR_QUESTIONS)}")
    st.markdown(
        f'<div class="mentor-question"><div class="mentor-question-number">QUESTION {question_index + 1:02d}</div>'
        f'<div class="mentor-question-title">{html.escape(question["prompt"])}</div></div>',
        unsafe_allow_html=True,
    )
    answer_a, answer_c, answer_b = st.columns([1, 0.62, 1], gap="small")
    for column, answer_key in ((answer_a, "a"), (answer_b, "b")):
        with column:
            answer_text, _ = question[answer_key]
            if st.button(answer_text, key=f"mentor-answer-{question_index}-{answer_key}", use_container_width=True, type="primary"):
                scores = st.session_state.get("mentor_scores", {axis: 0 for axis in MENTOR_AXES}).copy()
                history = st.session_state.get("mentor_answer_history", [])
                history.append({"index": question_index, "scores": scores.copy(), "response": answer_key})
                st.session_state.mentor_answer_history = history
                scores = apply_question_response(scores, question, answer_key)
                st.session_state.mentor_scores = scores
                if question_index + 1 == len(MENTOR_QUESTIONS):
                    mentor, group, score = calculate_best_mentor(scores)
                    rankings = calculate_mentor_rankings(scores)
                    conflicts = conflicting_mentors(scores)
                    st.session_state.update({
                        "screen": "mentor_result",
                        "mentor": mentor,
                        "mentor_group": group,
                        "mentor_score": score,
                        "mentor_report": enhanced_mentor_report(scores, group),
                        "mentor_rankings": rankings,
                        "mentor_conflicts": conflicts,
                    })
                else:
                    st.session_state.mentor_index = question_index + 1
                st.rerun()
    with answer_c:
        if st.button("잘 모르겠다", key=f"mentor-answer-{question_index}-c", use_container_width=True):
            scores = st.session_state.get("mentor_scores", {axis: 0 for axis in MENTOR_AXES}).copy()
            history = st.session_state.get("mentor_answer_history", [])
            history.append({"index": question_index, "scores": scores.copy(), "response": "neutral"})
            st.session_state.mentor_answer_history = history
            scores = apply_question_response(scores, question, "neutral")
            st.session_state.mentor_scores = scores
            if question_index + 1 == len(MENTOR_QUESTIONS):
                mentor, group, score = calculate_best_mentor(scores)
                rankings = calculate_mentor_rankings(scores)
                conflicts = conflicting_mentors(scores)
                st.session_state.update({
                    "screen": "mentor_result",
                    "mentor": mentor,
                    "mentor_group": group,
                    "mentor_score": score,
                    "mentor_report": enhanced_mentor_report(scores, group),
                    "mentor_rankings": rankings,
                    "mentor_conflicts": conflicts,
                })
            else:
                st.session_state.mentor_index = question_index + 1
            st.rerun()

    if st.session_state.get("mentor_answer_history") and question_index > 0:
        if st.button("← 이전 선택지로", key="mentor-back-choice", use_container_width=True):
            history = st.session_state.get("mentor_answer_history", [])
            previous_state = history.pop()
            st.session_state.mentor_answer_history = history
            st.session_state.mentor_scores = previous_state.get("scores", {axis: 0 for axis in MENTOR_AXES})
            st.session_state.mentor_index = previous_state.get("index", max(0, question_index - 1))
            st.rerun()


elif st.session_state.screen == "mentor_result":
    render_scroll_to_top()
    if st.button("← 홈으로", key="mentor-result-home", use_container_width=True):
        go_to_screen("landing")
    mentor = st.session_state.mentor
    group = st.session_state.mentor_group
    quote, quote_note = MENTOR_QUOTES[group]
    mentor_portrait = avatar_image(mentor)
    mentor_portrait_markup = (
        f'<div class="mentor-result-portrait"><img src="{mentor_portrait}" alt="{html.escape(mentor)} 초상화"></div>'
        if mentor_portrait
        else f'<div class="mentor-result-portrait" aria-label="{html.escape(mentor)} 초상화">{html.escape(chat_avatar(mentor))}</div>'
    )
    report = st.session_state.mentor_report
    scores = st.session_state.get("mentor_scores", {})
    match_reason, match_evidence, match_difference = mentor_match_reasons(mentor, scores)
    mentor_tagline, mentor_resemblance, mentor_advice = mentor_story(mentor, scores)
    rankings = st.session_state.get("mentor_rankings", [])
    top_rankings = rankings[:5]
    conflict_person = conflicting_mentors(scores)[0][0] if scores else "-"
    match_score = int(round(top_rankings[0][2])) if top_rankings else 0
    match_score = max(0, min(100, match_score))
    tag_options = (("Action", "실행"), ("Innovation", "창의"), ("Logic", "논리"), ("Empathy", "공감"), ("Mastery", "집중"), ("Acceptance", "유연"), ("Order", "질서"), ("Reflection", "성찰"))
    tags = [label for axis, label in tag_options if scores.get(axis, 0) >= 3][:4]
    neutral_count = sum(1 for state in st.session_state.get("mentor_answer_history", []) if state.get("response") == "neutral")
    summary = mentor_match_summary(scores, neutral_count=neutral_count)
    mentor_viewpoint = mentor_viewpoint_for(mentor, scores)
    st.markdown('<div class="eyebrow">YOUR AGORA MENTOR · RESULT</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="mentor-result"><div class="mentor-result-head">{mentor_portrait_markup}<div class="mentor-result-heading">'
        f'<div class="mentor-kicker">YOUR AGORA MENTOR · 오늘의 멘토</div>'
        f'<div class="mentor-result-name">{html.escape(mentor)}</div>'
        f'<div class="mentor-result-group">{html.escape(group)}</div></div></div>'
        f'<div class="mentor-story-tagline">“{html.escape(mentor_tagline)}”</div>'
        f'<div class="mentor-story-section"><div class="mentor-story-label">선택의 닮은꼴</div>'
        f'<div class="mentor-story-text">{html.escape(mentor_resemblance)}</div></div>'
        f'<div class="mentor-story-section"><div class="mentor-story-label">이 인물이 건네는 팁</div>'
        f'<div class="mentor-story-text">“{html.escape(mentor_advice)}”</div></div>'
        f'<div class="mentor-story-section"><div class="mentor-story-label">이 인물의 한 문장</div>'
        f'<div class="mentor-story-text">“{html.escape(quote)}”<br><small>{html.escape(quote_note)}</small></div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(mentor_radar_chart(scores, mentor), unsafe_allow_html=True)
    similar_rankings = [item for item in rankings if item[0] != mentor][:2]
    contrast_ranking = conflicting_mentors(scores)[0] if scores else None
    st.markdown('<div class="mentor-comparison-title">당신의 다른 가능성</div>', unsafe_allow_html=True)
    comparison_columns = st.columns(2)
    for column, (person, person_group, score) in zip(comparison_columns, similar_rankings):
        person_image = avatar_image(person)
        image_markup = (
            f'<img src="{person_image}" alt="{html.escape(person)} 초상화">'
            if person_image
            else html.escape(chat_avatar(person))
        )
        with column:
            st.markdown(
                f'<div class="mentor-comparison-card"><div class="mentor-comparison-card-head">'
                f'<div class="mentor-comparison-avatar">{image_markup}</div><div>'
                f'<div class="mentor-comparison-name">{html.escape(person)}</div>'
                f'<div class="mentor-comparison-score">닮은 정도 {int(round(score))}% · {html.escape(person_group)}</div></div></div>'
                f'<div class="mentor-comparison-copy">{html.escape(mentor_comparison_phrase(person, scores))}</div></div>',
                unsafe_allow_html=True,
            )
    if contrast_ranking:
        contrast_person, contrast_group, contrast_score = contrast_ranking
        contrast_image = avatar_image(contrast_person)
        contrast_markup = (
            f'<img src="{contrast_image}" alt="{html.escape(contrast_person)} 초상화">'
            if contrast_image
            else html.escape(chat_avatar(contrast_person))
        )
        st.markdown(
            f'<div class="mentor-comparison-card contrast" style="margin-top:.75rem"><div class="mentor-comparison-card-head">'
            f'<div class="mentor-comparison-avatar">{contrast_markup}</div><div>'
            f'<div class="mentor-comparison-name">나와 가장 다른 인물 · {html.escape(contrast_person)}</div>'
            f'<div class="mentor-comparison-score">닮은 정도 {int(round(contrast_score))}% · {html.escape(contrast_group)}</div></div></div>'
            f'<div class="mentor-comparison-copy">{html.escape(mentor_comparison_phrase(contrast_person, scores, opposite=True))} '
            f'그래서 이 인물은 당신이 놓치기 쉬운 반대편의 선택을 보여줍니다.</div></div>',
            unsafe_allow_html=True,
        )
    with st.expander("내 답변이 만든 추천 과정을 더 보고 싶다면"):
        st.markdown(
            f"**추천된 이유**  \n{match_reason}  \n\n"
            f"**비교해 본 방향**  \n{match_evidence}  \n\n"
            f"**다르게 보이는 지점**  \n{match_difference}",
        )
    st.write("")

    if st.button(f"🎴 {mentor}와의 연결점 보기", type="primary", use_container_width=True, key="mentor-insight"):
        st.session_state.mentor_insight = quote_note
    if st.session_state.get("mentor_insight"):
        st.markdown(f'<div class="callout"><strong>{mentor}와의 연결점</strong><br>{html.escape(st.session_state.mentor_insight)}</div>', unsafe_allow_html=True)
    if st.button("다시 테스트하기", use_container_width=True, key="mentor-retry"):
        reset_mentor_state()
        st.session_state.screen = "mentor_quiz"
        st.rerun()
    st.write("")
    if st.button("🏠 홈으로", key="mentor-result-home-bottom", type="primary", use_container_width=True):
        go_to_screen("landing")


elif st.session_state.screen == "parallel_age":
    if st.button("← 홈으로", key="parallel-age-home", use_container_width=True):
        st.session_state.screen = "landing"
        st.rerun()
    st.markdown('<div class="eyebrow">04 · PARALLEL AGE</div>', unsafe_allow_html=True)
    st.header("평행 시절")
    st.markdown(
        '<div class="beta-notice"><strong>지금의 나와 비슷한 시절을 지나온 사람을 만나보세요.</strong>'
        '<span>나이대와 감정, 고민을 바탕으로 역사 속 기록을 연결합니다. 기록과 오늘의 해석은 분리해 보여드리며, 실제 인물의 발언을 재현하지 않습니다.</span></div>',
        unsafe_allow_html=True,
    )

    with st.form("parallel_age_form"):
        age = st.slider("지금 나는 몇 살인가요?", min_value=16, max_value=70, value=29, step=1)
        emotion = st.radio("요즘 가장 가까운 마음", options=PARALLEL_AGE_EMOTIONS, index=0)
        concern = st.radio("지금 가장 크게 걸리는 것", options=PARALLEL_AGE_CONCERNS, index=1)
        submitted = st.form_submit_button("나와 닿는 시절 찾기  →", type="primary", use_container_width=True)

    if submitted:
        parallel_cards = build_parallel_age_cards(age, emotion, concern, limit=4)
        st.session_state.parallel_age_result = enrich_parallel_age_cards_with_llm(
            parallel_cards,
            age=age,
            emotion=emotion,
            concern=concern,
        )

    result_cards = st.session_state.get("parallel_age_result", [])
    if result_cards:
        for card in result_cards:
            inferred_feeling = card["inferred_feeling"].replace("[공감적 재구성] ", "", 1)
            inferred_action = card["inferred_action"].replace("[오늘의 연결] ", "", 1)
            psychology_lens = card.get("psychology_lens", "이 시기의 감정은 정체성의 흔들림으로 이해할 수 있습니다.")
            counseling_translation = card.get("counseling_translation", "지금의 감정은 변화의 시기에서 자연스럽게 나타나는 혼란일 수 있습니다.")
            developmental_stage = card.get("developmental_stage", "인생 전환기")
            developmental_task = card.get("developmental_task", "삶의 방향을 다시 점검하는 단계")
            llm_markup = ""
            if card.get("llm_connection"):
                llm_markup = (
                    '<div class="parallel-age-section parallel-age-ai">'
                    '<div class="parallel-age-section-title">✦ 내 상황과 연결해 보기</div>'
                    f'<div class="parallel-age-ai-angle">{html.escape(card["llm_angle"])}</div>'
                    f'<div class="parallel-age-section-body"><strong>왜 지금 내 이야기처럼 느껴지는가:</strong> {html.escape(card["llm_connection"])}<br><br>'
                    f'<strong>내 마음에 대입해 보면:</strong> {html.escape(card["llm_emotion"])}<br><br>'
                    f'<strong>오늘 살펴볼 작은 행동:</strong> {html.escape(card["llm_action"])}</div>'
                    '</div>'
                )
            st.markdown(
                f'<article class="parallel-age-card">'
                f'<div class="parallel-age-header"><div>'
                f'<div class="parallel-age-source">{html.escape(card["label"])}</div>'
                f'<div class="parallel-age-person">{html.escape(card["person"])}</div>'
                f'<div class="parallel-age-age">{html.escape(card["age_label"])}</div>'
                f'<div class="parallel-age-match">{html.escape(card["age_match_label"])}</div>'
                f'</div></div>'
                f'<div class="parallel-age-context"><strong>시대 배경</strong><br>{html.escape(card["era_context"])}</div>'
                f'<div class="parallel-age-section"><div class="parallel-age-section-title">🧠 지금의 나와 이어지는 지점</div>'
                f'<div class="parallel-age-section-body"><strong>지금 겪고 있는 시기:</strong> {html.escape(developmental_stage)}<br><br>'
                f'<strong>이 시기에 자주 드는 질문:</strong> {html.escape(developmental_task)}<br><br>'
                f'<strong>내 감정과 닿는 이유:</strong> {html.escape(psychology_lens)}<br><br>'
                f'<strong>내 삶에 대입해 보면:</strong> {html.escape(counseling_translation)}</div>'
                f'</div>'
                f'<div class="parallel-age-section"><div class="parallel-age-section-title">📜 기록으로 확인되는 사건</div>'
                f'<div class="parallel-age-section-body">{html.escape(card["record_event"])}</div>'
                f'<div class="parallel-age-source-note"><strong>근거와 범위:</strong> {html.escape(card["record_detail"])}</div>'
                f'</div>'
                f'<div class="parallel-age-section"><div class="parallel-age-section-title">기록에서 이어지는 행보</div>'
                f'<div class="parallel-age-section-body">{html.escape(card["recorded_next_step"])}</div>'
                f'</div>'
                f'<div class="parallel-age-section parallel-age-inference"><div class="parallel-age-section-title">🧭 공감적 재구성 · 기록에 없는 내면</div>'
                f'<div class="parallel-age-section-body"><strong>그때의 마음을 오늘의 언어로 옮기면:</strong> {html.escape(inferred_feeling)}<br><br>'
                f'<strong>오늘의 연결:</strong> {html.escape(inferred_action)}</div>'
                f'</div>'
                f'{llm_markup}'
                f'<div class="parallel-age-source-note"><strong>{html.escape(card["label"])}:</strong> {html.escape(card["source_boundary"])}<br>'
                f'<strong>자료 표기:</strong> {html.escape(card["source_note"])}</div>'
                f'</article>',
                unsafe_allow_html=True,
            )
        st.caption("📜 기록으로 확인되는 사실과 🧭 오늘의 연결을 분리했습니다. 연결 문장은 해석이며, 실제 인물의 발언이나 확인된 심리 기록이 아닙니다.")
    else:
        st.info("나이대와 지금의 마음을 고르면, 나와 닿는 시절의 기록을 찾아드립니다.")

    if st.button("다시 하기", key="parallel-age-reset", use_container_width=True):
        st.session_state.parallel_age_result = []
        st.rerun()


elif st.session_state.screen == "magazine":
    if st.button("← 홈으로", key="magazine-home", use_container_width=True):
        st.session_state.screen = "landing"
        st.rerun()
    st.markdown('<div class="eyebrow">VIRTUAL AGORA · TODAY</div>', unsafe_allow_html=True)
    st.header("오늘의 질문")
    st.markdown(
        '<div class="beta-notice"><strong>가상 기사 · 인물 코멘터리</strong>'
        '<span>아래 기사는 오늘의 질문을 더 넓게 바라보기 위한 가상 이슈입니다. '
        '각 코멘트 역시 인물의 사상과 공개 기록을 참고해 AI가 창작한 가상 의견이며 실제 발언이 아닙니다.</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown("#### 오늘 우리가 함께 들여다볼 질문")
    for article_index, article in enumerate(MAGAZINE_ARTICLES):
        st.markdown(
            f'<article class="magazine-card"><div class="magazine-category">{article["category"]}</div>'
            f'<div class="magazine-title">{html.escape(article["title"])}</div>'
            f'<div class="magazine-dek">{html.escape(article["dek"])}</div>'
            f'<div class="magazine-body">{html.escape(article["body"])}</div>'
            f'<div class="magazine-question">EDITORIAL QUESTION · {html.escape(article["question"])}</div></article>',
            unsafe_allow_html=True,
        )
        st.markdown("##### 인물들의 댓글")
        for person, comment, tag in article["comments"]:
            avatar = avatar_image(person)
            avatar_markup = f'<img src="{avatar}" alt="{html.escape(person)} 프로필">' if avatar else html.escape(chat_avatar(person))
            st.markdown(
                f'<div class="comment-card"><span class="comment-head">'
                f'<span class="chat-avatar" style="display:inline-flex;vertical-align:middle;margin-right:.35rem">{avatar_markup}</span>'
                f'{html.escape(person)}</span><span class="comment-tag">#{html.escape(tag)}</span>'
                f'<div class="comment-text">{html.escape(comment)}</div></div>',
                unsafe_allow_html=True,
            )
        if article_index < len(MAGAZINE_ARTICLES) - 1:
            st.divider()
    st.caption("※ 매거진의 기사와 댓글은 모두 데모를 위한 가상 창작 콘텐츠입니다.")
    if st.button("홈으로", key="magazine-home-bottom", use_container_width=True):
        st.session_state.screen = "landing"
        st.rerun()


elif st.session_state.screen == "ask":
    if st.button("← 홈으로", key="ask-home", use_container_width=True):
        st.session_state.screen = "landing"
        st.rerun()
    st.markdown('<div class="eyebrow">VIRTUAL AGORA · PERSPECTIVES</div>', unsafe_allow_html=True)
    st.header("여러 시선 모아보기")
    st.markdown(
        '<div class="beta-notice"><strong>하나의 질문, 아홉 가지 시선</strong>'
        '<span>궁금한 주제를 적으면 각 인물이 공개적으로 알려진 사상과 경험을 참고해 서로 다른 관점을 남깁니다. '
        '모든 코멘트는 실제 발언이 아닌 가상 창작 콘텐츠입니다.</span></div>',
        unsafe_allow_html=True,
    )
    topic_prompt = st.text_area(
        "무엇을 다른 시선으로 보고 싶나요?",
        value=st.session_state.get("perspective_topic", ""),
        placeholder="예: 나이가 들수록 새로운 일을 시작하는 것은 무모한가요?",
        height=110,
    )
    st.session_state.perspective_topic = topic_prompt
    if st.button("시선 모아보기  →", type="primary", use_container_width=True):
        if not topic_prompt.strip():
            st.error("인물들의 시선을 보고 싶은 주제를 입력해주세요.")
        else:
            with st.spinner("아홉 인물이 각자의 시선을 정리하는 중…"):
                try:
                    st.session_state.perspective_comments = remote_perspective_comments(topic_prompt.strip())
                    st.session_state.perspective_topic = topic_prompt.strip()
                    st.rerun()
                except RuntimeError as error:
                    st.error(str(error))
    comments = st.session_state.get("perspective_comments", [])
    if comments:
        st.markdown(f"#### “{html.escape(st.session_state.perspective_topic)}”에 대한 코멘트")
        for comment_person, comment, tag in comments:
            avatar = avatar_image(comment_person)
            avatar_markup = f'<img src="{avatar}" alt="{html.escape(comment_person)} 프로필">' if avatar else html.escape(chat_avatar(comment_person))
            st.markdown(
                f'<div class="comment-card"><span class="comment-head"><span class="chat-avatar" style="display:inline-flex;vertical-align:middle;margin-right:.35rem">{avatar_markup}</span>{html.escape(comment_person)}</span>'
                f'<span class="comment-tag">#{html.escape(tag)}</span><div class="comment-text">{html.escape(comment)}</div></div>',
                unsafe_allow_html=True,
            )
    if st.button("홈으로", key="ask-home-bottom", use_container_width=True):
        st.session_state.screen = "landing"
        st.rerun()


elif st.session_state.screen == "select":
    if st.button("← 홈으로", key="select-home", use_container_width=True):
        st.session_state.screen = "landing"
        st.rerun()
    st.markdown('<div class="eyebrow">STEP 01 · GATHER YOUR GUESTS</div>', unsafe_allow_html=True)
    st.header("어떤 대화를 열어볼까요?")
    defaults = {
        "person_a": PEOPLE[0],
        "person_b": "스티브 잡스",
        "topic": TOPICS[0],
        "tone": 50,
    }
    st.markdown(
        '<div class="beta-notice"><strong>두 인물, 하나의 질문</strong>'
        '<span>준비된 주제를 골라도 좋고, 지금 마음에 걸리는 질문을 직접 적어도 좋습니다. '
        '모든 대화는 AI가 창작한 가상 시뮬레이션입니다.</span></div>',
        unsafe_allow_html=True,
    )
    saved_person_a = st.session_state.get("person_a", defaults["person_a"])
    saved_person_b = st.session_state.get("person_b", defaults["person_b"])
    person_a = st.selectbox(
        "첫 번째 목소리",
        PEOPLE,
        index=PEOPLE.index(saved_person_a) if saved_person_a in PEOPLE else 0,
    )
    person_b = st.selectbox(
        "두 번째 목소리",
        PEOPLE,
        index=PEOPLE.index(saved_person_b) if saved_person_b in PEOPLE else 1,
    )
    image_a, image_b = st.columns(2)
    with image_a:
        if person_a in PEOPLE_INFO:
            st.image(PEOPLE_INFO[person_a][1], caption=f"{person_a} · {PEOPLE_INFO[person_a][0]}", use_container_width=True)
    with image_b:
        if person_b in PEOPLE_INFO:
            st.image(PEOPLE_INFO[person_b][1], caption=f"{person_b} · {PEOPLE_INFO[person_b][0]}", use_container_width=True)
    topic_choices = [*TOPICS, "직접 주제 입력하기"]
    saved_topic = st.session_state.get("topic", defaults["topic"])
    saved_choice = "직접 주제 입력하기" if st.session_state.get("custom_topic", "").strip() else saved_topic
    topic_choice = st.radio(
        "두 사람이 함께 들여다볼 질문",
        topic_choices,
        horizontal=False,
        index=topic_choices.index(saved_choice) if saved_choice in topic_choices else 0,
    )
    custom_topic = ""
    if topic_choice == "직접 주제 입력하기":
        custom_topic = st.text_area(
            "지금 마음에 걸리는 질문을 적어주세요",
            value=st.session_state.get("custom_topic", ""),
            placeholder="예: 인간은 자신의 기억을 AI에게 맡겨도 괜찮을까요?",
            height=90,
            key="custom_topic",
        )
        topic = custom_topic.strip()
        if not topic:
            st.caption("질문은 선택한 두 인물의 관점에 맞춰 대화의 중심이 됩니다.")
    else:
        topic = topic_choice
        st.session_state.custom_topic = ""
    saved_intensity = st.session_state.get("tone", defaults["tone"])
    if not isinstance(saved_intensity, int):
        saved_intensity = 50
    slider_col, _ = st.columns([1.35, 1])
    with slider_col:
        intensity = st.slider(
            "대화의 온도",
            min_value=0,
            max_value=100,
            value=max(0, min(100, saved_intensity)),
            step=1,
            format="%d",
            help="왼쪽은 서로의 말을 오래 듣는 대화, 오른쪽은 관점이 선명하게 부딪히는 대화입니다.",
        )
    debate_name, debate_style, _, _ = debate_profile(intensity)
    temperature_label, temperature_color, temperature_description = temperature_visual(intensity)
    st.markdown(
        f'<div class="temperature-readout">'
        f'<div class="temperature-title" style="color:{temperature_color}">{temperature_label}</div>'
        f'<div class="temperature-track"><span style="width:{intensity}%;background:{temperature_color}"></span></div>'
        f'<div class="temperature-description">{temperature_description} · {debate_name}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if person_a and person_b and person_a == person_b:
        st.warning("서로 다른 인물을 골라주세요.")
    st.write("")
    left, right = st.columns([1, 2])
    with left:
        if st.button("← 홈으로", key="select-home-bottom", use_container_width=True):
            st.session_state.screen = "landing"
            st.rerun()
    with right:
        if st.button("이 질문으로 대화 열기  →", type="primary", use_container_width=True):
            if not person_a or not person_b or not topic:
                st.error("인물 두 명과 주제를 모두 입력해주세요.")
            elif person_a == person_b:
                st.error("서로 다른 인물을 골라주세요.")
            else:
                dialogue = None
                with st.status("두 인물이 광장에 모이는 중…", expanded=True) as generation_status:
                    try:
                        st.session_state.topic = topic
                        curated_dialogue = demo_dialogue(person_a, person_b, topic, debate_name)
                        if curated_dialogue is not None:
                            generation_status.write("준비된 큐레이션 대화를 불러오는 중")
                            dialogue = curated_dialogue
                        else:
                            generation_status.write("두 인물의 시대와 관점을 정리하는 중")
                            dialogue = remote_dialogue(person_a, person_b, topic, intensity)
                        generation_status.update(label="대화가 준비되었습니다.", state="complete", expanded=False)
                    except RuntimeError as error:
                        generation_status.update(label="대화를 준비하지 못했습니다.", state="error", expanded=True)
                        st.error(str(error))
                if dialogue is not None:
                    st.session_state.update(
                        {
                            "screen": "result",
                            "dialogue": dialogue,
                            "person_a": person_a,
                            "person_b": person_b,
                            "topic": topic,
                            "tone": intensity,
                            "direct_messages": [],
                            "dialogue_followups": [],
                            "dialogue_followup_prompt": "",
                        }
                    )
                    st.rerun()


else:
    person_a, person_b = st.session_state.person_a, st.session_state.person_b
    topic, tone = st.session_state.topic, st.session_state.tone
    dialogue: Dialogue = st.session_state.dialogue
    back_col, home_col = st.columns(2)
    with back_col:
        if st.button("← 설정으로 돌아가기", key="result-back", use_container_width=True):
            if st.session_state.get("person_a") not in PEOPLE:
                st.session_state.person_a = PEOPLE[0]
            if st.session_state.get("person_b") not in PEOPLE:
                st.session_state.person_b = PEOPLE[1]
            st.session_state.screen = "select"
            st.rerun()
    with home_col:
        if st.button("홈으로", key="result-home", use_container_width=True):
            st.session_state.screen = "landing"
            st.rerun()
    st.markdown('<div class="eyebrow">STEP 02 · THE AGORA SPEAKS</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="topic-hero"><div class="topic-kicker">오늘의 논제</div>'
        f'<div class="topic-title">{html.escape(topic)}</div></div>',
        unsafe_allow_html=True,
    )
    st.header(f"{person_a} × {person_b}")
    stance_a, stance_b, conflict, _ = viewpoint_cards(person_a, person_b, topic)
    if dialogue.stance_a and dialogue.stance_b and dialogue.conflict:
        stance_a, stance_b, conflict = (
            dialogue.stance_a,
            dialogue.stance_b,
            dialogue.conflict,
        )
    st.subheader("대화")
    bubbles = "".join(chat_bubble(speaker, line, person_a, turn) for turn, (speaker, line) in enumerate(dialogue.script, 1))
    st.markdown(
        f'<div class="chat-window"><div class="chat-window-head"><span class="chat-status"></span>'
        f'<span class="chat-title">{html.escape(person_a)} × {html.escape(person_b)}</span>'
        f'<span class="chat-subtitle">{len(dialogue.script)}개의 메시지</span></div>{bubbles}</div>',
        unsafe_allow_html=True,
    )
    st.subheader("두 인물들의 입장 요약")
    insight_a, insight_b = st.columns(2)
    with insight_a:
        st.markdown(
            f'<div class="insight-card"><b>{html.escape(person_a)}</b>'
            f'<strong>{html.escape(stance_a)}</strong></div>',
            unsafe_allow_html=True,
        )
    with insight_b:
        st.markdown(
            f'<div class="insight-card"><b>{html.escape(person_b)}</b>'
            f'<strong>{html.escape(stance_b)}</strong></div>',
            unsafe_allow_html=True,
        )
    st.subheader("두 인물의 입장 차이")
    st.markdown(
        f'<div class="insight-card"><strong>{html.escape(conflict)}</strong></div>',
        unsafe_allow_html=True,
    )
    st.subheader("내 의견 전달하기")
    st.caption("이 대화에서 떠오른 의견이나 질문을 남기면, 두 인물이 지금까지의 대화 맥락을 바탕으로 답합니다.")
    with st.form("dialogue_followup_form", clear_on_submit=False):
        user_message = st.text_area(
            "의견 또는 질문",
            placeholder="예: 두 분의 말을 들어보니, 현실적인 생존과 인간다운 열정은 함께 설계해야 한다고 생각합니다. 그렇다면 첫 단계는 무엇인가요?",
            height=120,
            key="dialogue_user_message",
            label_visibility="collapsed",
        )
        followup_submitted = st.form_submit_button("두 인물의 추가 의견 받기  →", type="primary", use_container_width=True)
    if followup_submitted:
        if not user_message.strip():
            st.warning("의견이나 질문을 입력해주세요.")
        else:
            with st.status("두 인물이 당신의 의견을 읽는 중…", expanded=True) as followup_status:
                try:
                    followup_status.write("지금까지의 대화와 연결점을 찾는 중")
                    st.session_state.dialogue_followups = remote_dialogue_followup(
                        person_a,
                        person_b,
                        topic,
                        dialogue.script,
                        user_message.strip(),
                    )
                    st.session_state.dialogue_followup_prompt = user_message.strip()
                    followup_status.update(label="두 인물의 답변이 도착했습니다.", state="complete", expanded=False)
                    st.rerun()
                except RuntimeError as error:
                    followup_status.update(label="추가 의견을 받지 못했습니다.", state="error", expanded=True)
                    st.error(str(error))
    followup_prompt = st.session_state.get("dialogue_followup_prompt")
    followups = st.session_state.get("dialogue_followups", [])
    if followup_prompt and followups:
        st.markdown(
            f'<div class="callout"><strong>내 의견</strong><br>{html.escape(followup_prompt)}</div>',
            unsafe_allow_html=True,
        )
        for speaker, reply in followups:
            st.markdown(
                f'<div class="insight-card"><b>{html.escape(speaker)}의 추가 의견</b>'
                f'<strong>{html.escape(reply)}</strong></div>',
                unsafe_allow_html=True,
            )
    if st.button("홈으로", key="result-home-bottom", use_container_width=True):
        st.session_state.screen = "landing"
        st.rerun()
