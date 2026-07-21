import streamlit as st
import pandas as pd
import requests
import plotly.express as px

st.set_page_config(page_title="전국 고령화 단계구분도", layout="wide")

POP_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
GEO_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
TARGET_YEAR = 2026


@st.cache_data
def load_population():
    df = pd.read_csv(POP_URL, dtype={"코드": str})
    df = df[df["연도"] == TARGET_YEAR].copy()
    return df


@st.cache_data
def load_geojson():
    res = requests.get(GEO_URL)
    res.raise_for_status()
    return res.json()


def parse_age(col: str) -> int:
    # '계_0세' -> 0, '계_100세 이상' -> 100
    s = col[len("계_"):]
    s = s.replace("세 이상", "").replace("세", "")
    return int(s)


@st.cache_data
def compute_ratio(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["시군구코드"] = df["코드"].astype(str).str[:5]

    total_cols = [c for c in df.columns if c.startswith("계_")]
    elderly_cols = [c for c in total_cols if parse_age(c) >= 65]

    df["전체인구"] = df[total_cols].sum(axis=1)
    df["고령인구"] = df[elderly_cols].sum(axis=1)

    grouped = df.groupby("시군구코드", as_index=False)[["전체인구", "고령인구"]].sum()
    grouped["고령화율"] = (grouped["고령인구"] / grouped["전체인구"] * 100).round(2)

    return grouped


def build_name_maps(geojson: dict):
    sigungu_map = {}
    sido_map = {}
    for feat in geojson["features"]:
        props = feat["properties"]
        code = str(props.get("코드"))
        sigungu_map[code] = props.get("시군구")
        sido_map[code] = props.get("시도")
    return sigungu_map, sido_map


def main():
    st.title("전국 고령화 단계구분도")
    st.caption(f"{TARGET_YEAR}년 6월 기준, 시군구별 65세 이상 인구 비율")

    with st.spinner("데이터를 불러오는 중입니다..."):
        pop_df = load_population()
        geojson = load_geojson()

    ratio_df = compute_ratio(pop_df)

    sigungu_map, sido_map = build_name_maps(geojson)
    ratio_df["시군구"] = ratio_df["시군구코드"].map(sigungu_map)
    ratio_df["시도"] = ratio_df["시군구코드"].map(sido_map)

    # 경계 파일에 없는 코드는 지도에 그릴 수 없으므로 제외
    ratio_df = ratio_df.dropna(subset=["시군구"])

    fig = px.choropleth(
        ratio_df,
        geojson=geojson,
        locations="시군구코드",
        featureidkey="properties.코드",
        color="고령화율",
        color_continuous_scale="Reds",
        hover_name="시군구",
        hover_data={"시군구코드": False, "고령화율": ":.2f"},
        labels={"고령화율": "고령화율(%)"},
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=750,
        coloraxis_colorbar=dict(title="고령화율(%)"),
    )

    st.plotly_chart(fig, use_container_width=True)

    with st.expander("데이터 표 보기"):
        st.dataframe(
            ratio_df[["시도", "시군구", "시군구코드", "전체인구", "고령인구", "고령화율"]]
            .sort_values("고령화율", ascending=False)
            .reset_index(drop=True)
        )


if __name__ == "__main__":
    main()
