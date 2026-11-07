# SOP tái lập dự báo độ cao đỉnh triều theo Hibbert và cộng sự (2015)

Phiên bản 1.1 • Repository: `high-water-forecasting` • Quy trình triển khai từ repository trống.

## 1. Mục tiêu và định nghĩa hoàn thành

Câu hỏi chính: tại Avonmouth, thông tin sai số ở ba đỉnh triều xen kẽ trước đó giúp thay đổi sai số dự báo độ cao đỉnh thứ N bao nhiêu cm so với mô hình điều hòa? Đơn vị phân tích là một chu kỳ đỉnh triều tại một cảng. Sản phẩm chính là bảng dự báo từng đỉnh, bảng so sánh sai số có thể tính lại, và Power BI cho phép truy từ chỉ số tổng hợp xuống một đỉnh cụ thể.

Ưu tiên chạy Avonmouth 2007, hai phương pháp điều hòa và hiệu chỉnh thực nghiệm (ECM). Mở rộng mặc định sang Avonmouth và Newport 2006–2009 và chấm 2010 khi có đúng đầu vào. Việc tái tạo cả bốn phương pháp tại Avonmouth và toàn bộ mạng lưới có phạm vi riêng ở mục 7. Mỗi kết quả phải có trạm, kỳ, loại mục tiêu, mô hình điều hòa, kỳ fit và số đỉnh được chấm.

Kết thúc khi một người khác có thể chạy lại từ nguồn hợp lệ và đối chiếu kết quả với bảng dự báo đã lưu. Chiều và độ lớn của cải thiện là kết quả cần báo cáo. Điểm số công bố dùng để đối chiếu sau khi khóa thiết kế.

## 2. Nguồn và quyết định về tính tương đương

| Nguồn cần đọc | Đọc để triển khai | Bằng chứng cần ghi |
|---|---|---|
| [Hibbert et al., Journal of Operational Oceanography, DOI](https://doi.org/10.1080/1755876X.2015.1014641) · [PDF mở](https://nora.nerc.ac.uk/id/eprint/509610/1/1755876X.2015.1014641_Hibbert.pdf) | Mục Data/Methods; Eq. 5, 6; Hình 2; Bảng 1a, 1b, 2 và thử trên năm 2010. | Trong paper_map.csv đánh dấu từng dòng là quy định trong bài, lựa chọn nhóm hoặc chi tiết chưa biết. |
| [BODC – UK Tide Gauge Network](https://www.bodc.ac.uk/data/hosted_data_systems/sea_level/uk_tide_gauge_network/processed/) | Số đo mực nước kiểm soát chất lượng, metadata và cờ. | Tên trạm, mã, tọa độ, múi giờ ghi trong file, đơn vị, mốc cao độ, lịch sử vị trí, cadence từng năm, quyền sử dụng. |
| [NOC – CS3/CS3X tide and surge](https://knowledge-software.noc-innovations.com/cs3/cs3x-tidesurge-model-data-format) | Phân biệt residual surge, tide only và tide+surge. Tìm chuỗi hindcast theo giờ cho đúng địa điểm và năm. | Ghi sản phẩm/phiên bản, trạm hoặc cách trích ô lưới, dấu, thời điểm hiệu lực và thời điểm cung cấp nếu có. Mô tả định dạng chưa đủ để xác nhận đã có dữ liệu. |
| [Codiga (2011), UTide technical report](https://www.po.gso.uri.edu/~codiga/utide/2011Codiga-UTide-Report.pdf) · [UTide Python](https://github.com/wesleybowman/UTide) | Tham khảo phương pháp ước lượng hằng số và tái tạo triều, triển khai solve/reconstruct. | Lưu phiên bản/commit, tùy chọn solver, constituent, xử lý nút quỹ đạo, pha, datum và trend. |
| [NOC-MSM/anyTide](https://github.com/NOC-MSM/anyTide) | Đọc ví dụ Oban và bộ tái tổng hợp triều để kiểm tra cách dùng hằng số. | Ghi file/commit và giấy phép nếu tái sử dụng. Hằng số tại Oban chỉ dùng cho ví dụ ở Oban. |

UTide và anyTide là hai nguồn tham khảo cho bước phân tích điều hòa. Ghi phiên bản và giấy phép của phần mềm thực sự sử dụng.

### Quyết định theo dữ liệu thực lấy được

| Dữ liệu | Nhãn nhánh | Dự báo và so sánh |
|---|---|---|
| Gauge, đúng surge lịch sử và EHM gốc hoặc cấu hình tương đương đã kiểm chứng | paper_aligned | Chấm phần triều tại đỉnh theo Eq. 6. Ghi rõ mọi chi tiết chưa tái tạo được. |
| Gauge và surge khả dụng, nhưng hằng số/solver điều hòa khác hoặc surge là sản phẩm thay thế | method_replication | Chạy cùng công thức, ghi tên baseline và sản phẩm surge thực dùng. Đối chiếu xu hướng và độ lớn, công khai sai khác đầu vào. |
| Chỉ có gauge | gauge_only | Dự báo tổng độ cao đỉnh quan trắc. Fit phần dư H−A và chấm H−P. Đánh dấu “biến thể tổng mực nước” trên mọi file/visual. Không điền số của nhánh này vào cột kết quả Eq. 6. |

Chọn nhánh sau khi đọc và kiểm tra một file mẫu của từng nguồn cần thiết. Nếu thiếu surge, soạn yêu cầu xin “hourly residual surge hindcast, Avonmouth, 2007”, sau đó bổ sung năm cần cho train/validation. Ghi đầu mối, nhu cầu giấy phép và đường dẫn đặt file. AI chỉ soạn yêu cầu để nhóm gửi. Tiến hành nhánh khả thi và giữ trạng thái của nhánh thiếu nguồn.

## 3. Hợp đồng khoa học

H, A, S cùng đơn vị; lưu độ cao bằng m và đổi sang cm đúng một lần khi chấm. H_N và A_N là hai cực đại trong cùng chu kỳ, có thể khác giờ. S_N là surge ứng với kỳ triều. Bài chưa đặc tả đủ mọi quy tắc ghép mẫu để khôi phục từng đỉnh; lựa chọn chi tiết của nhóm phải lưu vào config trước khi xem điểm.

~~~text
e_N       = H_N − S_N − A_N
y_train   = e_N
X_train   = [e_(N−2), e_(N−4), e_(N−6)]
P_base,N  = A_N
P_ecm,N   = A_N + C4 + C1*e_(N−2) + C2*e_(N−4) + C3*e_(N−6)
target_N  = H_N − S_N
error_cm  = 100 * (target_N − P_N)                # các biến đầu vào dùng m
~~~

Fit OLS có intercept C4 cho từng cảng. Ví dụ unit test, giả sử A=5 m, ba phần dư theo thứ tự = [0,10; −0,04; 0,02] m, hệ số [0,5; 0,25; 0,1], C4=0,01 m. Kết quả P=5,052 m. Nếu H=5,20 và S=0,10 m, error_base=10 cm, error_ecm=4,8 cm. Giá trị ví dụ là dữ liệu nhân tạo.

Hai thiết kế đánh giá, giữ riêng trong mọi bảng:

1. **Lịch sử theo bài.** Pilot dựng điều hòa trên Avonmouth 1988–2007, chấm 2007. Mạng lưới dựng điều hòa trên 1990–2009 hoặc hồ sơ dài nhất có thể, so 2006–2009. Lưu fit_start/end của cả điều hòa và ECM. Nếu không xác minh được tập fit ECM chính xác của pilot, ghi rõ: lựa chọn nhóm cho nhánh mô tả là fit ECM trên các đỉnh đủ lag năm 2007 rồi tính sai số trong mẫu. Không dùng kết quả này làm ước lượng dự báo ngoài mẫu. Chấm 2010 riêng với hệ số mạng lưới đã đóng băng khi có dữ liệu.
2. **Backtest theo thời gian của nhóm.** Điều hòa fit đến hết 2004, ECM fit 2005, rà quy trình 2006, khóa rồi chấm 2007. Lưu ngày đầu thực dùng, số mẫu và độ phủ. Lịch này ngắn hơn chuỗi điều hòa của pilot. Nếu thiếu lịch sử, ghi thay đổi, phiên bản và lý do trước khi mở tập chấm. Nạp đủ ngữ cảnh cuối năm trước để có lag cho đầu năm. Dùng phân vùng riêng cho nhánh này. Nhánh lịch sử đã xem 2007 thì công khai exposure của nhóm; tốt nhất khóa cả hai cấu hình trước khi chạy nhánh nào xuất metric 2007.

**Thời điểm phát hành.** Với backtest, quy tắc đề xuất là origin = giờ đỉnh điều hòa N trừ 24 giờ. Chỉ lấy các đỉnh cũ có cửa sổ đã khép và đủ đầu vào tại origin. Nếu N−2 hoàn tất sau origin, ghi loại với lý do; không lùi origin hoặc mượn N−1. Báo riêng coverage và lead tới đỉnh quan trắc. Nếu lệch pha giữa mốc phát hành và cửa sổ đỉnh khiến quá ít mẫu, vẫn giữ kết quả thiết kế 24h; có thể đăng ký một thiết kế thứ hai phát hành ngay khi ba lag khả dụng, ghi phân bố lead thực và đánh giá thành kết quả riêng. Historical hindcast ở ngày mục tiêu chỉ dùng lúc chấm. Khi thiếu timestamp phát hành surge cũ, dùng cờ availability_assumed và mô tả giả định độ trễ; chỉ kết luận về backtest hồi cứu. Các thời điểm theo UTC sau khi xác minh nguồn.

## 4. Repo và giao diện chạy

Khởi tạo cấu trúc dưới thư mục gốc của repository mới `high-water-forecasting`. Tạo `pyproject.toml` khai báo package `tide` trong `src/`, tệp khóa phụ thuộc, README và .gitignore cho dữ liệu tải về cùng thông tin đăng nhập. Cài package trong môi trường dự án trước khi chạy CLI. Ưu tiên Python, NumPy/SciPy, pandas hoặc Polars, Parquet, UTide; dùng SQL khi hữu ích cho môn học. CSV/Parquet là đường bàn giao Power BI trên Linux. Khóa phiên bản thực sự đã cài và ghi công cụ đọc dữ liệu. Không cần dựng dịch vụ Docker để bắt đầu thực nghiệm.

~~~text
configs/                  # nhánh, trạm, kỳ, fit, peak, issue time và QC
src/tide/                 # ingest, quality, harmonic, peaks, empirical, evaluate, export
tests/fixtures/           # sóng tổng hợp, đỉnh, khoảng trống, ví dụ tính tay
data/raw/                 # file nguyên trạng, theo nguồn/trạm/năm
data/clean/               # chuỗi đã chuẩn hóa và QC
runs/<run_id>/            # configs đã khóa, checksum, coefficients, forecasts, exclusions, metrics
powerbi/                  # mart, M/DAX, dictionary, quan hệ, hướng dẫn và PBIX nếu có
reports/                  # paper_map, access, kết quả, nghiệm thu, hình và slide
~~~

Giao diện dưới đây là **hợp đồng để AI xây**, chưa có lệnh nào được triển khai sẵn trong SOP. Cho phép đổi tên CLI nếu cập nhật README tương ứng. Những lệnh này phải chạy từ gốc repo; lệnh ingest nhận file đã tải hợp lệ hoặc tải từ nguồn cho phép.

~~~bash
python -m tide doctor --config configs/avonmouth.yaml
python -m tide ingest --config configs/avonmouth.yaml
python -m tide prepare --config configs/avonmouth.yaml
python -m tide fit --config configs/chronological.yaml --run-id avon_chrono_01
python -m tide predict --run-id avon_chrono_01
python -m tide evaluate --run-id avon_chrono_01
python -m tide export-bi --run-id avon_chrono_01
python -m pytest -q
~~~

**Khóa bảng.** station_id + source_product + time_utc cho chuỗi giờ. station_id + harmonic_series_id + cycle_id cho lịch đỉnh. run_id + station_id + cycle_id + model cho dự báo trong một nhánh. Giữ forecast_origin nếu một run tạo nhiều horizon và đưa origin vào khóa đó. Bảng lag lưu cycle_id nguồn, thời điểm và availability từng lag. Bảng QC chứa nguyên cờ nguồn và lý do loại. Bảng dự báo giữ H, A, S, target, predicted, error_cm, model, branch, split, fit_id, lead_hours và cờ eligibility. Trường không áp dụng để null kèm lý do. Forecast trước khi chấm và bảng nối nhãn sau chấm là hai artifact riêng.

## 5. Trình tự triển khai

### P0 • Thiết kế và quyền dữ liệu

1. Đọc nguồn mục 2; lập bảng đối chiếu Eq. 5–6, bảng 1b/2, trường bắt buộc và chi tiết phải giả định. Ghi cấu hình nào là bản lịch sử, backtest hay gauge-only.
2. Lập inventory trạm–năm–sản phẩm. Ưu tiên kiểm tra năm đầu train, 2005, 2006, 2007; sau đó 2008–2010. Avonmouth và Portbury là các trạm riêng. Dùng đúng metadata để xác định các giai đoạn đổi mốc đo.
3. Xác minh một file thật cho mỗi nguồn cần thiết. Ghi quyền tải, tái phân phối, kích thước, múi giờ, units, checksum và số header/data rows. Khóa danh sách metric và cách tính trước.
4. Xuất configs, data/source_inventory.csv, reports/access_decision.md và docs/paper_map.csv. **Đạt** khi xác định được nhánh chạy thực tế và chỉ rõ dữ liệu chưa lấy được. Fixture chỉ giúp phát triển phần mềm.

### P1 • Thu thập, kiểm tra và chuẩn hóa

1. Tải theo trạm/năm, lưu raw nguyên trạng, ghi checksum. Nếu tải đứt, ghi file tạm và kiểm tra trước khi đổi tên. Chạy lại phải giữ nguyên file đã khớp. Không đưa mật khẩu vào manifest.
2. Giữ cờ QC gốc; loại giá trị suspect theo bài và xử lý missing/invalid theo tài liệu nguồn. Ghi count theo từng loại cờ, giá trị sentinel, duplicate xung đột, cadence thực. Chỉ quy đổi datum khi có metadata xác nhận.
3. Tạo chuỗi giờ. Nhóm mặc định lấy mẫu đúng phút 00 UTC nếu nguồn có mốc đó; bài cho biết đã giảm tần số xuống giờ nhưng không đặc tả hết cách lấy mẫu. Khóa lựa chọn này; so sánh biến thể trung bình giờ riêng nếu cần. Giờ thiếu để null. Không nội suy cực đại làm nhãn thật. Không tự xóa đỉnh lớn chỉ vì là ngoại lệ thống kê.
4. Xuất data/clean/hourly.parquet, qc_by_station_month.csv, dictionary và biểu đồ 2 tuần. **Đạt** khi đếm được số timestamp kỳ vọng/thực có/hợp lệ, giải thích được duplicate, đơn vị và mốc cao độ ở mỗi trạm.

### P2 • Baseline điều hòa và phổ

1. Ưu tiên dự báo điều hòa hoặc bộ hằng số lịch sử có provenance. Nếu tự fit, lưu trạm/latitude, timezone, datum, danh sách constituent (gồm các thành phần nước nông nếu phù hợp), trend, phase convention, khoảng fit. EHM trong bài thường dùng 114 thành phần; số lượng giống nhau chưa đủ để chứng minh hai baseline tương đương.
2. Tạo chuỗi A(t) theo giờ, kể cả những giờ gauge thiếu để giữ lịch chu kỳ. Tạo và kiểm trên sóng tổng hợp có pha/amplitude biết trước. Vẽ H(t), A(t), S(t) riêng khi có. Ghi phiên bản repo tham khảo và lời gọi API đã chạy được.
3. Tạo phần dư giờ H−A−S ở nhánh có surge. Vẽ phổ Welch theo đoạn liên tục; ghi fs=1 mẫu/giờ, cửa sổ Hann, nperseg/noverlap, detrend, độ dài tối thiểu và đơn vị m²/(chu kỳ/giờ). Ví dụ cấu hình nhóm: nperseg=336 giờ, overlap=168; bỏ đoạn quá ngắn và báo phần dữ liệu còn lại. Đánh dấu năng lượng gần chu kỳ bán nhật triều; độ phân giải phụ thuộc độ dài đoạn. Welch là lựa chọn triển khai của nhóm. Phổ giờ và histogram sai số tại đỉnh là hai đầu ra khác nhau.
4. Xuất coefficients, fit manifest, harmonic_hourly và spectra.csv. **Đạt** khi tái tổng hợp được A từ artifact và kiểm tra được trục thời gian/đơn vị trên đồ thị.

### P3 • Lịch đỉnh và thiết kế lag

1. Từ lưới giờ A(t), xác định turning points. Quy ước nhóm: lấy hai cực tiểu điều hòa liên tiếp làm biên một chu kỳ bán nhật triều tại cảng pilot, giữ một cực đại A và tìm riêng cực đại H trong cùng khoảng. Chu kỳ nhiều cực đại rõ, biên thiếu, giá trị bằng nhau kéo dài hoặc sai khoảng cách bất thường phải gắn cờ. Rà trên train/validation rồi lưu quy tắc. Xác nhận lưới A tái tạo được cả khi quan trắc thiếu.
2. Mặc định đề xuất cho phân tích chính: nhãn H cần các giờ QC hợp lệ bao phủ toàn khoảng tìm đỉnh; loại cửa sổ thiếu để tránh cực đại giả thấp. Ghi ảnh hưởng đến số mẫu. Chọn S ở giờ đỉnh quan trắc đã ghép làm quy ước chính khi nguồn cho phép; lấy tại giờ đỉnh điều hòa chỉ là kiểm tra độ nhạy đã ghi trước. Không lấy cực đại S độc lập và không ước S bằng H−A.
3. Đánh số cycle_id trước khi loại QC. Join theo số chu kỳ N−2/N−4/N−6 trong cùng trạm và lịch baseline. Khi thiếu một đỉnh, các lag tham chiếu nó phải thiếu. Cấm dùng row shift sau dropna. Rà ít nhất 20 chu kỳ do nhóm chọn trước theo loại, gồm gap, đỉnh rõ, gần biên năm, đỉnh mơ hồ nếu có.
4. Xuất high_water.parquet, exclusions.csv và các ví dụ kiểm bằng tay. **Đạt** khi truy được mỗi lag về đúng đỉnh; thay đổi H ở tương lai không làm đổi predictor của một forecast đã phát hành.

### P4 • Fit và sinh dự báo

1. Fit OLS riêng theo trạm trên các hàng đủ target/lag trong kỳ fit. Ghi số hàng, ma trận đủ hạng, hệ số và intercept. Nếu hạng thiếu hoặc số mẫu không đủ ước lượng, ghi BLOCKED ở trạm tương ứng. Không tự đổi phương pháp để có kết quả đẹp.
2. Tách chức năng tạo nhãn, fit, predict và score. Hàm predict chỉ nhận A_N, ba e quá khứ, hệ số và trạng thái khả dụng. Chạy test sửa ngẫu nhiên H_N/S_N của mục tiêu sau khi khóa input: dự báo phải giữ nguyên. Có thể dùng target quá khứ sau khi quan trắc đã khả dụng cho các lần dự báo kế tiếp.
3. Khóa configs, phiên bản code, checksum model và danh sách split trước chấm. Dự báo 2007 theo cả hai thiết kế. Tách mẫu có thể nhận forecast ở origin khỏi mẫu sau này có quan trắc để chấm. Ghi từng lý do mất mẫu; không gán số 0 cho dự báo thiếu.
4. Nếu dữ liệu thật chưa sẵn, hoàn thành công thức, test và pipeline trên fixture; outputs ghi SYNTHETIC_ONLY. **Đạt trên dữ liệu thật** khi lưu forecasts trước khi join target, làm đúng ví dụ tính tay, và tái truy được hệ số cho từng run.

### P5 • Chấm, so với bài và kiểm tra chuyển kỳ

1. Dựng tập đỉnh chung có target và dự báo của cả hai mô hình. Lưu ID tập chung. Báo thêm coverage trên mọi chu kỳ ứng viên. Tính MAE=mean(abs(error_cm)), RMSE=sqrt(mean(error_cm²)), bias=mean(error_cm), gain_cm=MAE_base−MAE_ecm và gain_pct=100×gain_cm/MAE_base (null nếu mẫu số 0). Nếu tái tạo r² của bài, dùng 1−var(error)/var(H) với cùng đơn vị/cùng mẫu và khai báo trường H dùng; không mặc định lấy r2_score.
2. Mốc công bố dùng sau khi tính kết quả nhóm:

| Kỳ và cảng | MAE baseline → ECM (cm) | RMSE baseline → ECM (cm) |
|---|---:|---:|
| Avonmouth 2007, Bảng 1b | 16,30 → 9,05 | 19,55 → 11,59 |
| Avonmouth 2006–2009, Bảng 2 | 14,37 → 8,94 | 17,80 → 11,61 |
| Newport 2006–2009, Bảng 2 | 15,83 → 9,71 | 19,26 → 12,89 |

3. Tạo bảng paper_vs_replication với 3 cột riêng gồm số công bố, số tái lập, chênh lệch; thêm trạm/kỳ, n, tập fit, baseline, surge, quy tắc đỉnh, loại target và comparability. Với gauge_only để trống phần delta so bài. Nếu chênh nhiều, kiểm tra đơn vị, datum, H/A peak timing, surge, QC và fit theo thứ tự. Sửa lỗi có bằng chứng, lưu run cũ. Không tune trên 2007 để tiến gần 9,05.
4. Trình bày sai số từng cặp và phân bố theo tháng/cảng. Nếu thêm khoảng tin cậy, đăng ký trước cách resample theo block thời gian trên cùng cặp đỉnh; báo giả định và độ nhạy. Kết luận bằng cm và phạm vi thời gian. Không diễn giải giảm sai số thành độ chính xác cảnh báo ngập.
5. Với 2010, đóng băng hệ số đã fit đến 2009 và ghi ngày fit của cả baseline lẫn ECM. Mỗi cảng một kết quả; ghi đúng số cảng thực chạy. **Đạt** khi người rà soát tính lại toàn bộ metric từ CSV, kiểm tra số đỉnh bằng nhau trên so sánh paired và đếm được số loại.

### P6 • Mô hình dữ liệu Power BI và dashboard

1. Xuất DimStation, DimDate, DimModel, DimRun, FactForecast (mỗi đỉnh/mô hình/run/origin), FactQuality và FactSpectrum. Tạo khóa dimension duy nhất, quan hệ 1:n lọc một chiều; date từ đỉnh mục tiêu. Ghi rõ tập mẫu chung và giữ cờ paired_eligible. Thẻ số đỉnh dùng distinct station/cycle key trong một run, tránh đếm đôi do hai model.
2. Measures trên các hàng đã lọc paired_eligible: MAE = AVERAGEX(hàng hợp lệ, ABS(error_cm)); RMSE = SQRT(AVERAGEX(hàng hợp lệ, error_cm²)). Gain phải so hai model trong cùng run, trạm, khoảng ngày và cùng tập đỉnh. DAX thực phải có kiểm tra blank và mẫu số 0. Giữ slicer một target/nhánh mỗi lần so sánh. Không lấy trung bình các RMSE tháng để ra RMSE năm.
3. Dựng bốn trang: (i) bản đồ trạm, coverage và heatmap thiếu; (ii) đường giờ thực đo/điều hòa, drill-through đến hai giờ đỉnh và QC; (iii) phổ phần dư theo giờ và histogram tại đỉnh có đơn vị; (iv) sai số hai model, n, MAE/RMSE và bảng truy ra ba lag cùng số cm hiệu chỉnh. Đường ECM chỉ có giá trị tại đỉnh, không nối thành chuỗi dự báo hàng giờ giả.
4. Xuất CSV/Parquet, Power Query M tham số hóa path, DAX, data dictionary, quan hệ, danh mục visual và bảng counts/metrics kỳ vọng. Nếu có Power BI Desktop, mở/refresh PBIX và kiểm ít nhất 3 lát cắt (toàn pilot, một tháng, một đỉnh). Trên Linux có thể hoàn tất bàn giao dữ liệu; ghi UI_PENDING cho đến khi mở trên máy có Desktop. **Đạt phần dữ liệu** khi ba lát cắt khớp Python; **đạt UI** khi có bằng chứng refresh và slicer.

### P7 • Tái chạy và bàn giao

1. Trong thư mục output sạch, chạy lại với cùng manifest/cache raw, cấu hình và phiên bản. So ID, counts, hệ số, forecast và metric. Mặc định nhóm dùng dung sai tuyệt đối 1e−6 cm trên metric khi môi trường đã khóa; ID, n và cờ phải khớp tuyệt đối. Tách timestamp/run ID khỏi đối chiếu nội dung số.
2. Tổng hợp coverage, lý do loại, tập fit, kết quả công bố/nhóm, các lựa chọn chưa xác minh và phạm vi Power BI đã kiểm tra. Báo cáo riêng kết quả hồi cứu và backtest. Ghi số giờ dẫn trước thực tế và tình trạng biết/giả định độ trễ nguồn.
3. Xuất README tái chạy, báo cáo tiếng Việt, hình, slide và evidence_index.csv. Minh họa một đỉnh bằng các số thật đã lưu, sau đó đặt nó trong phân bố toàn bộ đỉnh. **Đạt** khi người không viết model tái tạo được bảng điểm từ forecast đã lưu và biết phải xin dữ liệu nào để tái chạy từ đầu.

## 6. Bộ kiểm thử và báo cáo bắt buộc của AI

| Kiểm thử | Fixture hoặc thao tác | Điều kiện mong đợi |
|---|---|---|
| Đơn vị/datum | Hai nguồn m và cm; một file thiếu datum | Đổi đơn vị chính xác, không tự ghép hai mốc chưa xác định. |
| Cờ nguồn/duplicate | Một sentinel, một suspect, hai record xung đột | Số loại khớp nguyên nhân; input nguồn giữ nguyên. |
| Lịch đỉnh | Xóa đỉnh giữa chuỗi, hai đỉnh lệch giờ H/A, một plateau | Hai cực đại ghép đúng chu kỳ; lag không trượt; plateau có quyết định tái lập được. |
| Dấu và hệ số ECM | Ví dụ tại mục 3 | 5,052 m, 10 cm và 4,8 cm. |
| Rò rỉ thời gian | Sửa H_N, S_N hoặc giá trị sau origin; thêm một lag đến muộn | Forecast cũ bất biến; hàng đến muộn bị gắn cờ theo quy tắc đã khóa. |
| Split và tập chung | Cùng một đỉnh thiếu forecast ở một model; chu kỳ gần 1/1 | So sánh chỉ dùng ID chung; lag hợp lệ có thể lấy từ cuối năm trước. |
| Metric/BI | Tính lại từ detail cho một tháng và toàn kỳ | n, MAE, RMSE khớp; strata khác target bị tách. |
| Chạy lại | Cùng config, raw, model trên thư mục output khác | So khóa tự nhiên, counts, metric, lưu kết quả kiểm tra. |

Sau mỗi phase, cập nhật một dòng trong reports/status.csv gồm phase, branch, station, period, trạng thái, artifact thật, lần chạy, giới hạn, bước tiếp theo. Dùng DONE cho bước đã thực thi và kiểm tra; PARTIAL cho đầu ra dùng được còn thiếu thành phần; BLOCKED cho phụ thuộc cụ thể; NOT_RUN cho bước chưa chạy. Nếu đã có bằng chứng tái dùng được, xác minh rồi tiếp tục. Không phát sinh gate mới chỉ vì metric thấp hơn kỳ vọng.

## 7. Mở rộng để tái lập toàn bài

- **ANN tại Avonmouth.** Đọc Methods và tái lập riêng thiết kế đầu vào theo giờ, horizon và cấu hình MATLAB của bài. Dùng train 2005, validation 2006, pilot 2007. Nếu dùng thư viện khác, lưu activation, regularization, seed, số lượt huấn luyện và cách chọn kết quả. Đối chiếu Bảng 1a theo giờ, sau đó subsample ở đỉnh cho Bảng 1b.
- **Species concordance.** Chuẩn bị dữ liệu cảng tham chiếu Newlyn và chuỗi ghép với Avonmouth; trích Eq. 2–4, các nhóm thành phần và hằng số chuyển cảng. Kiểm tra khả năng tiếp cận SHOM MAS. Ghi rõ cách tính thay thế nếu dùng công cụ khác.
- **Mạng lưới.** Inventory toàn bộ 44 địa điểm của bài; đánh dấu Bournemouth và Port Ellen, nơi tác giả không áp dụng ECM do hình dạng triều phức tạp. Đối chiếu 42 cảng có kết quả, sau đó chấm 2010 với hệ số đã khóa. Bản chạy hai cảng phải ghi rõ tử số/mẫu số cảng đã tái tạo.
- **Điều kiện mở rộng.** Hoàn thành pilot hai mô hình, backtest, bảng kiểm soát dữ liệu và Power BI trước khi mở các nhánh trên. Báo cáo phần mở rộng riêng nếu nguồn hoặc thời gian chưa đủ.
