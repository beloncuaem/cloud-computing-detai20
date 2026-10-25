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
- `app/`: Mã nguồn ứng dụng REST API
- `infra/`: File cấu hình Docker Compose, Vault, Postgres, TLS
- `tests/`: Kịch bản kiểm thử bảo mật & xoay vòng khóa
- `bench/`: Kịch bản & kết quả đo lường hiệu năng
- `docs/`: Báo cáo kỹ thuật và ảnh minh chứng
