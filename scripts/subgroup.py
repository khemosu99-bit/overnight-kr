"""
합리적 부분군 분석 — 부분군 크기 20일 고정 (X̄-R 관리도 방식)

★ 부분군 크기는 데이터 보기 전에 20일로 확정 (사용자 사전 선언)
★ 창 크기 5/10/20/60 비교 → 20이 정말 특별한지 검증
★ 표본 13군의 한계를 명시하고, 과대해석 금지
"""
import pathlib
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
SG = 20                                    # ★ 부분군 크기 (사전 선언)

# ═══ 데이터 ═══
df = pd.read_csv(ROOT / "data" / "night_futures.csv", parse_dates=["date"])
df = df.sort_values("date").reset_index(drop=True)

df["prev_close"] = df["reg_close"].shift(1)
df["night_ret"] = (df["night_close"] / df["prev_close"] - 1) * 100
df["gap"] = (df["reg_open"] / df["prev_close"] - 1) * 100
df["intra"] = (df["reg_close"] / df["reg_open"] - 1) * 100
df["fade"] = (df["reg_close"] / df["night_close"] - 1) * 100
df["full"] = (df["reg_close"] / df["prev_close"] - 1) * 100

d = df.dropna(subset=["night_ret", "gap", "intra", "fade"]).reset_index(drop=True)

# ★ 겹치지 않는 20일 부분군 (뒤에서부터 잘라 최신이 온전하게 남도록)
n = len(d)
d["sg"] = (np.arange(n) - (n % SG)) // SG
d = d[d["sg"] >= 0].copy()                 # 앞의 자투리 제거
d["sg"] = d["sg"].astype(int)


def beta_r2(g):
    if len(g) < 8:
        return np.nan, np.nan, np.nan
    b = np.polyfit(g["night_ret"], g["gap"], 1)
    pred = np.polyval(b, g["night_ret"])
    ss_res = ((g["gap"] - pred) ** 2).sum()
    ss_tot = ((g["gap"] - g["gap"].mean()) ** 2).sum()
    r2 = 1 - ss_res / ss_tot if ss_tot else np.nan
    return b[0], r2, np.sqrt(ss_res / max(len(g) - 2, 1))


print("=" * 84)
print(f"  합리적 부분군 분석  |  부분군 크기 = {SG}일 (사전 선언)")
print(f"  기간 {d['date'].min():%Y-%m-%d} ~ {d['date'].max():%Y-%m-%d}"
      f"  |  {len(d)}일 → {d['sg'].nunique()}개 부분군")
print("=" * 84)
print(f"\n  ⚠️ 부분군 {d['sg'].nunique()}개는 관리도 기준(25개 이상)에 미달합니다.")
print(f"     → 경향 파악용으로만 사용. 이탈점 1개로 결론 내리지 않습니다.")

# ══════════════════════════════════════════════════════
#  【1】 X̄-R 관리도 (20일 부분군)
# ══════════════════════════════════════════════════════
print("\n\n【1】 X̄-R 관리도  (부분군별 특성치)")
print("-" * 84)
print(f"  {'군':>3} {'시작일':<12} {'끝일':<12} {'베타':>7} {'R²':>6} "
      f"{'X̄(fade)':>9} {'R(범위)':>8} {'σ(full)':>8}")
print("  " + "-" * 76)

recs = []
for sg, g in d.groupby("sg"):
    b, r2, _ = beta_r2(g)
    xbar = g["fade"].mean()
    rng = g["fade"].max() - g["fade"].min()
    vol = g["full"].std()
    recs.append(dict(sg=sg, start=g["date"].iloc[0], end=g["date"].iloc[-1],
                     beta=b, r2=r2, xbar=xbar, R=rng, vol=vol, n=len(g)))
    print(f"  {sg:>3} {g['date'].iloc[0]:%Y-%m-%d}  {g['date'].iloc[-1]:%Y-%m-%d} "
          f"{b:>7.3f} {r2:>6.3f} {xbar:>+9.2f} {rng:>8.2f} {vol:>8.2f}")

R = pd.DataFrame(recs)

# ── 관리한계 (n=20 → d2=3.735, A2=0.180, D3=0.415, D4=1.585)
d2, A2, D3, D4 = 3.735, 0.180, 0.415, 1.585
xbb, rbar = R["xbar"].mean(), R["R"].mean()
ucl_x, lcl_x = xbb + A2 * rbar, xbb - A2 * rbar
ucl_r, lcl_r = D4 * rbar, D3 * rbar

print(f"\n  ── X̄ 관리도 (fade) ──")
print(f"     중심선 CL = {xbb:+.3f}")
print(f"     UCL = {ucl_x:+.3f}   LCL = {lcl_x:+.3f}")
oo = R[(R["xbar"] > ucl_x) | (R["xbar"] < lcl_x)]
print(f"     이탈군: {list(zip(oo['sg'], oo['xbar'].round(2))) if len(oo) else '없음 ✅'}")

print(f"\n  ── R 관리도 (산포) ──")
print(f"     R̄ = {rbar:.3f}   UCL = {ucl_r:.3f}   LCL = {lcl_r:.3f}")
ro = R[(R["R"] > ucl_r) | (R["R"] < lcl_r)]
print(f"     이탈군: {list(zip(ro['sg'], ro['R'].round(2))) if len(ro) else '없음 ✅'}")

print(f"\n  ── 베타 안정성 (회귀계수) ──")
bb = R["beta"].dropna()
print(f"     평균 {bb.mean():.3f}  σ {bb.std():.3f}  범위 [{bb.min():.3f}, {bb.max():.3f}]")
print(f"     변동계수 CV = {bb.std()/bb.mean()*100:.1f}%")
print(f"     → {'✅ 베타 안정. 환산기 신뢰 가능' if bb.std()/bb.mean() < 0.15 else '⚠️ 베타 흔들림'}")

# ══════════════════════════════════════════════════════
#  【2】 분산 분해 (군간 vs 군내)  ← 당신의 핵심 질문
# ══════════════════════════════════════════════════════
print("\n\n【2】 분산 분해  ← '통으로 평균내면 오류인가?'")
print("-" * 84)
for tgt in ["fade", "intra", "gap"]:
    grand = d[tgt].mean()
    ss_b = sum(len(g) * (g[tgt].mean() - grand) ** 2 for _, g in d.groupby("sg"))
    ss_w = sum(((g[tgt] - g[tgt].mean()) ** 2).sum() for _, g in d.groupby("sg"))
    k, N = d["sg"].nunique(), len(d)
    F = (ss_b / (k - 1)) / (ss_w / (N - k))
    icc = ss_b / (ss_b + ss_w) * 100      # 군간이 설명하는 비율
    sig = "🚨 군간차 유의" if F > 1.8 else "✅ 군간차 없음"
    print(f"  {tgt:<8} F = {F:>5.2f}   군간 설명력 {icc:>5.1f}%   {sig}")
print(f"\n  → F > 1.8 이면 '국면(regime)이 존재' = 통으로 평균낸 게 오류였음")
print(f"     F < 1.8 이면 '20일 부분군 간 차이 없음' = 통계 오류 아니었음")

# ══════════════════════════════════════════════════════
#  【3】 창 크기 비교  ← 20일이 정말 특별한가?
# ══════════════════════════════════════════════════════
print("\n\n【3】 부분군 크기 비교  ← 20일이 진짜 특별한가?")
print("-" * 84)
print(f"  {'크기':>5} {'군수':>5} {'F(fade)':>9} {'F(intra)':>9} {'베타CV':>8}")
print("  " + "-" * 42)
for sz in [5, 10, 20, 60]:
    tmp = d.copy()
    m = len(tmp)
    tmp["g2"] = (np.arange(m) - (m % sz)) // sz
    tmp = tmp[tmp["g2"] >= 0]
    k = tmp["g2"].nunique()
    if k < 3:
        continue
    out = []
    for tgt in ["fade", "intra"]:
        gm = tmp[tgt].mean()
        sb = sum(len(g) * (g[tgt].mean() - gm) ** 2 for _, g in tmp.groupby("g2"))
        sw = sum(((g[tgt] - g[tgt].mean()) ** 2).sum() for _, g in tmp.groupby("g2"))
        out.append((sb / (k - 1)) / (sw / (len(tmp) - k)))
    bs = [beta_r2(g)[0] for _, g in tmp.groupby("g2")]
    bs = [x for x in bs if not np.isnan(x)]
    cv = np.std(bs) / np.mean(bs) * 100 if bs else np.nan
    star = " ⭐" if sz == 20 else ""
    print(f"  {sz:>5} {k:>5} {out[0]:>9.2f} {out[1]:>9.2f} {cv:>7.1f}%{star}")
print(f"\n  → 20일의 F값이 다른 크기보다 뚜렷이 높으면 → 20일이 실제 의미 있음")
print(f"     비슷비슷하면 → 20일은 특별하지 않음 (그래도 관리도용으론 유효)")

# ══════════════════════════════════════════════════════
#  【4】 이동 20일선 상태변수 (당신이 말한 '20일선')
# ══════════════════════════════════════════════════════
print("\n\n【4】 20일 이동평균선 기준 국면  (상태변수로서의 20일선)")
print("-" * 84)
d["ma20"] = d["reg_close"].rolling(20).mean()
d["rv20"] = d["full"].rolling(20).std()
e = d.dropna(subset=["ma20", "rv20"]).copy()
e["above"] = e["reg_close"] > e["ma20"]

def tt(s):
    s = s.dropna()
    return (s.mean() / (s.std() / np.sqrt(len(s))), len(s)) if len(s) > 15 else (np.nan, len(s))

print(f"  {'국면':<22} {'n':>4} {'fade':>8} {'t':>6} {'intra':>8} {'t':>6} {'베타':>7}")
print("  " + "-" * 66)
for lab, m in [("20일선 위 (상승추세)", e["above"]),
               ("20일선 아래 (하락추세)", ~e["above"]),
               ("고변동 (rv20 상위33%)", e["rv20"] >= e["rv20"].quantile(0.67)),
               ("저변동 (rv20 하위33%)", e["rv20"] <= e["rv20"].quantile(0.33))]:
    g = e[m]
    t1, _ = tt(g["fade"])
    t2, _ = tt(g["intra"])
    b, _, _ = beta_r2(g)
    s1 = "⭐" if abs(t1) >= 2.5 else " "
    s2 = "⭐" if abs(t2) >= 2.5 else " "
    print(f"  {lab:<22} {len(g):>4} {g['fade'].mean():>+8.2f} {t1:>+6.2f}{s1} "
          f"{g['intra'].mean():>+8.2f} {t2:>+6.2f}{s2} {b:>7.3f}")
print(f"\n  ⚠️ 4개 그룹 × 2개 지표 = 8회 검정. 우연히 1개는 ⭐가 뜹니다.")
print(f"     임계값을 2.5로 올렸습니다. 그래도 ⭐ 1개는 신뢰하지 마십시오.")

# ══════════════════════════════════════════════════════
#  【5】 제품용 — 국면별 예측구간
# ══════════════════════════════════════════════════════
print("\n\n【5】 국면별 예측구간  ← 알파와 무관하게 제품에 들어갈 것")
print("-" * 84)
print(f"  {'국면':<22} {'n':>4} {'베타':>7} {'R²':>6} {'80% 예측폭':>12}")
print("  " + "-" * 56)
for lab, m in [("전체", pd.Series(True, index=e.index)),
               ("저변동 국면", e["rv20"] <= e["rv20"].quantile(0.33)),
               ("중변동 국면", (e["rv20"] > e["rv20"].quantile(0.33)) &
                              (e["rv20"] < e["rv20"].quantile(0.67))),
               ("고변동 국면", e["rv20"] >= e["rv20"].quantile(0.67))]:
    g = e[m]
    b, r2, se = beta_r2(g)
    print(f"  {lab:<22} {len(g):>4} {b:>7.3f} {r2:>6.2f}   ±{1.28*se:>6.2f}%p")
print(f"\n  → 국면별 예측폭이 크게 다르면, 사이트에 국면별 오차범위를 표시해야 함")
print(f"     (이게 당신 서브그룹 논리의 가장 확실한 성과입니다)")
