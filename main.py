import requests
import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# 기본 설정
# ---------------------------------------------------------

# 웹페이지 제목과 화면 아이콘을 설정합니다.
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 어제의 박스오피스")
st.caption("KOBIS 영화관입장권통합전산망 · 한국 시간 기준")


# ---------------------------------------------------------
# 날짜 계산
# ---------------------------------------------------------

# 배포 서버가 어느 나라 시간으로 설정되어 있는지와 관계없이
# 한국 시간(KST)을 기준으로 오늘 날짜를 구합니다.
kst = ZoneInfo("Asia/Seoul")
today_kst = datetime.now(kst).date()

# KOBIS에는 오늘 데이터가 아직 집계 중이므로 어제를 조회합니다.
target_date = today_kst - timedelta(days=1)

# KOBIS API가 요구하는 날짜 형식: yyyymmdd
target_dt = target_date.strftime("%Y%m%d")

# 사람이 읽기 좋은 날짜도 준비합니다.
target_date_text = target_date.strftime("%Y년 %m월 %d일")


# ---------------------------------------------------------
# KOBIS API 호출
# ---------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def get_box_office(target_dt):
    """
    KOBIS 일별 박스오피스 API를 호출합니다.

    ttl=3600:
    같은 날짜를 다시 조회할 경우 약 1시간 동안
    캐시에 저장된 결과를 사용합니다.
    """

    # Streamlit Cloud의 Secrets에서 인증키를 읽습니다.
    # 실제 인증키는 코드에 넣지 않습니다.
    api_key = st.secrets["KOBIS_KEY"]

    url = (
        "https://www.kobis.or.kr/"
        "kobisopenapi/webservice/rest/boxoffice/"
        "searchDailyBoxOfficeList.json"
    )

    params = {
        "key": api_key,
        "targetDt": target_dt,
    }

    # API에 요청합니다.
    response = requests.get(url, params=params, timeout=10)

    # HTTP 오류가 있으면 예외를 발생시킵니다.
    response.raise_for_status()

    # JSON 응답으로 변환합니다.
    data = response.json()

    return data


# ---------------------------------------------------------
# API 결과 확인
# ---------------------------------------------------------

try:
    data = get_box_office(target_dt)

except KeyError:
    # st.secrets에 KOBIS_KEY가 없을 때 발생합니다.
    st.error(
        "KOBIS 인증키를 찾을 수 없습니다.\n\n"
        "Streamlit Cloud의 앱 설정에서 Secrets를 열고 "
        "`KOBIS_KEY`라는 이름으로 인증키를 등록했는지 확인하세요."
    )
    st.stop()

except requests.exceptions.RequestException as e:
    # 인터넷 연결, KOBIS 서버, 요청 시간 초과 등의 오류입니다.
    st.error(
        "KOBIS API를 호출하지 못했습니다.\n\n"
        "다음 사항을 확인해 주세요:\n"
        "- KOBIS API 서버가 정상적으로 응답하는지\n"
        "- 인터넷 연결이 가능한지\n"
        "- 인증키가 올바른지\n"
        "- 잠시 후 다시 시도해도 같은 문제가 발생하는지\n\n"
        f"오류 내용: {e}"
    )
    st.stop()

except Exception as e:
    # 예상하지 못한 오류도 빈 화면으로 끝나지 않도록 안내합니다.
    st.error(
        "박스오피스 데이터를 가져오는 중 문제가 발생했습니다.\n\n"
        "KOBIS 인증키와 API 응답 상태를 확인한 뒤 다시 시도해 주세요.\n\n"
        f"오류 내용: {e}"
    )
    st.stop()


# ---------------------------------------------------------
# KOBIS가 반환한 오류(faultInfo) 확인
# ---------------------------------------------------------

# KOBIS는 인증키가 잘못된 경우에도 HTTP 상태코드 200을
# 반환할 수 있으므로 faultInfo를 직접 확인해야 합니다.
fault_info = data.get("faultInfo")

if fault_info:
    fault_code = fault_info.get("faultCode", "알 수 없음")
    fault_message = fault_info.get("message", "알 수 없는 오류")

    st.error(
        "KOBIS API에서 오류를 반환했습니다.\n\n"
        f"- 오류 코드: {fault_code}\n"
        f"- 오류 메시지: {fault_message}\n\n"
        "KOBIS 인증키가 정확한지, 인증키가 활성화되어 있는지, "
        "Secrets의 이름이 `KOBIS_KEY`인지 확인해 주세요."
    )
    st.stop()


# ---------------------------------------------------------
# 영화 목록 가져오기
# ---------------------------------------------------------

box_office_result = data.get("boxOfficeResult", {})
movie_list = box_office_result.get("dailyBoxOfficeList", [])


# 영화 목록이 없는 경우 안내합니다.
if not movie_list:
    st.warning(
        f"{target_date_text}의 박스오피스 영화 목록이 없습니다.\n\n"
        "다음 사항을 확인해 주세요:\n"
        "- KOBIS에서 해당 날짜의 일별 박스오피스 데이터가 집계되었는지\n"
        "- 조회 날짜가 정상적으로 계산되었는지\n"
        "- KOBIS API가 정상적으로 데이터를 제공하고 있는지\n"
        "- 잠시 후 다시 실행해 보세요."
    )
    st.stop()


# ---------------------------------------------------------
# 문자열 숫자를 실제 숫자로 변환
# ---------------------------------------------------------

def to_int(value):
    """
    KOBIS가 문자열로 보내는 숫자를 정수로 바꿉니다.

    예:
    "12,345" -> 12345
    "12345"  -> 12345
    빈 값    -> 0
    """
    if value is None:
        return 0

    text = str(value).replace(",", "").strip()

    if not text:
        return 0

    try:
        return int(text)
    except ValueError:
        return 0


# KOBIS 응답을 화면에서 사용하기 편한 형태로 정리합니다.
movies = []

for movie in movie_list:
    movies.append(
        {
            "순위": to_int(movie.get("rank")),
            "영화명": movie.get("movieNm", ""),
            "개봉일": movie.get("openDt", ""),
            "관객수": to_int(movie.get("audiCnt")),
            "누적관객": to_int(movie.get("audiAcc")),
            "스크린수": to_int(movie.get("scrnCnt")),
        }
    )


# 순위를 숫자로 정렬합니다.
movies.sort(key=lambda movie: movie["순위"])


# ---------------------------------------------------------
# 1위 영화
# ---------------------------------------------------------

first_movie = movies[0]

st.subheader(f"🥇 1위 · {first_movie['영화명']}")

# 1위 영화의 핵심 지표 세 가지를 크게 보여줍니다.
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "어제 관객수",
        f"{first_movie['관객수']:,}명",
    )

with col2:
    st.metric(
        "누적 관객수",
        f"{first_movie['누적관객']:,}명",
    )

with col3:
    st.metric(
        "스크린수",
        f"{first_movie['스크린수']:,}개",
    )


# ---------------------------------------------------------
# 관객수 상위 5편 막대그래프
# ---------------------------------------------------------

st.subheader("📊 관객수 상위 5편")

# 영화 목록을 관객수 기준으로 내림차순 정렬합니다.
top_5 = sorted(
    movies,
    key=lambda movie: movie["관객수"],
    reverse=True,
)[:5]

# Streamlit의 기본 bar chart를 사용하기 쉽도록
# 영화명을 인덱스로 하는 딕셔너리를 만듭니다.
chart_data = {
    movie["영화명"]: movie["관객수"]
    for movie in top_5
}

st.bar_chart(chart_data, y_label="관객수(명)")


# ---------------------------------------------------------
# 전체 박스오피스 표
# ---------------------------------------------------------

st.subheader(f"📋 {target_date_text} 일별 박스오피스")

# 표에 표시할 열 순서를 지정합니다.
table_data = [
    {
        "순위": movie["순위"],
        "영화명": movie["영화명"],
        "개봉일": movie["개봉일"],
        "관객수": movie["관객수"],
        "누적관객": movie["누적관객"],
        "스크린수": movie["스크린수"],
    }
    for movie in movies
]

st.dataframe(
    table_data,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn(
            "순위",
            format="%d",
        ),
        "영화명": st.column_config.TextColumn(
            "영화명",
        ),
        "개봉일": st.column_config.TextColumn(
            "개봉일",
        ),
        "관객수": st.column_config.NumberColumn(
            "관객수",
            format="%d",
        ),
        "누적관객": st.column_config.NumberColumn(
            "누적관객",
            format="%d",
        ),
        "스크린수": st.column_config.NumberColumn(
            "스크린수",
            format="%d",
        ),
    },
)

st.caption(
    f"조회 날짜: {target_dt} · 한국 시간(KST) 기준 어제 · "
    "KOBIS API 응답은 약 1시간 동안 캐시됩니다."
)
