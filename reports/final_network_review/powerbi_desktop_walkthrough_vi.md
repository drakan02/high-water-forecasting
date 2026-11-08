# Hướng dẫn mở gói mạng lưới trong Power BI Desktop

## Tệp cần chép sang Windows

Tạo một thư mục, ví dụ `C:\high-water-forecasting\data\bi_handoff_network\`, rồi chép từ repo các tệp sau:

| Tệp nguồn trong repo | Vai trò |
|---|---|
| `data/bi_handoff_network/DimStation.csv` | 44 cảng, tọa độ, coverage, tình trạng ECM và metadata nguồn |
| `data/bi_handoff_network/DimPeriod.csv` | Hai kỳ: retrospective 2006–2009 và held-out 2010 |
| `data/bi_handoff_network/DimModel.csv` | UTide và ECM; target cố định |
| `data/bi_handoff_network/FactPeakMetrics.csv` | Metric tổng hợp theo cảng × kỳ × model; dùng kiểm tra trạng thái và số cặp, không lấy trung bình RMSE cấp cảng |
| `data/bi_handoff_network/FactPeakForecast.csv` | Bảng chi tiết theo đỉnh × model, gồm H, forecast, sai số, origin và ba lag; đây là bảng để tính MAE/RMSE pooled |
| `data/bi_handoff_network/manifest.json` | SHA-256, số dòng và nhãn target của gói P13 |
| `reports/final_network_review/station_metrics_2010.csv` | Mức giảm MAE theo cảng cho riêng held-out 2010; không dùng cho kỳ khác |

Gói P13 hiện là CSV cục bộ bị Git ignore, được tạo bởi `scripts/build_network_dashboard.py`; nếu thiếu thư mục, chạy lệnh đó trong worktree P13 nơi các output P12 tồn tại rồi chép CSV. Bảng `FactPeakForecast.csv` khoảng 67 MB. Không có file PBIX/PBIT trong repo; hãy tạo PBIX mới.

Các tên bảng/cột dưới đây khớp header CSV thực tế. Target duy nhất là `total_observed_water_level_gauge_only`. Không có cột `run_id` hoặc cột năm riêng: nguồn là run P12 đã nghiệm thu; trường kỳ đánh giá là `DimPeriod[period]` với giá trị `heldout_2010` hoặc `retrospective_2006_2009`.

## Tạo PBIX và nhập CSV

1. Mở Power BI Desktop trên Windows, chọn **Blank report**, rồi **Get data → Text/CSV**. Chọn lần lượt năm CSV trong thư mục đã chép và chọn **Transform Data**.
2. Với mỗi query, kiểm tra delimiter comma và encoding UTF-8. Dùng **Change Type → Using Locale…** cho số thập phân, chọn **Decimal Number** và locale English (United States), vì file dùng dấu chấm thập phân. Đặt `valid_2010`, `present_2010`, `expected_2010`, port và counts thành Whole Number; flags thành True/False; thời gian forecast thành Date/Time/Time Zone nếu Power Query nhận được offset `+00:00`. Giữ SHA, ID, target, tên cảng và period là Text.
3. Đặt tên query/table chính xác là `DimStation`, `DimPeriod`, `DimModel`, `FactPeakMetrics`, `FactPeakForecast`, `StationGain2010` (bảng cuối từ `station_metrics_2010.csv`). Chọn **Close & Apply**.

Nếu muốn đổi thư mục mà không chọn lại từng file, tạo Text parameter tên `pDataFolder`, giá trị là thư mục chứa CSV, ví dụ `C:\high-water-forecasting\data\bi_handoff_network`. Trong Advanced Editor, nguồn Power Query cho từng CSV có dạng dưới đây; thay tên file tương ứng và dùng bước `PromoteHeaders`:

```powerquery
let
    Source = Csv.Document(
        File.Contents(pDataFolder & "\DimStation.csv"),
        [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]
    ),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true])
in
    Headers
```

## Quan hệ và bộ lọc

Trong **Model view**, tạo quan hệ `1:*`, hướng lọc single từ dimension sang fact:

- `DimStation[station_id]` → `FactPeakForecast[station_id]`
- `DimStation[station_id]` → `FactPeakMetrics[station_id]`
- `DimStation[station_id]` → `StationGain2010[station_id]`
- `DimPeriod[period]` → `FactPeakForecast[period]`
- `DimPeriod[period]` → `FactPeakMetrics[period]`
- `DimModel[model]` → `FactPeakForecast[model]`
- `DimModel[model]` → `FactPeakMetrics[model]`

Không tạo quan hệ từ `StationGain2010` sang kỳ: bảng này chỉ có 42 hàng cho 2010. Measure biểu đồ phía dưới trả blank khi không chọn riêng `heldout_2010`. Các bảng forecast/metric có target cố định; không cần slicer target. Dùng slicer `DimStation[station]` và `DimPeriod[label]`; nếu thêm slicer model, không dùng nó để lọc các card tính song song cả hai mô hình.

Tạo các measure sau (menu **Modeling → New measure**). Các metric được tính lại từ từng đỉnh trong `FactPeakForecast`; không lấy trung bình các giá trị RMSE đã tổng hợp trong `FactPeakMetrics`.

```DAX
UTide Ports :=
CALCULATE (
    DISTINCTCOUNT ( FactPeakMetrics[station_id] ),
    FactPeakMetrics[model] = "UTide-0.4.0",
    FactPeakMetrics[status] = "DONE",
    FactPeakMetrics[target] = "total_observed_water_level_gauge_only"
)

ECM Paired Ports :=
CALCULATE (
    DISTINCTCOUNT ( FactPeakMetrics[station_id] ),
    FactPeakMetrics[model] = "ECM-OLS-3lag",
    FactPeakMetrics[status] = "DONE",
    FactPeakMetrics[n_scored_paired] > 0,
    FactPeakMetrics[target] = "total_observed_water_level_gauge_only"
)

Paired Peak N :=
CALCULATE (
    DISTINCTCOUNT ( FactPeakForecast[cycle_id] ),
    FactPeakForecast[model] = "UTide-0.4.0",
    FactPeakForecast[paired_sample] = TRUE (),
    FactPeakForecast[target] = "total_observed_water_level_gauge_only"
)

UTide MAE cm :=
CALCULATE (
    AVERAGEX (
        FILTER ( FactPeakForecast,
            FactPeakForecast[paired_sample] = TRUE ()
                && FactPeakForecast[model] = "UTide-0.4.0"
        ), ABS ( FactPeakForecast[error_m] ) * 100
    ),
    FactPeakForecast[target] = "total_observed_water_level_gauge_only"
)

ECM MAE cm :=
CALCULATE (
    AVERAGEX (
        FILTER ( FactPeakForecast,
            FactPeakForecast[paired_sample] = TRUE ()
                && FactPeakForecast[model] = "ECM-OLS-3lag"
        ), ABS ( FactPeakForecast[error_m] ) * 100
    ),
    FactPeakForecast[target] = "total_observed_water_level_gauge_only"
)

UTide RMSE cm :=
CALCULATE (
    SQRT ( AVERAGEX (
        FILTER ( FactPeakForecast,
            FactPeakForecast[paired_sample] = TRUE ()
                && FactPeakForecast[model] = "UTide-0.4.0"
        ), POWER ( FactPeakForecast[error_m] * 100, 2 )
    )),
    FactPeakForecast[target] = "total_observed_water_level_gauge_only"
)

ECM RMSE cm :=
CALCULATE (
    SQRT ( AVERAGEX (
        FILTER ( FactPeakForecast,
            FactPeakForecast[paired_sample] = TRUE ()
                && FactPeakForecast[model] = "ECM-OLS-3lag"
        ), POWER ( FactPeakForecast[error_m] * 100, 2 )
    )),
    FactPeakForecast[target] = "total_observed_water_level_gauge_only"
)

Ports Improving 2010 :=
IF (
    SELECTEDVALUE ( DimPeriod[period] ) = "heldout_2010",
    DIVIDE (
        COUNTROWS ( FILTER ( StationGain2010, StationGain2010[gain_mae_cm] > 0 ) ),
        COUNTROWS ( StationGain2010 )
    ) * 100,
    BLANK ()
)

MAE Gain 2010 cm :=
IF (
    SELECTEDVALUE ( DimPeriod[period] ) = "heldout_2010",
    MAX ( StationGain2010[gain_mae_cm] ),
    BLANK ()
)
```

Đặt định dạng bốn metric MAE/RMSE là Decimal Number với 2 chữ số thập phân; `Ports Improving 2010` là số phần trăm. Thêm card `UTide Ports`, `ECM Paired Ports`, `Paired Peak N`, hai MAE, hai RMSE và `Ports Improving 2010`. `FactPeakMetrics` là bảng cấp cảng/kỳ/model; `FactPeakForecast` có một dòng cho mỗi model trên mỗi đỉnh, nên measure đếm cặp lọc một model để không đếm đôi.

## Tạo biểu đồ theo cảng

Tạo clustered bar chart: **Y-axis** = `StationGain2010[station_name]`, **X-axis** = measure `MAE Gain 2010 cm`; sắp giảm dần theo measure. Giá trị dương nghĩa là ECM giảm MAE so với UTide. Có thể dùng trực tiếp PNG `reports/final_network_review/ecm_mae_gain_by_port_2010.png` làm hình tham khảo. Giữ thông báo/tiêu đề rằng kết quả chỉ là held-out 2010 và gauge-only.

## Kiểm tra ba lát cắt và giá trị mong đợi

1. **Toàn mạng, 2010:** đặt `DimPeriod[label] = 2010 held-out`, bỏ lọc cảng/model, target cố định. Kỳ vọng 44 cảng UTide; 42 cảng có ECM ghép cặp; 22,267 cặp đỉnh; UTide MAE/RMSE **12.71/16.93 cm**; ECM **9.71/13.16 cm**; 42/42 cảng cải thiện (100%). Port Ellen và Bournemouth hiện UTide nhưng ECM `NOT_APPLICABLE_PER_PAPER`.
2. **Một cảng:** thêm slicer `DimStation[station] = Avonmouth`. Kỳ vọng n=645; UTide MAE/RMSE **21.86/27.37 cm**; ECM **14.85/18.97 cm**; gain MAE **7.0139 cm**.
3. **Một đỉnh cụ thể:** lọc `FactPeakForecast[cycle_id]` bằng `p06_avonmouth:p06_avonmouth_network_2010_fit_1990_2009:20100101T0200Z`. Target time **2010-01-01 07:00 UTC**, origin **2009-12-31 07:00 UTC**; H **13.416 m**, UTide forecast **13.20596057 m**, ECM forecast **13.15163533 m**. Dự án lưu `error_m = prediction_m − H_m`; ở hàng UTide và ECM, `paired_sample` phải true.

Giá trị kỳ vọng được lấy từ P12 forecast/metric đã lưu và tính lại trong `reports/final_network_review/`; nếu số trên màn hình lệch, kiểm tra locale, period, target, model filters và việc `paired_sample` đang bật trước khi chụp hình.

## Refresh và ghi nhận UI

Chọn **Home → Refresh**, kiểm tra không có lỗi đường dẫn hoặc chuyển kiểu dữ liệu, lưu file `.pbix`, rồi chụp ảnh trang mạng lưới, bộ lọc Avonmouth và bảng chi tiết một đỉnh. Ghi phiên bản Power BI Desktop, ngày refresh và các slicer đang chọn trong biên bản kiểm tra. Nộp PBIX/ảnh kiểm tra vào repo hoặc thư mục bàn giao để đối chiếu với các giá trị mong đợi ở trên.

**Giữ `UI_PENDING` cho tới khi người dùng mở Power BI Desktop trên Windows, refresh thành công và xác nhận ba lát cắt khớp.** Hướng dẫn này và validator Python chưa phải bằng chứng giao diện đã pass.
