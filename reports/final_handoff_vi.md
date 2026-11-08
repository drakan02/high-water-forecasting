# Bàn giao dự án — dự báo đỉnh triều Avonmouth

## Phạm vi đã hoàn tất

Các phase P0–P7 đã được thực hiện trên các nhánh riêng và nghiệm thu theo phạm vi dữ liệu gauge-only. Dự án dùng chuỗi GESLA S3 mang lineage BODC cho Avonmouth; SHA-256 nguồn là `7a796fcb64215becd2fb429b75a48be5afcb392c613a7f54e509c36250e71bb8`. Tệp nguồn giữ nguyên.

Năm 2007 có 35.040 mẫu 15 phút. Quy tắc P1 giữ mẫu đúng phút 00 UTC; 8.760 timestamp giờ hiện diện, 8.759 giờ hợp lệ và một giờ bị loại theo QC. P3 tìm được 705 chu kỳ triều cao; 704 chu kỳ có đủ coverage gauge, một chu kỳ bị loại do khoảng trống dữ liệu. Không nội suy khoảng trống.

## Kết quả dự báo

| Tập | Mô hình | n cặp | MAE (cm) | RMSE (cm) | Cách diễn giải |
|---|---|---:|---:|---:|---|
| 2006 validation | Điều hòa UTide | 650 | 23,92 | 31,03 | Kiểm định theo thời gian |
| 2006 validation | ECM gauge-only | 650 | 15,83 | 21,50 | ECM OLS fit trên 636 đỉnh năm 2005 |
| 2007 test | Điều hòa UTide | 701 | 25,34 | 31,82 | Fit điều hòa chỉ đến hết 2004 |
| 2007 test | ECM gauge-only | 701 | 16,29 | 22,23 | Dự báo phát hành trước 24 giờ |
| 2007 hồi cứu | Điều hòa UTide | 701 | 25,21 | 31,62 | Fit hồi cứu/in-sample |
| 2007 hồi cứu | ECM gauge-only | 701 | 16,28 | 21,82 | Fit và chấm cùng năm; không phải backtest |
| 2010 transfer | Điều hòa UTide | 645 | 21,86 | 27,37 | Fit đến hết 2009 |
| 2010 transfer | ECM gauge-only | 645 | 14,63 | 18,72 | ECM fit trên 684 đỉnh năm 2009 |

Mọi so sánh paired dùng cùng tập chu kỳ cho hai mô hình. Bảng metric chi tiết theo tháng có ở `data/clean/p5_gauge_only_evaluation/monthly_metrics.csv`; đầu ra được dựng lại từ forecast đã lưu.

Ví dụ một đỉnh thật trong bảng 2007: `avonmouth:chronological_fit_through_2004:20061231T2300Z`, đỉnh quan trắc lúc 2007-01-01 05:00 UTC. Forecast origin là 2006-12-31 05:00 UTC (lead cấu hình 24 giờ). H quan trắc = 11,604 m; dự báo điều hòa = 11,5833 m, sai số +2,07 cm; dự báo ECM = 11,5574 m, sai số +4,66 cm. Ba residual lag là −0,1405, −0,1039 và −0,2754 m; hiệu chỉnh ECM là −0,02595 m. Ví dụ được giữ nguyên như đầu ra, dù ECM kém hơn tại đỉnh đơn lẻ này.

## Đối chiếu với bài báo và giới hạn

Bảng 1b công bố Avonmouth 2007 MAE 16,30 → 9,05 cm và RMSE 19,55 → 11,59 cm. Kết quả ở trên **không được lấy delta so với các số công bố**: nhánh này dự báo tổng mực nước H bằng gauge-only, còn bài báo dùng H−S và yêu cầu residual surge tương ứng. Không được dùng H−A để thay surge. File không xác định kênh gốc hoặc datum của gauge; ánh xạ ô lưới surge cũng chưa có. Vì vậy dự án chưa tái lập trực tiếp Bảng 1b.

Lead 24 giờ là thời gian cấu hình từ forecast origin đến đỉnh mục tiêu. Thời điểm gauge được cung cấp thực tế và độ trễ của nhà cung cấp không có metadata; phân tích giả định giá trị QC có thể dùng tại timestamp ghi nhận.

P6 đã xuất các bảng DimStation, DimDate, DimModel, DimRun, FactForecast, FactQuality, FactSpectrum ở CSV/Parquet; có Power Query M, DAX, quan hệ, từ điển và thiết kế bốn trang. Các lát cắt toàn bộ, tháng 1/2007 và một đỉnh khớp Python. **UI Power BI Desktop vẫn `UI_PENDING`** do môi trường chạy Linux; chưa có bằng chứng mở/refresh PBIX hoặc tương tác slicer.

## Tái chạy và bằng chứng

```bash
UV_CACHE_DIR=/tmp/uv-cache MPLCONFIGDIR=/tmp/mpl-cache uv run python scripts/run_p7_replay.py
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/compare_p7_replay.py
UV_CACHE_DIR=/tmp/uv-cache MPLCONFIGDIR=/tmp/mpl-cache uv run pytest -q
```

Replay P1–P6 trong `data/p7_replay/` chạy sạch; tất cả ID và counts khớp, sai lệch số tối đa bằng 0, metric dùng dung sai 1e−6 cm; test suite `21 passed`. Xem `reports/p7_replay/run_manifest.json`, `reports/p7_replay/comparison.csv`, `reports/acceptance/` và `reports/evidence_index.csv`.

Để tiếp tục nhánh paper-aligned, cần xin: (1) metadata/tệp BODC gốc xác định kênh và datum Avonmouth; (2) residual surge hindcast NOC CS3X theo giờ cho 2007 và bằng chứng ánh xạ ô lưới đến Avonmouth; (3) máy có Power BI Desktop để hoàn tất refresh và slicer check. Không dùng Portbury thay Avonmouth.
