# D3 粒度不等价风险对（20 对）——确认丢失/改变的语义约束

每对判定：compact 是否丢失了 unrolled 中的实质语义约束（年度过滤/时相条件/逐年求和/最终平均）？裁定：semantic_loss_confirmed / actually_equivalent / needs_full_dag

| # | unrolled 阶段 | compact 阶段 | famJ | U 标题 | C 标题 | 裁定 | 丢失的约束 |
|---|---|---|---|---|---|---|---|
| 1 | 53 | 8 | 1.0 | Map land surface in Madre de Dios | Classify land cover types | ______ | ______ |
| 2 | 12 | 8 | 1.0 | Estimate land surface temperature | Classify land cover types | ______ | ______ |
| 3 | 14 | 8 | 1.0 | Analyze NDVI time series | Classify land cover types | ______ | ______ |
| 4 | 1473 | 5 | 1.0 | Estimate maximum water flux | Extract snow cover samples | ______ | ______ |
| 5 | 45 | 5 | 1.0 | Analyze daily precipitation patterns | Extract snow cover samples | ______ | ______ |
| 6 | 1473 | 5 | 1.0 | Model soil water erosion potential | Extract snow cover samples | ______ | ______ |
| 7 | 19 | 4 | 1.0 | Analyze NDVI time series for forest types | Analyze vegetation trends | ______ | ______ |
| 8 | 81 | 4 | 1.0 | Analyze NDVI trends over time | Analyze vegetation trends | ______ | ______ |
| 9 | 10 | 6 | 1.0 | Analyze urban light trends | Model NDVI time series with harmonic regression | ______ | ______ |
| 10 | 12 | 13 | 1.0 | Analyze land surface temperature | Calculate potential productivity | ______ | ______ |
| 11 | 13 | 13 | 1.0 | Assess desertification risk using ISD index | Calculate potential productivity | ______ | ______ |
| 12 | 12 | 13 | 1.0 | Analyze tree cover change | Calculate potential productivity | ______ | ______ |
| 13 | 100 | 12 | 1.0 | Map seasonal land cover | Estimate land surface temperature | ______ | ______ |
| 14 | 100 | 12 | 1.0 | Map seasonal land cover changes | Estimate land surface temperature | ______ | ______ |
| 15 | 24 | 12 | 1.0 | Analyze surface reflectance trends | Estimate land surface temperature | ______ | ______ |
| 16 | 29 | 5 | 1.0 | Compare land cover change | Extract monthly NDVI time series | ______ | ______ |
| 17 | 30 | 5 | 1.0 | Map land surface changes | Extract monthly NDVI time series | ______ | ______ |
| 18 | 16 | 5 | 1.0 | Extract seasonal land cover | Extract monthly NDVI time series | ______ | ______ |
| 19 | 29 | 13 | 1.0 | Compare land cover change | Analyze NDVI and LAI time series | ______ | ______ |
| 20 | 30 | 13 | 1.0 | Map land surface changes | Analyze NDVI and LAI time series | ______ | ______ |