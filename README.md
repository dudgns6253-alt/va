# Virtual Agora

서로 다른 시대의 인물에게 오늘의 질문을 던지고, 한 가지 정답 대신 더 나은 질문과 관점을 발견하는 인터랙티브 대화 실험입니다.

## 핵심 기능

- **인물 대화**: 9명의 인물과 8개 주제의 2인 대화
- **인물에게 질문하기**: 한 인물의 관점으로 직접 질문하고 후속 질문하기
- **아고라 매거진**: AI, 창작, 추천 알고리즘 등 동시대 이슈와 인물별 코멘트
- **AI 실시간 생성**: 선택한 인물과 사용자가 입력한 주제로 매번 새로운 대화 생성
- **대화 후 관점 확인**: 대화 전후의 판단 변화를 비교

## 다루는 주제

AI와 일자리, 인간만의 역할, 생성형 AI와 창작, 채용 AI의 공정성, AI 시대의 리더십뿐 아니라 진로 선택, 관계의 거리, 결혼과 자유까지 인간의 삶 전반을 다룹니다.

대화는 역사적 인물의 공개적으로 알려진 사상과 사례를 참고해 구성한 **AI 창작 시뮬레이션**입니다. 실제 발언이나 역사적 기록이 아니며, 인물의 관점을 현재의 질문과 연결한 창작물입니다.

## 로컬 실행

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

실행 후 `http://localhost:8501`에서 확인할 수 있습니다. AI 기능을 사용하려면 OpenRouter API 키가 필요합니다.

API 연동 전 오프라인 버전은 `app_0.py`로 보관되어 있습니다. 오프라인 버전을 실행하려면 다음처럼 파일명을 지정하세요.

```powershell
streamlit run app_0.py
```

## Streamlit Community Cloud 배포

1. GitHub 저장소에 `app.py`, `requirements.txt`, `assets/`를 포함해 push합니다.
2. [Streamlit Community Cloud](https://share.streamlit.io/)에서 **Deploy an app**을 선택합니다.
3. 다음 값을 입력합니다.

```text
Branch: main
Main file path: app.py
```

배포 후 생성되는 `https://<app-name>.streamlit.app` 주소를 서비스 링크로 제출합니다.

앱의 Secrets에 아래 값을 추가합니다. API 키가 없거나 API 요청이 실패하면 하드코딩 답변으로 대체하지 않고 연결 오류만 표시합니다.

```text
OPENROUTER_API_KEY = "..."
OPENROUTER_MODEL = "openai/gpt-4o-mini"
```

OpenRouter API 키는 [OpenRouter](https://openrouter.ai/)에서 발급할 수 있습니다. 무료 모델은 제공량과 rate limit이 변동될 수 있으므로 실제 사용 가능한 `:free` 모델을 선택하세요. 로컬에서는 환경 변수로 설정하고, Streamlit Community Cloud에서는 앱의 Secrets에 등록하세요. 인물에게 질문하기와 대화 결과의 직접 물어보기 모두 자유 입력을 지원하며, API가 연결되면 대화 이력과 함께 OpenRouter에 전달됩니다.

## 추천 시연 순서

1. 입장 페이지에서 **아고라 입장하기**
2. **인물 대화**에서 두 인물과 주제를 선택
3. 대화 전 관점을 고른 뒤 **대화 생성하기**
4. AI가 생성한 12~24턴 대화와 직접 질문 기능 확인
5. 홈으로 돌아가 **인물에게 질문하기**와 **아고라 매거진** 확인

## 기술 스택

- Python
- Streamlit
- Groq API 선택 연동
- 생성형 AI 기반 콘텐츠 큐레이션

## 저작권 및 콘텐츠 안내

인물 이미지는 프로젝트에 포함된 에셋을 사용하며, 역사적 인물에 대한 대화와 매거진 코멘트는 공개 자료를 참고한 창작 콘텐츠입니다. 실제 인물의 발언이나 공식 입장을 대표하지 않습니다.
