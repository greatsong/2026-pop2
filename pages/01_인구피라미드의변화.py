# -------------------------------------------------
# 동네별 인구 피라미드 (연도 애니메이션 버전)
# -------------------------------------------------
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="동네별 인구 피라미드 (연도 애니메이션)", page_icon="🏘️", layout="wide")

# -------------------------------------------------
# 1. 데이터 불러오기 (한 번만 다운로드하도록 캐시)
# -------------------------------------------------
@st.cache_data(show_spinner="데이터를 불러오는 중이에요...")
def load_data():
    url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    df = pd.read_csv(url, compression="gzip")
    return df

df = load_data()

st.title("🏘️ 동네별 인구 피라미드 (2015~2026 애니메이션)")

# -------------------------------------------------
# 2. 시도 → 시군구 → 동 선택 (전체 연도 기준으로 목록 생성)
# -------------------------------------------------
col1, col2, col3 = st.columns(3)

with col1:
    sido = st.selectbox("시도 선택", sorted(df["시도"].dropna().unique()))
with col2:
    sub = df[df["시도"] == sido]
    sigungu = st.selectbox("시군구 선택", sorted(sub["시군구"].dropna().unique()))
with col3:
    sub2 = sub[sub["시군구"] == sigungu]
    dong = st.selectbox("동 선택", sorted(sub2["동"].dropna().unique()))

# 선택한 동네의 전체 연도 데이터만 남기기
loc_df = df[(df["시도"] == sido) & (df["시군구"] == sigungu) & (df["동"] == dong)].copy()
loc_df = loc_df.sort_values("연도")
years = sorted(loc_df["연도"].unique())  # 보통 2015~2026

if loc_df.empty:
    st.warning("데이터가 없어요. 다른 동네를 선택해보세요.")
    st.stop()

# -------------------------------------------------
# 3. 나이 순서 고정 (0세 ~ 100세 이상, 이 순서가 곧 세로축 순서)
# -------------------------------------------------
ages = [f"{i}세" for i in range(100)] + ["100세 이상"]
age_num = list(range(101))  # 나이를 숫자로도 다뤄야 평균/중앙값 계산 가능 (100세 이상은 100으로 취급)

# -------------------------------------------------
# 4. 연도별 남/여 인구 배열 미리 계산
# -------------------------------------------------
def get_values(row):
    male = np.array([row.get(f"남_{a}", 0) for a in ages], dtype=float)
    female = np.array([row.get(f"여_{a}", 0) for a in ages], dtype=float)
    return male, female

year_data = {}  # {연도: (남자배열, 여자배열)}
for _, row in loc_df.iterrows():
    year_data[row["연도"]] = get_values(row)

# 가로축 폭 고정을 위해, 모든 연도 중 최댓값 찾기
max_val = 0
for m, f in year_data.values():
    max_val = max(max_val, m.max(), f.max())
max_val = max_val * 1.1  # 여유 있게 10% 더 크게

# -------------------------------------------------
# 5. 애니메이션용 Figure 만들기 (frames = 연도별 스냅샷)
# -------------------------------------------------
first_year = years[0]
male0, female0 = year_data[first_year]

fig = go.Figure(
    data=[
        go.Bar(y=ages, x=-male0, name="남자", orientation="h", marker_color="#6FA3D9"),
        go.Bar(y=ages, x=female0, name="여자", orientation="h", marker_color="#F4978E"),
    ],
    layout=go.Layout(
        title=f"{sido} {sigungu} {dong} 인구 피라미드 - {first_year}년",
        barmode="overlay",
        bargap=0.1,
        plot_bgcolor="#FFFBF5",
        paper_bgcolor="#FFFBF5",
        xaxis=dict(range=[-max_val, max_val], title="인구 수 (명)",  # 가로축 폭 고정!
                   tickvals=[-max_val, -max_val / 2, 0, max_val / 2, max_val],
                   ticktext=[f"{abs(v):,.0f}" for v in [-max_val, -max_val / 2, 0, max_val / 2, max_val]]),  # 눈금은 절댓값으로
        yaxis=dict(title="나이", categoryorder="array", categoryarray=ages),  # 0세가 맨 아래
        legend_title="성별",
        updatemenus=[{
            "type": "buttons",
            "buttons": [
                {"label": "▶ 재생", "method": "animate",
                 "args": [None, {"frame": {"duration": 700, "redraw": True}, "fromcurrent": True}]},
                {"label": "⏸ 정지", "method": "animate",
                 "args": [[None], {"frame": {"duration": 0}, "mode": "immediate"}]},
            ],
        }],
        sliders=[{
            "steps": [
                {"label": str(y), "method": "animate",
                 "args": [[str(y)], {"frame": {"duration": 700, "redraw": True}, "mode": "immediate"}]}
                for y in years
            ],
        }],
    ),
    frames=[
        go.Frame(
            name=str(y),
            data=[
                go.Bar(x=-year_data[y][0]),
                go.Bar(x=year_data[y][1]),
            ],
            layout=go.Layout(title=f"{sido} {sigungu} {dong} 인구 피라미드 - {y}년"),
        )
        for y in years
    ],
)

st.plotly_chart(fig, use_container_width=True)

# -------------------------------------------------
# 6. 연도별 평균 연령 / 중앙값 연령 계산
# -------------------------------------------------
def weighted_median(values, weights):
    # 가중치(인구수)를 반영한 중앙값 계산
    order = np.argsort(values)
    values, weights = np.array(values)[order], np.array(weights)[order]
    cum = np.cumsum(weights)
    half = cum[-1] / 2
    return values[np.searchsorted(cum, half)]

mean_ages, median_ages = [], []
for y in years:
    male, female = year_data[y]
    total = male + female  # 남녀 합친 나이별 인구수
    mean_ages.append(np.sum(np.array(age_num) * total) / total.sum())
    median_ages.append(weighted_median(age_num, total))

# -------------------------------------------------
# 7. 평균/중앙값 연령 변화 꺾은선 그래프
# -------------------------------------------------
line_fig = go.Figure()
line_fig.add_trace(go.Scatter(x=years, y=mean_ages, mode="lines+markers",
                               name="평균 연령", line=dict(color="#E07A5F", width=3)))
line_fig.add_trace(go.Scatter(x=years, y=median_ages, mode="lines+markers",
                               name="중앙값 연령", line=dict(color="#3D405B", width=3)))
line_fig.update_layout(
    title=f"{sido} {sigungu} {dong} 평균·중앙값 연령 변화 (2015~2026)",
    xaxis_title="연도", yaxis_title="나이",
    plot_bgcolor="#FFFBF5", paper_bgcolor="#FFFBF5",
)

st.plotly_chart(line_fig, use_container_width=True)

st.info("✅ 슬라이더나 ▶ 재생 버튼으로 연도를 바꿔가며 인구 구조 변화를 확인해보세요!")
