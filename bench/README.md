# Benchmark — k6

Thư mục này chứa kịch bản đo và kết quả thô cho Chương 4. Kết quả phải đo trên cùng một máy, cùng dữ liệu và cùng tài nguyên container; ghi lại phiên bản Docker, Vault, PostgreSQL, k6 và cấu hình CPU/RAM.

## 1. Kịch bản

`k6/mixed.js` mô phỏng 70% ghi và 30% đọc:

- Ghi: `POST /records` với `record_type = bench_phone`, giá trị tổng hợp `090xxxxxxx`.
- Đọc: `GET /records/{id}` của một bản ghi được tạo trong `setup()`.
- Header `X-API-Key` lấy từ biến môi trường `API_KEY`.
- `SLEEP` (giây, mặc định `0`) giãn nhịp sau mỗi vòng lặp. Benchmark hiệu năng để mặc định; T16 dùng `SLEEP>0` để tải nền không vượt ngưỡng cảnh báo.

Chạy qua Docker để không cần cài k6 trên máy:

```powershell
New-Item -ItemType Directory -Force bench/results | Out-Null

# Warm-up 60 giây, không ghi CSV
docker run --rm -v "${PWD}:/work" -w /work grafana/k6:0.54.0 run `
  -e BASE_URL=http://host.docker.internal:8000 `
  -e API_KEY=local-demo-api-key-change-me `
  -e VUS=10 -e DURATION=1m bench/k6/mixed.js

# Đo chính thức (ví dụ D-lab, 50 VUs, lần 1)
docker run --rm -v "${PWD}:/work" -w /work grafana/k6:0.54.0 run `
  -e BASE_URL=http://host.docker.internal:8000 `
  -e API_KEY=local-demo-api-key-change-me `
  -e VUS=50 -e DURATION=3m `
  --out csv=bench/results/D-lab_50_run1.csv bench/k6/mixed.js
```

Nếu API chạy native trên Windows (không qua Docker), dùng `BASE_URL=http://127.0.0.1:8000`; nếu k6 chạy trong container thì `host.docker.internal` trỏ về máy host trên Docker Desktop.

Với T16 (kiểm tra false positive của cảnh báo giải mã), chạy tải nền chậm trong 10 phút: `VUS=5`, `SLEEP=2`, `DURATION=10m`. Lượng decrypt ~90/phút, thấp hơn ngưỡng 200/phút. Nếu chạy k6 trong cùng network Compose thì dùng `BASE_URL=http://api:8000` thay cho `host.docker.internal`.

## 2. Ma trận cấu hình

| Mã | Cấu hình | Ghi chú |
|---|---|---|
| A | Plaintext, HTTP | Baseline. App hiện chưa có chế độ này; cần build benchmark riêng, không merge vào `main` |
| B | TLS | Chờ SV1 cấu hình TLS |
| C | TLS + mã hóa volume | Chờ SV1 + BitLocker/volume encryption |
| D | TLS + envelope encryption | Đo được phần envelope; nếu chưa có TLS thì ghi là `D-lab` |
| E | D + rotation | Xoay DB credential/KEK trong lúc chạy k6 |
| D' | D sau tối ưu | Sau khi SV2 cache DEK/giảm gọi Vault |

Không được ghi `D-lab` thành `D` trong báo cáo. Mỗi cấu hình chạy tối thiểu 5 lần; mỗi lần 3–5 phút; lặp lại ở 10, 50, 100 VUs. Khởi động lại stack trước mỗi cấu hình.

## 3. Đặt tên và phân tích

Mẫu tên: `<config>_<vus>_run<N>.csv`, ví dụ `D-lab_50_run3.csv`. Khi lưu vào Git, nén lossless thành `.csv.gz` để giảm dung lượng (một lượt 3 phút có thể tạo 100–300 MB CSV thô; `.gz` thường còn 3–10%). `analyze.py` đọc trực tiếp file `.csv.gz`.

Mỗi lượt nên kèm `--summary-export=bench/results/<config>_<vus>_run<N>_summary.json` (vài KB) để đối chiếu nhanh p50/p95/p99 và error rate kể cả khi CSV bị lược bớt.

```powershell
docker run --rm -v "${PWD}:/work" -w /work python:3.12-slim `
  python bench/analyze.py "bench/results/*.csv.gz"
```

Script in bảng p50/p95/p99, trung vị p95 theo cấu hình/VUs và overhead so với baseline A nếu có. Đây là số liệu để điền bảng Chương 4, không thay thế việc lưu dữ liệu thô.

## 4. Đo trong lúc rotation (E)

```powershell
# Terminal 1: chạy k6 50 VUs trong 3 phút
docker run --rm -v "${PWD}:/work" -w /work grafana/k6:0.54.0 run `
  -e BASE_URL=http://host.docker.internal:8000 `
  -e API_KEY=local-demo-api-key-change-me `
  -e VUS=50 -e DURATION=3m `
  --out csv=bench/results/E_50_run1.csv bench/k6/mixed.js

# Terminal 2: sau khi k6 đã chạy khoảng 60 giây
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/admin/rotation/database" `
  -Headers @{ "X-Admin-Key" = "local-demo-admin-key-change-me" }
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/admin/rotation/transit-key" `
  -Headers @{ "X-Admin-Key" = "local-demo-admin-key-change-me" }
```

Ghi lại thời điểm bắt đầu/kết thúc rotation và cửa sổ lỗi (nếu có). H2 yêu cầu tỷ lệ lỗi dưới 0,1% trong cửa sổ này.

## 5. Bằng chứng cần lưu

- CSV thô (nén `.csv.gz`) trong `bench/results/`; kèm `_summary.json` cho từng lượt. Chỉ commit dữ liệu tổng hợp, không commit log chứa secret.
- Ảnh summary k6 của mỗi cấu hình.
- Ảnh thời điểm rotation và kết quả API rotation.
- Bảng tổng hợp do `analyze.py` in ra.
- Mô tả máy: CPU, RAM, phiên bản Docker/Vault/PostgreSQL/k6.
- Nêu rõ giới hạn: máy cá nhân, không suy diễn sang production; `D-lab` khác `D` nếu thiếu TLS.
