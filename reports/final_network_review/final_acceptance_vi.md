# Kiểm toán cuối P8–P13 và kết quả mạng lưới 2010

## Kết luận

Các phase mở rộng đã tạo được forecast và kết quả thật trên dữ liệu GESLA công khai, nhưng phần lớn là **gauge-only hoặc phương pháp thay thế**. P8 vẫn bị chặn đối với tái lập trực tiếp Bảng 1b. P13 đã bàn giao dashboard HTML và các bảng nhập Power BI; kiểm tra Power BI Desktop vẫn `UI_PENDING`.

Không gộp các kết quả thay thế với kết quả Hibbert. Bài báo định nghĩa sai số là quan trắc trừ surge hindcast và dự báo (Eq. 6), dùng EHM 114 constituents, và báo các số Avonmouth Table 1(b) EHM MAE/RMSE 16.30/19.55 cm và ECM 9.05/11.59 cm. Ở đây không có residual surge phù hợp và chưa chứng minh UTide tương đương EHM; do đó metric dưới đây chỉ đánh giá dự báo tổng mực nước gauge-only. Nguồn bài báo và trích đoạn Table 1: https://livrepository.liverpool.ac.uk/3179635/1/Hibbert_etal_2015.pdf và https://nora.nerc.ac.uk/id/eprint/509610/1/1755876X.2015.1014641_Hibbert.pdf.

## Ma trận nghiệm thu

Chi tiết theo từng phase nằm trong `phase_acceptance_matrix.csv`. Tóm tắt:

| Phase | Việc đã thực hiện | Trạng thái kiểm toán |
|---|---|---|
| P8 | Đánh giá đầu vào paper-aligned Avonmouth; lập inventory và ghi blocker | **BLOCKED** cho khoa học trực tiếp; không có gauge BODC gốc, surge CS3X khớp và baseline EHM xác minh. Báo cáo P8 còn uncommitted trong worktree `/tmp/high-water-forecasting-P8`. |
| P9 | ANN ba seed trên Avonmouth, train 2005 / validation 2006 / held-out 2007 | **Đã chạy, substitute**. Forecast/metric tồn tại; peak n=692, ensemble MAE/RMSE 18.35/42.73 cm. Thuật toán không phải MATLAB Bayesian regularization của bài. |
| P10 | Newlyn-to-Avonmouth species-banded UTide transfer, fit 2006 / test 2007 | **Đã chạy, substitute**. Hourly n=8,759; đỉnh n=704. Không phải SHOM MAS; kết quả đủ cả hai mô hình và được giữ dù transfer kém hơn theo giờ. |
| P11 | Newport UTide/ECM, held-out 2010 | **Đã chạy, gauge-only**. 605 cặp; MAE/RMSE UTide 19.75/24.68 cm và ECM 12.52/16.30 cm. |
| P12 | UTide trên 44/44 cảng; ECM trên 42 cảng | **Đã chạy, gauge-only**. Port Ellen và Bournemouth là `NOT_APPLICABLE_PER_PAPER` do bài nêu multiple highs/lows mỗi ngày. 2010 có 22,267 cặp. Một số vấn đề nhận diện chu kỳ được ghi trong quyết định audit v2, chưa giải quyết. |
| P13 | Dashboard offline, gói CSV Power BI và validator | **Data handoff nghiệm thu; UI_PENDING**. Validator kiểm hash/schema/count/metric, nhưng chưa có PBIX refresh/render/slicer evidence. |

P9–P13 được kiểm theo acceptance docs tương ứng: `reports/acceptance/P9.md`–`P13.md`. P8 evidence là file trong worktree riêng, chưa commit: `/tmp/high-water-forecasting-P8/reports/acceptance/P8.md`, `reports/p8/input_inventory.csv`. `reports/access_decision.md` ghi riêng quyết định gauge-only và sự thiếu dữ liệu direct Table 1b.

## ECM theo từng cảng, held-out 2010

Phân tích tái tính từ `reports/network_2010/network_forecasts_paired.parquet`, không dùng các giá trị MAE đã làm tròn. Chỉ lọc `period=heldout_2010`, target `total_observed_water_level_gauge_only`, rồi ghép cùng hàng/cycle theo khóa `(station_id, cycle_id)`. Mỗi hàng nguồn đã có H, UTide A và ECM forecast cùng forecast origin; kiểm tra không có khóa trùng và chỉ giữ hàng có đủ cả ba giá trị. Có 23,377 cycle ứng viên, trong đó 22,267 cặp đầy đủ ở 42 cảng. Hai cảng loại khỏi mẫu số là Port Ellen và Bournemouth vì ECM không áp dụng theo bài.

Mỗi cảng trong 42 cảng có `gain_mae_cm = MAE_UTide − MAE_ECM > 0` khi so sánh float64 chưa làm tròn: **42 cải thiện, 0 bằng, 0 xấu đi; 100% số cảng được chấm cải thiện**. Không dùng dung sai hòa. Trung vị mức giảm MAE giữa cảng là **2.6184 cm**. Ở cấp từng cặp đỉnh, **14,204/22,267 (63.79%)** có sai số tuyệt đối ECM nhỏ hơn, 8,063 lớn hơn và 0 bằng. Tỷ lệ cảng cải thiện vì vậy khác tỷ lệ đỉnh cải thiện.

| Mốc | UTide | ECM | ECM giảm |
|---|---:|---:|---:|
| Pooled MAE, cm | 12.7069 | 9.7117 | 2.9952 |
| Pooled RMSE, cm | 16.9304 | 13.1564 | 3.7740 |
| Cặp đỉnh | 22,267 | 22,267 | — |

Metric pooled được tính trực tiếp trên 22,267 cặp; không lấy trung bình các metric cấp cảng. Kết quả khớp validator P13 trong sai số dưới `1e-8 cm`.

Portbury có mức giảm MAE lớn nhất: **8.4575 cm** trên 637 đỉnh; tiếp theo Newport **7.0340 cm / 605 đỉnh** và Avonmouth **7.0139 cm / 645 đỉnh**. Mức thấp nhất vẫn dương là Whitby **0.1589 cm / 357 đỉnh**. Không có cảng nào xấu đi theo MAE. Không diễn giải các số này thành cải thiện dự báo surge hoặc tái lập Table 2: target là tổng H gauge-only, UTide thay EHM, dữ liệu kênh/datum gốc chưa xác minh.

Chi tiết 42 hàng: `station_metrics_2010.csv`. Số liệu cấp từng đỉnh: `paired_event_gains_2010.csv`. Hình ngang đầy đủ: `ecm_mae_gain_by_port_2010.png`. Mã tái chạy: `scripts/final_network_review.py`.

## Git và kiểm tra

- Điểm bắt đầu được xác minh: P12 `911fcee77a626b0f82b0fcdbdc4530b69679b6c6`; P13 `5ac4d5cc437e8ef7993efcf03d37f9a3017fa11b`, parent là P12; `main` `e6deb2b04ef28b1d5e42258b128f2f53d8f78882`.
- Nhánh audit tạo từ P13: `audit/final-network-results`; không checkout/chỉnh main, không push. Worktree P7 bẩn và P8 riêng được giữ nguyên.
- P12 artifact hashes: forecast Parquet `01126f1852eaf3961d6d4ce9adb6cdfb5fb41e6f71e8f0ee10b5db8f8a21ba1d`, metric CSV `3a0ff3932607cc2f1f80838eb8f71b8e9c3ed5d9901274fed829725cdc5162b7`. Summary JSON ghi hai hash đầu vào và toàn bộ mốc kiểm toán.

## Tái chạy

```bash
MPLCONFIGDIR=/tmp/mpl-cache PYTHONPATH=src /home/khang/Code/data-pipeline/high-water-forecasting/.venv/bin/python scripts/final_network_review.py
PYTHONPATH=src /home/khang/Code/data-pipeline/high-water-forecasting/.venv/bin/python scripts/validate_network_dashboard.py
PYTHONPATH=src /home/khang/Code/data-pipeline/high-water-forecasting/.venv/bin/python -m pytest -q
```

`network_summary_2010.json` lưu bộ lọc, khóa ghép, số lượng, phân loại và kết quả pooled. Validator P13 tái kiểm tra HTML, CSV handoff và mốc pooled. Trong lượt này validator trả `PASS`; full test suite trả **31 passed**. `git diff --check` và `git diff --cached --check` đạt; `main` vẫn ở SHA ban đầu. Lần tạo script đầu tiên phát hiện các hàng cycle ứng viên không forecast được có origin null; phép kiểm tra được giới hạn đúng vào các cặp có đủ dự báo, rồi toàn bộ 22,267 origin/target của cặp hợp lệ được xác nhận hiện diện. Không thay đổi dữ liệu đầu vào.
