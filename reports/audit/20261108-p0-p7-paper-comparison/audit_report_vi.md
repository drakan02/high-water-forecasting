# Kiểm toán P0–P7 và đối chiếu Hibbert et al. (2015)

**Audit ID:** `20261108-p0-p7-paper-comparison`

**Nhánh:** `audit/p0-p7-paper-comparison`, tạo từ commit P7 `7bf1290b71c904a2f4ca57d96021d83bd911654a`

**main:** `e6deb2b04ef28b1d5e42258b128f2f53d8f78882` (không checkout, sửa, commit hay push)

**Phạm vi:** kiểm toán snapshot P0–P7 và tính lại metric từ dự báo từng đỉnh đã lưu; không tuning, thay QC, chọn lại đỉnh hay refit để khớp bài.

## Kết luận

Dự án tái hiện được cấu trúc thực nghiệm ở mức **gauge-only**: baseline điều hòa, hiệu chỉnh đỉnh theo ba sai số N−2/N−4/N−6, phát hành giả định trước 24 giờ, và đánh giá ghép cặp trên cùng các đỉnh. Trên test 2007 và transfer 2010, ECM gauge-only giảm MAE và RMSE so với baseline gauge-only. Đây là bằng chứng về chiều cải thiện trong pipeline hiện có, không phải tái lập trực tiếp các trị số Hibbert.

Đối chiếu trực tiếp Bảng 1b còn bị ngăn bởi hai khác biệt khoa học cốt yếu: không có hindcast surge CS3x đúng năm/trạm/ô lưới nên dự án không thể dùng sai số `H−S−P`; đồng thời baseline UTide chưa được chứng minh tương đương EHM. Kênh gốc và datum của bản ghi GESLA cũng chưa được xác định. Vì thế không lấy hiệu giữa metric gauge-only và metric bài báo.

## Phương pháp trong bài và dự án thực chạy

Bảng đầy đủ: [`method_comparison.csv`](method_comparison.csv). Hibbert dùng chuỗi Avonmouth BODC năm 2007 gồm trung bình 15 phút từ gauge bubbler lấy mẫu 1 giây; loại mẫu suspect và downsample toàn bộ chuỗi xuống giờ. Surge đến từ hindcast NTSLF CS3x theo giờ. EHM Avonmouth cho 2007 được fit trên 1988–2007. ECM dùng sai số triều đã trừ surge tại các đỉnh N−2/N−4/N−6 và hằng số, với lead tới 24 giờ; bài bỏ qua lệch thời điểm giữa đỉnh quan trắc và đỉnh thiên văn. Sai số chấm điểm là `H−S−P`. [Mục Data và Methods, phương trình (5)–(6), Hình 2](https://nora.nerc.ac.uk/id/eprint/509610/1/1755876X.2015.1014641_Hibbert.pdf#page=3) [PDF gốc trên NERC](https://nora.nerc.ac.uk/id/eprint/509610/1/1755876X.2015.1014641_Hibbert.pdf#page=4)

Dự án dùng object Parquet GESLA công khai có lineage BODC, 853.104 dòng, 5.180.521 byte, SHA-256 `7a796fcb64215becd2fb429b75a48be5afcb392c613a7f54e509c36250e71bb8`. Toàn file trải từ 1961-01-01 đến 2012-04-30. Năm 2007 có đủ 35.040 timestamp 15 phút và 8.760 mốc phút 00; sau QC có 8.759 giờ hợp lệ. Mẫu suspect bị giữ nguyên cờ và loại khỏi fit; không nội suy. Đơn vị nguồn là mét, datum không khai báo trong record, kênh gốc primary/secondary chưa rõ. Nguồn là lineage BODC chứ chưa chứng minh là cùng file/kênh gốc nhóm tác giả dùng.

P2 dùng UTide 0.4.0, 68 constituents tự chọn, OLS, mean và trend, nodal corrections bật, pha Greenwich. Baseline hồi cứu fit 1988–2007 (148.551 mẫu hợp lệ); baseline theo thời gian fit 1988–2004 (123.271 mẫu), ECM fit năm 2005 trên 636 đỉnh; 2006 là validation. Dự án có 705 chu kỳ ứng viên năm 2007, 704 đỉnh H đạt QC, 702 dự báo có đủ lag tại origin và 701 đỉnh có đủ cả hai dự báo cùng nhãn. 2010 transfer có 705 ứng viên, 681 nhãn đạt QC, 657 dự báo, 645 cặp chấm được. Các bộ đếm có thể xem trong `paired_metrics.csv`.

ECM dự án là `P=A_N+C1e_(N−2)+C2e_(N−4)+C3e_(N−6)+C4`, với `e=H−A`; nó dự báo tổng mực nước H, không trừ surge. Coefficients fit 2005 là C1=0,9295371; C2=−0,3206953; C3=−0,1266835; C4=0,0364387 m. Code dùng cycle ID cho lag và không đọc H_N trong hàm predict; nhãn được nối sau dự báo. Lead 24 giờ là cấu hình issue, nhưng độ trễ cung cấp dữ liệu thực tế của nhà vận hành chưa được đo. 60/705 cặp đỉnh 2007 có đỉnh H và A lệch 1 giờ; điều này được báo cáo thay vì ép timestamp trùng.

UTide tái tổng hợp chính xác A(t) từ state đã lưu trên đoạn kiểm tra (sai khác cực đại quan sát được 0 m); lưới 2007 có 8.760 giá trị A, H và residual hợp lệ lần lượt 8.759. Phổ Welch dùng 1 mẫu/giờ, Hann, cửa sổ 336 giờ, overlap 168 giờ; 8.511 giờ hợp lệ đóng góp qua 49 cửa sổ. Residual `H−A` có thể còn tín hiệu khí tượng và sai số điều hòa, nên không được gọi là surge.

## Metric tính lại trên dự báo từng đỉnh

Sai số được tính bằng `100 × (H−P)` cm. MAE, RMSE, bias và mức cải thiện tính từ cùng các dòng đã ghép theo run/design/cycle; gain là baseline trừ ECM, trước khi làm tròn. Số liệu chi tiết và bộ đếm ghép nằm trong [`paired_metrics.csv`](paired_metrics.csv), từng dòng trong `*_paired_detail.csv`.

| Kỳ / thiết kế | n cặp | Baseline MAE | ECM MAE | Giảm MAE | Giảm MAE % | Baseline RMSE | ECM RMSE | Giảm RMSE | Bias baseline / ECM (cm) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2007 test theo thời gian, fit tới 2004 | 701 | 25,34 | 16,29 | 9,05 cm | 35,72% | 31,82 | 22,23 | 9,59 cm | +10,99 / +1,98 |
| 2007 hồi cứu, fit có cả 2007 (in-sample) | 701 | 25,21 | 16,28 | 8,93 cm | 35,41% | 31,62 | 21,82 | 9,80 cm | +10,02 / 0,00 |
| 2010 transfer, coefficients fit 1990–2009 | 645 | 21,86 | 14,63 | 7,23 cm | 33,06% | 27,37 | 18,72 | 8,65 cm | +2,01 / −2,00 |

Trên test 2007, ECM có absolute error thấp hơn baseline ở 493 đỉnh và cao hơn ở 208; hòa 0. Trên 2010 transfer, tốt hơn ở 436 và xấu hơn ở 209; hòa 0. Một ví dụ 2007 thật: chu kỳ `avonmouth:chronological_fit_through_2004:20061231T2300Z`, origin 2006-12-31 05Z, target 2007-01-01 05Z. Baseline dự báo 11,58330 m, ECM 11,55735 m, H=11,60400 m; sai số tuyệt đối lần lượt 2,07 cm và 4,66 cm. Các lag residual tại N−2/N−4/N−6 là −0,14048/−0,10387/−0,27535 m, tạo hiệu chỉnh −0,02595 m. ECM cải thiện trung bình nhưng không cải thiện mọi đỉnh; audit không thực hiện kiểm định ý nghĩa thống kê.

### Kiểm tra ba lát cắt P6

| Lát cắt 2007 | n | Baseline MAE / RMSE (cm) | ECM MAE / RMSE (cm) |
|---|---:|---:|---:|
| Cả năm, chronological test | 701 | 25,3412 / 31,8247 | 16,2892 / 22,2337 |
| Tháng 1 | 60 | 34,6728 / 42,4992 | 27,7786 / 38,5973 |
| Đỉnh ví dụ ở trên | 1 | 2,0701 / 2,0701 | 4,6649 / 4,6649 |

Các lát cắt năm và tháng khớp tính lại với artifact dự báo. Bảng BI gốc đã kiểm tra tháng 1 và một đỉnh; metric cả năm được tính bổ sung độc lập từ dự báo đã lưu. P6 xác nhận dữ liệu CSV/Parquet; mở/refresh PBIX và tương tác slicer vẫn `UI_PENDING`.

## Đặt cạnh số liệu bài báo

Bảng 1b in cột theo thứ tự RMSE rồi MAE. Với Avonmouth 2007: EHM 19,55/16,30 cm; ECM 11,59/9,05 cm; giảm nội bộ của bài là 7,96 cm RMSE và 7,25 cm MAE, tức giảm MAE 44,48%. [Bảng 1b và phần diễn giải](https://nora.nerc.ac.uk/id/eprint/509610/1/1755876X.2015.1014641_Hibbert.pdf#page=6)

| Kỳ | Bài: baseline MAE/RMSE | Bài: ECM MAE/RMSE | Dự án: baseline MAE/RMSE | Dự án: ECM MAE/RMSE | Chênh trực tiếp với bài |
|---|---:|---:|---:|---:|---|
| Avonmouth 2007 | 16,30 / 19,55 | 9,05 / 11,59 | 25,34 / 31,82 | 16,29 / 22,23 | Không tính: bài chấm H−S−P; dự án chấm H−P và dùng UTide |
| Avonmouth 2006–2009 | 14,37 / 17,80 | 8,94 / 11,61 | — | — | Chưa có run cùng thiết kế/kỳ và surge |
| Newport 2006–2009 | 15,83 / 19,26 | 9,71 / 12,89 | — | — | Chưa triển khai Newport |
| Avonmouth 2010 | Không có metric riêng theo trạm trong bài | Không có metric riêng theo trạm trong bài | 21,86 / 27,37 | 14,63 / 18,72 | Không có số bài theo trạm; mô tả định tính 42 trạm |

Bảng 2 dùng 2006–2009 và sai số đã trừ surge; bài báo nói các hệ số cố định tiếp tục giảm lỗi ở 42 trạm trong 2010 nhưng không đưa metric riêng Avonmouth. [Bảng 2 và đoạn xác nhận 2010](https://nora.nerc.ac.uk/id/eprint/509610/1/1755876X.2015.1014641_Hibbert.pdf#page=10) [Đoạn 2010](https://nora.nerc.ac.uk/id/eprint/509610/1/1755876X.2015.1014641_Hibbert.pdf#page=12)

## Phát hiện và ảnh hưởng

1. **Không đủ điều kiện tái lập trực tiếp Bảng 1b:** chưa có chuỗi residual surge hindcast CS3x phù hợp năm/trạm, kèm ánh xạ ô lưới; tuyệt đối không thay bằng `H−A`. Do đó metric 2007/2010 ở đây chỉ là đánh giá gauge-only.
2. **Không đồng nhất EHM và UTide:** bài nói EHM thường dùng 114 constituents nhưng không công bố danh sách chính xác Avonmouth; dự án đã lưu đầy đủ 68 constituent UTide, phase, amplitude, mean/trend và nodal options. Kết quả baseline khác biệt không chỉ do surge.
3. **Lineage dữ liệu chưa chứng minh identity:** GESLA file xác nhận Avonmouth và lineage BODC, nhưng release gốc không khai báo, channel chưa rõ, datum record chưa rõ. P0 chọn nguồn gauge-only hợp lệ; không thể tuyên bố dùng đúng bản/kênh BODC của bài.
4. **Kết quả metric được xác nhận với một điều kiện diễn giải:** mốc 2007 n=701, MAE/RMSE ECM 16,29/22,23 cm và transfer 2010 n=645, 14,63/18,72 cm khớp tính lại. Nhưng metric không phải hiệu suất ECM theo công thức đầy đủ của bài. 2010 không phải số liệu đối chiếu được công bố theo riêng Avonmouth.
5. **Retrospective 2007 là in-sample:** UTide fit có chứa 2007. Chỉ chronological run fit tới 2004 là test ngoại thời gian thích hợp trong các run hiện có.
6. **Power BI:** kiểm tra dữ liệu handoff đạt; giao diện Power BI Desktop chưa được nghiệm thu.

## Replay, kiểm tra và trạng thái Git

Replay audit mới chạy toàn bộ P1–P6 vào `reports/audit/20261108-p0-p7-paper-comparison/replay/data/`, khác hoàn toàn thư mục đầu ra P7 đã nghiệm thu. 12 bước trong manifest đều return code 0; so sánh 14 nhóm artifact đạt, max numeric difference 0. Audit thêm công cụ tính metric theo cặp chỉ đọc artifact và unit test fixture; toàn bộ suite hiện tại: **22 passed**. Đây là xác minh trực tiếp của audit, tách biệt với P7 lịch sử đã ghi 21 test.

SHA dữ liệu nguồn giữ nguyên. `main.py` untracked có sẵn được giữ nguyên (SHA-256 `35860e2c56f528ffbd1c0cceb633d11bf7940c69d907aad612009dd944765bd1`). Các log guarded ở `reports/` và `main.py` không thuộc audit commit. P0–P7 commit không bị sửa; main giữ nguyên SHA nêu đầu báo cáo.

## Lệnh tái chạy

Từ root repository, trong môi trường đã khóa:

```bash
UV_CACHE_DIR=/tmp/uv-cache MPLCONFIGDIR=/tmp/mpl-cache uv run python scripts/run_p7_replay.py \
  --replay-root reports/audit/20261108-p0-p7-paper-comparison/replay/data \
  --logs-dir reports/audit/20261108-p0-p7-paper-comparison/replay/logs \
  --manifest-path reports/audit/20261108-p0-p7-paper-comparison/replay/run_manifest.json
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/compare_p7_replay.py \
  --replay-root reports/audit/20261108-p0-p7-paper-comparison/replay/data \
  --comparison-path reports/audit/20261108-p0-p7-paper-comparison/replay/comparison.csv
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/audit_paired_metrics.py \
  --output-dir reports/audit/20261108-p0-p7-paper-comparison
UV_CACHE_DIR=/tmp/uv-cache MPLCONFIGDIR=/tmp/mpl-cache uv run pytest -q
```

Replay root cần không tồn tại hoặc rỗng trước lần chạy. Các script audit metric đọc forecast/label artifacts, không refit mô hình. Evidence paths và SHA-256 được liệt kê trong [`evidence_index.csv`](evidence_index.csv).
