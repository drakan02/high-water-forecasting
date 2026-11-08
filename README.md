# Dự báo đỉnh mực nước biển

Dự án này khảo sát cách dự báo các đỉnh triều cao tại cửa sông và cảng biển bằng dữ liệu mực nước quan trắc. Nền tảng phương pháp là bài báo của Hibbert và cộng sự (2015), nhưng kết quả trong repo được chia rõ thành **tái lập theo bài báo**, **thử nghiệm gauge-only bằng nguồn thay thế**, và **phần chưa thể kiểm chứng**.

## Bài toán là gì?

Mực nước tại trạm thủy triều thay đổi theo thời gian. Phần lớn biến động có quy luật do lực hấp dẫn của Mặt Trăng và Mặt Trời; gió và áp suất khí quyển cũng có thể làm mực nước cao hoặc thấp hơn dự đoán thủy triều. Đối với cảng và vùng cửa sông, dự báo sai một đỉnh triều có thể ảnh hưởng đến an toàn hàng hải, vận hành công trình và cảnh báo ngập.

Dự án tập trung vào **dự báo độ cao và sai số của từng đỉnh triều cao**. Câu hỏi phương pháp là: liệu có thể dùng sai số ở một số đỉnh trước đó để hiệu chỉnh dự báo đỉnh tiếp theo không?

## Hibbert và cộng sự (2015) làm gì?

Ở dạng khái quát, phương pháp trong bài gồm các bước:

1. Phân tích chuỗi mực nước để tạo dự báo thủy triều thiên văn, ký hiệu `A`.
2. Dùng hindcast nước dâng do thời tiết (residual surge), ký hiệu `S`, để ước lượng ảnh hưởng khí tượng.
3. Tại các đỉnh triều cao, tính phần sai khác còn lại giữa quan trắc và các thành phần đã dự báo. ECM dùng các sai khác ở những đỉnh trước — theo chỉ số `N−2`, `N−4`, `N−6` — để hiệu chỉnh đỉnh dự báo.
4. So sánh dự báo với quan trắc tại các đỉnh tương ứng và tính MAE, RMSE.

Bài báo sử dụng phương pháp điều hòa EHM với 114 thành phần triều và chuỗi surge hindcast CS3X của NTSLF. Với Avonmouth, Bảng 1(b) báo cáo MAE giảm từ **16,30 cm xuống 9,05 cm** và RMSE từ **19,55 cm xuống 11,59 cm** khi áp dụng ECM.

## Dự án này đã làm gì?

Do chưa có đủ dữ liệu đầu vào giống bài báo, dự án xây dựng một nhánh thử nghiệm **gauge-only** riêng:

1. Đọc số đo và cờ chất lượng, giữ nguyên đơn vị và loại các mẫu không đạt QC.
2. Dùng UTide để ước lượng thủy triều thiên văn `A(t)`.
3. Xác định các chu kỳ và đỉnh triều cao từ chuỗi giờ.
4. Tạo baseline điều hòa và ECM dùng sai số ở các đỉnh trước `N−2/N−4/N−6`.
5. Đối chiếu UTide và ECM trên cùng các đỉnh, rồi tính MAE/RMSE theo từng trạm, kỳ và mô hình.

Trong nhánh gauge-only, phần dư được tính là `H−A`, với `H` là mực nước quan trắc. Phần dư này **không phải surge hindcast đã xác minh**: nó có thể chứa ảnh hưởng thời tiết, sai số điều hòa và các thành phần khác. Vì thế dự án không dùng `H−A` thay cho `S` và không gọi các kết quả gauge-only là tái lập trực tiếp bài báo.

## Dữ liệu và QC

### Nguồn quan trắc

Nguồn chính là các đối tượng Parquet công khai trên GESLA S3, có lineage BODC. Đây là các bản ghi GESLA đã được tập hợp, **không phải bản tải processed nguyên gốc của BODC**. Dữ liệu thô không được đưa lên GitHub; một số tệp nằm local trong `data/raw/` và được ignore. Danh mục nguồn, thời đoạn, tọa độ, cờ QC và SHA-256 nằm trong [`data/source_inventory.csv`](data/source_inventory.csv) và [`reports/network_2010/`](reports/network_2010/).

Với Avonmouth, đối tượng đã kiểm tra có 853.104 dòng, từ 1961-01-01 đến 2012-04-30 theo thời gian UTC, cadence 15 phút và đơn vị mét. Riêng năm 2007 có 35.040 mốc 15 phút kỳ vọng; 35.030 dòng có cờ `qc_flag=1` và `use_flag=1`, còn 10 dòng bị gắn suspect. Sau khi tạo lưới giờ theo quy tắc phút 00 UTC, có 8.760 timestamp và 8.759 giờ hợp lệ. Không nội suy khoảng thiếu.

Trong mở rộng mạng lưới, 46 đối tượng GBR BODC-lineage được kiểm tra: 44 đối tượng ánh xạ một-một đến 44 cảng trong mạng lưới bài báo; Felixstowe và Moray Firth được giữ trong inventory nhưng không tính là cảng trong danh sách đó. Dữ liệu nguồn 15 phút được lọc theo QC rồi lấy các quan trắc đúng phút 00 để tạo lưới giờ. Không ghép hoặc lấy trung bình các kênh.

**Kênh BODC gốc và datum của các đối tượng GESLA chưa xác định được.** Không chuyển đổi mốc cao độ khi chưa có bằng chứng.

### Các kỳ và cách chấm

- **2006–2009 hồi cứu:** mô hình được fit và chấm trên cùng giai đoạn; kết quả này là in-sample, không phải kiểm tra ngoài mẫu.
- **2010 held-out:** UTide được fit trên dữ liệu đến hết 2009; ECM dùng các đỉnh đủ điều kiện trong 2006–2009 để dự báo năm 2010.
- Các chỉ số paired của UTide và ECM dùng chung ID đỉnh trong từng phép so sánh. `MAE` là sai số tuyệt đối trung bình; `RMSE` phạt sai số lớn mạnh hơn MAE.

## Kết quả mạng lưới 2010

Trên 42 cảng áp dụng được ECM theo phạm vi bài báo, có **22.267 cặp đỉnh** trong tập held-out 2010:

| Mô hình | MAE | RMSE |
|---|---:|---:|
| UTide gauge-only | 12,71 cm | 16,93 cm |
| ECM gauge-only | 9,71 cm | 13,16 cm |

ECM có MAE thấp hơn UTide tại cả 42 cảng được chấm; ở cấp từng đỉnh, ECM có sai số tuyệt đối thấp hơn tại 14.204/22.267 cặp. Hai cảng Port Ellen và Bournemouth vẫn được giữ trong inventory và kết quả điều hòa, nhưng ECM được ghi `NOT_APPLICABLE_PER_PAPER` do đặc điểm nhiều đỉnh cao/thấp trong ngày.

Các số này là kết quả của **thử nghiệm gauge-only trên dữ liệu GESLA/UTide**, không phải các con số của Bảng 2 Hibbert. Trung bình MAE theo cảng cũng khác với pooled MAE tính trực tiếp từ tất cả các cặp đỉnh; khi đọc Power BI cần xem rõ trường tổng hợp và mẫu số.

## Phần tái lập được và giới hạn

**Đã triển khai trên dữ liệu công khai:** kiểm toán nguồn, ingest/QC, baseline UTide, tạo đỉnh, ECM gauge-only, đánh giá ghép cặp, thử nghiệm ANN và Newlyn, thử nghiệm Newport, mở rộng 44 cảng, dashboard HTML offline và bảng dữ liệu Power BI. Acceptance report theo phase nằm trong [`reports/acceptance/`](reports/acceptance/); ma trận mô hình × cảng × kỳ × target ở [`reports/results/model_port_period_target.csv`](reports/results/model_port_period_target.csv).

**Chưa tái lập trực tiếp Bảng 1(b):** chưa có chuỗi residual surge CS3X phù hợp cho Avonmouth năm 2007 kèm ánh xạ ô lưới đã xác minh. Kênh/datum BODC gốc và tính tương đương giữa UTide với EHM 2015 cũng chưa được xác minh. Vì vậy, số liệu thay thế được gắn nhãn gauge-only/substitute và không so sánh delta trực tiếp với benchmark bài báo.

Các thử nghiệm mở rộng cũng giữ riêng giới hạn phương pháp: ANN không phải mạng Bayesian-regularized MATLAB của bài; chuyển giao Newlyn bằng UTide không phải triển khai SHOM MAS; Newport/mạng lưới là các kết quả gauge-only. Kết quả không bị loại chỉ vì kém hơn baseline.

## Dashboard và Power BI

- [`dashboard/index.html`](dashboard/index.html) là dashboard HTML hoạt động offline, gồm 44 cảng, bộ lọc cảng/kỳ/mô hình, độ phủ QC, metric, dự báo đỉnh và lịch sử độ trễ.
- Chạy `scripts/build_network_dashboard.py` để dựng dashboard và các bảng CSV nhập Power BI trong `data/bi_handoff_network/`.
- Chạy `scripts/validate_network_dashboard.py` để kiểm tra hash, schema, số dòng, khóa đỉnh và metric paired.
- Tài liệu mô hình, quan hệ, measures và gợi ý biểu đồ Power BI ở [`reports/powerbi/network/`](reports/powerbi/network/).

Báo cáo Power BI trên web cần được tạo từ semantic model và các bảng CSV/XLSX. Báo cáo tương tác cuối cùng do người dùng tạo/lưu trong Power BI Service; repo hiện bàn giao dữ liệu và thiết kế, không chứa một tệp PBIX đã kiểm chứng.

## Cấu trúc repo

- `src/tide/`: ingest, QC, harmonic, peak, ECM, evaluation, ANN và chuyển giao trạm.
- `configs/`: cấu hình khóa cho từng phân tích.
- `scripts/`: chạy phân tích, xuất dữ liệu và kiểm định dashboard/handoff.
- `tests/`: kiểm thử thuật toán và quy tắc QC.
- `data/source_inventory.csv`: danh mục nguồn và checksum.
- `reports/acceptance/`, `reports/decisions/`: phạm vi, quyết định và bằng chứng theo phase.
- `reports/network_2010/`: inventory, hệ số, metric và manifest mạng lưới.
- `data/raw/`, `data/clean/`, `data/bi_handoff_network/`: dữ liệu/đầu ra local được ignore theo chính sách; cần tải hoặc dựng lại trước khi replay tương ứng.

## Cài đặt và kiểm tra

Yêu cầu Python theo `.python-version` và `uv`:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv sync --locked
UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q
```

Để dựng lại dashboard và handoff sau khi các đầu ra P12 đã có local:

```bash
PYTHONPATH=src .venv/bin/python scripts/build_network_dashboard.py
PYTHONPATH=src .venv/bin/python scripts/validate_network_dashboard.py
```

Để tải lại dữ liệu mạng lưới GESLA và chạy lại P12 (có thể mất thời gian, chạy tuần tự theo trạm):

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/download_p12_gesla_bodc.py
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/build_p12_network_inventory.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 MPLCONFIGDIR=/tmp/mpl-cache PYTHONPATH=src UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/run_p12_network_2010.py --config configs/p12_network_2010.yaml
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/score_p12_network_2010.py --config configs/p12_network_2010.yaml
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/export_p12_models.py --config configs/p12_network_2010.yaml
UV_CACHE_DIR=/tmp/uv-cache uv run pytest -q
```

Lệnh chạy riêng cho Avonmouth và các thử nghiệm ANN/Newlyn/Newport được mô tả trong acceptance report và `NEXT_ACTION.md`. Một số bước cần dữ liệu nguồn local trước khi chạy.

## Tài liệu chính

- Bài báo Hibbert và cộng sự (2015): [bản lưu tại University of Liverpool](https://livrepository.liverpool.ac.uk/3179635/1/Hibbert_etal_2015.pdf).
- Đối chiếu từng yêu cầu bài báo: [`docs/paper_map.csv`](docs/paper_map.csv).
- Quyết định nguồn và nhánh gauge-only: [`reports/access_decision.md`](reports/access_decision.md).
- Bàn giao và giải thích kết quả Avonmouth: [`reports/final_handoff_vi.md`](reports/final_handoff_vi.md).
- Kiểm toán kết quả mạng lưới 2010: [`reports/final_network_review/final_acceptance_vi.md`](reports/final_network_review/final_acceptance_vi.md).
