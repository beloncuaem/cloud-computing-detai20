# Đồ án Điện toán đám mây - Đề tài 20
**Chủ đề:** Bảo vệ dữ liệu bằng mã hóa, quản lý khóa và vòng đời bí mật

## Thành viên nhóm
1. Sinh viên 1 - Leader / Infrastructure & Security
2. Sinh viên 2 - Developer / Application & Automation
3. Sinh viên 3 - Tester / DevSecOps & Report

## Quy định Commit Convention
- `feat:` Tính năng mới
- `fix:` Sửa lỗi
- `test:` Kịch bản kiểm thử
- `docs:` Tài liệu / Báo cáo
- `chore:` Cấu hình hạ tầng, công cụ

## Cấu trúc thư mục
- `api/`: mã nguồn FastAPI, SQL, script Vault và Dockerfile
- `docker-compose.yml`: stack lab dự phòng (PostgreSQL + Vault dev + API)
- `bench/`: kịch bản k6, script phân tích CSV và kết quả thô
- `docs/`: báo cáo, ảnh bằng chứng, kế hoạch kiểm thử và hướng dẫn hạ tầng
- `scripts/`: smoke test PowerShell
- `.github/workflows/`: CI security gate (Gitleaks + unit tests)

## Chạy nhanh bằng Docker (phương án dự phòng)
Stack này dùng Vault dev mode để kiểm thử trong lúc chờ hạ tầng Vault file storage + TLS của SV1. Không dùng cho production hoặc dữ liệu thật.

```powershell
docker compose up -d --build
powershell -ExecutionPolicy Bypass -File scripts/smoke-test.ps1
```

Chi tiết vận hành: `docs/infra/local-stack.md`. Kế hoạch kiểm thử T01–T16: `docs/testing/test-plan.md`. Hướng dẫn chạy trực tiếp trên Windows: `api/README_VI.md`.
