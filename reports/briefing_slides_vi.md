# Slide 1 — Avonmouth: dự báo đỉnh triều

- Pilot gauge-only tái lập quy trình theo Hibbert et al. (2015).
- Dữ liệu GESLA S3, lineage BODC; checksum nguồn được ghi trong manifest.
- 2007: 35.040 mẫu 15 phút, 8.759 giờ hợp lệ, 705 chu kỳ đỉnh.
- Hình: `reports/figures/avonmouth_2007_first_14_days_raw_vs_hourly.png`.

# Slide 2 — Thiết kế dự báo

- Baseline điều hòa UTide, 68 thành phần; dữ liệu QC thiếu không được lấp.
- ECM OLS dùng residual gauge-only ở các đỉnh N−2, N−4, N−6.
- Chronological: harmonic fit đến 2004; ECM train 2005; validation 2006; test 2007.
- Transfer: baseline fit đến 2009, ECM train 2009, test 2010.
- Lead cấu hình 24 giờ; latency nguồn không biết.

# Slide 3 — Kết quả chính

| Tập | Baseline MAE/RMSE (cm) | ECM MAE/RMSE (cm) | n |
|---|---:|---:|---:|
| 2006 validation | 23,92 / 31,03 | 15,83 / 21,50 | 650 |
| 2007 test | 25,34 / 31,82 | 16,29 / 22,23 | 701 |
| 2010 transfer | 21,86 / 27,37 | 14,63 / 18,72 | 645 |

- 2007 hồi cứu (in-sample): baseline 25,21/31,62; ECM 16,28/21,82 cm, n=701.
- Hình: `data/clean/p5_gauge_only_evaluation/chronological_fit_through_2004/paired_error_histogram.png`.

# Slide 4 — Ví dụ đỉnh và Power BI handoff

- 01-01-2007 05:00 UTC: H=11,604 m; baseline sai số +2,07 cm; ECM +4,66 cm.
- Forecast phát hành lúc 31-12-2006 05:00 UTC; ba lag và correction được lưu để drill-through.
- CSV/Parquet star schema cùng DAX, Power Query và bốn trang đặc tả đã được kiểm bằng Python.
- Power BI Desktop UI vẫn `UI_PENDING`.

# Slide 5 — Kết luận và dữ liệu còn thiếu

- Kết quả là gauge-only total H; không so delta trực tiếp với Table 1b.
- Surge CS3X 2007 và ánh xạ lưới chưa có; không dùng H−A làm surge.
- Datum/kênh gauge gốc chưa xác định.
- Cần metadata/tệp BODC gốc, residual surge hindcast theo giờ và Power BI Desktop để hoàn thiện các phần tương ứng.
