"""
야간→정규 최종 분석
- 265일 전수 검증
- 검증/시험 분할로 과최적화 확인
"""
import pathlib
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
df = pd.read_csv(ROOT / "data" / "night_futures.csv", parse_dates=["date"])
df = df.sort_values("date").reset_index(drop=True)

# ── 지표 계산 ──────────────────────────────
df["prev_close"] = df["reg_close"].shift(1)          # 전일 정규 종가
df["night_ret"] = (df["night_close"] / df["prev_close"] - 1) * 100   # 야간 등락
df["gap"] = (df["reg_open"] / df["prev_close"] - 1) * 100            # 개장 갭
df["intra"] = (df["reg_close"] / df["reg_open"] - 1) * 100           # 장중
df["full"] = (df["reg_close"] / df["prev_close"] - 1) * 100          # 하루 전체
df["fade"] = (df["reg_close"] / df["night_close"] - 1) * 100         # 야간→종가
df["capture"] = df["gap"] / df["night_ret"]          # 야간등락 중 갭에 반영된 비율

d = df.dropna(subset=["night_ret", "gap", "intra"]).copy()


def t(s):
    s = s.dropna()
    if len(s) < 10:
        return np.nan, len(s)
    return s.mean() / (s.std() / np.sqrt(len(s))), len(s)


def show(label, s):
    tv, n = t(s)
    if np.isnan(tv):
        print(f"    {label:<28} 표본부족({n})")
        return
    up = (s.dropna() > 0).mean() * 100
    m = "⭐" if abs(tv) >= 2 else "  "
    print(f"    {label:<28} {n:>4}일 | 평균 {s.mean():>+6.2f}% | "
          f"양(+) {up:>5.1f}% | t={tv:>+6.2f} {m}")


print("=" * 78)
print(f"  KRX 야간선물 분석  |  {d['date'].min():%Y-%m-%d} ~ {d['date'].max():%Y-%m-%d}"
      f"  ({len(d)}일)")
print("=" * 78)

# ══ 1. 핵심 가설: 야간 프리미엄은 소멸하는가 ══
print("\n  【1】 야간→정규종가 소멸 (fade)   ← 핵심 가설")
show("전체", d["fade"])
show("야간 상승일", d[d["night_ret"] > 0]["fade"])
show("야간 하락일", d[d["night_ret"] < 0]["fade"])
show("야간 +1% 이상", d[d["night_ret"] >= 1]["fade"])
show("야간 -1% 이하", d[d["night_ret"] <= -1]["fade"])

# ══ 2. 갭은 지켜지는가 ══
print("\n  【2】 갭 방향별 장중 흐름   ← '갭은 지켜지지 않는다'")
show("전체 장중", d["intra"])
show("갭상승일의 장중", d[d["gap"] > 0]["intra"])
show("갭하락일의 장중", d[d["gap"] < 0]["intra"])
show("갭 +1% 이상의 장중", d[d["gap"] >= 1]["intra"])
show("갭 -1% 이하의 장중", d[d["gap"] <= -1]["intra"])

# ══ 3. 야간이 갭을 얼마나 예고하나 ══
print("\n  【3】 야간 등락 → 개장 갭 예고력")
c = d[["night_ret", "gap"]].corr().iloc[0, 1]
b = np.polyfit(d["night_ret"], d["gap"], 1)
print(f"    상관계수         {c:>+6.3f}   (1.0에 가까울수록 강함)")
print(f"    회귀식           갭 = {b[0]:.3f} × 야간등락 {b[1]:+.3f}")
print(f"    설명력(R²)       {c**2*100:>5.1f}%")
same = ((d["night_ret"] > 0) == (d["gap"] > 0)).mean() * 100
print(f"    방향 일치율      {same:>5.1f}%")
cap = d[d["night_ret"].abs() >= 0.5]["capture"].median()
print(f"    갭 반영률(중앙값) {cap*100:>5.1f}%   ← 야간 등락의 몇 %가 갭에 반영되나")

# ══ 4. 과최적화 검증 ══
print("\n  【4】 과최적화 검증 (앞 60% 학습 / 뒤 40% 시험)")
cut = d["date"].quantile(0.6)
for lab, sub in [("학습(앞60%)", d[d["date"] <= cut]),
                 ("시험(뒤40%)", d[d["date"] > cut])]:
    print(f"\n    ── {lab}  ({sub['date'].min():%Y-%m} ~ {sub['date'].max():%Y-%m}) ──")
    show("  야간→종가 소멸", sub["fade"])
    show("  갭상승일 장중", sub[sub["gap"] > 0]["intra"])

# ══ 5. 실전 문장 (사이트에 쓸 것) ══
print("\n\n" + "=" * 78)
print("  【5】 사이트에 쓸 문장 (자동 생성 예시)")
print("=" * 78)
for lo, hi, lab in [(1, 99, "야간선물 +1% 이상 상승"),
                    (-99, -1, "야간선물 -1% 이하 하락")]:
    s = d[d["night_ret"].between(lo, hi)]
    if len(s) < 10:
        continue
    print(f"\n  ▶ [{lab}] 한 경우 (과거 {len(s)}회)")
    print(f"     · 개장 갭      평균 {s['gap'].mean():+.2f}%  "
          f"(같은 방향 {((s['gap']>0)==(lo>0)).mean()*100:.0f}%)")
    print(f"     · 장중 흐름    평균 {s['intra'].mean():+.2f}%")
    print(f"     · 하루 전체    평균 {s['full'].mean():+.2f}%")
    print(f"     · 야간→종가    평균 {s['fade'].mean():+.2f}%  ← 야간 가격 대비")
