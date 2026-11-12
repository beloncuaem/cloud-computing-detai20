# Đồ án Điện toán đám mây - Đề tài 20
**Chủ đề:** Bảo vệ dữ liệu bằng mã hóa, quản lý khóa và vòng đời bí mật

## Thành viên nhóm

| Vai trò | Thành viên | GitHub | Phụ trách chính |
|---|---|---|---|
| **Nhóm trưởng** — Tester / DevSecOps & Report | Bùi Ngô Anh Quang (SV3) | [`beloncuaem`](https://github.com/beloncuaem) | Kiểm thử T01–T16, CI `security-gate`, ruleset `main-1`, benchmark A/D-lab/E-lab, báo cáo kỹ thuật, kịch bản demo |
| Developer / Application & Automation | Nguyễn Minh Hiếu (SV2) | [`Hieu0408`](https://github.com/Hieu0408) | API FastAPI, mã hóa phong bì, script Vault (AppRole, rotate, rewrap, `min_decryption_version`), credential DB động |
| Infrastructure & Security | SV1 | [`hothienphu`](https://github.com/hothienphu) | Hạ tầng triển khai, TLS/mTLS, mã hóa volume (T13) |

Xem lịch sử đóng góp thực tế của từng thành viên: `git shortlog -sne --all`.

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
- `docs/`: báo cáo, ảnh bằng chứng, kế hoạch kiểm thử, hướng dẫn hạ tầng và kịch bản demo
- `docs/demo/`: kịch bản trình diễn trực tiếp 15–20 phút, phân công theo từng người
- `scripts/`: smoke test PowerShell
- `.github/workflows/`: CI security gate (Gitleaks + unit tests)

## Chạy nhanh bằng Docker (phương án dự phòng)
Stack này dùng Vault dev mode để kiểm thử trong lúc chờ hạ tầng Vault file storage + TLS của SV1. Không dùng cho production hoặc dữ liệu thật.

**Bắt buộc có `.env` ở gốc repo.** Từ PR #9, API key/admin key chỉ đọc từ môi trường: thiếu một trong hai thì `docker compose` thoát ngay, và API từ chối khởi động.

```powershell
Copy-Item .env.example .env
# Mở .env và điền hai khóa sinh mới, mỗi khóa một lệnh:
python -c "import secrets; print(secrets.token_urlsafe(32))"

docker compose up -d --build

# Nạp biến từ .env vào phiên hiện tại rồi chạy smoke test (9 điểm)
Get-Content .env | ForEach-Object { if ($_ -match '^([A-Z_]+)=(.*)$') { Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2] } }
./scripts/smoke-test.ps1
```

`.env` đã nằm trong `.gitignore`; không commit khóa thật. Nếu PowerShell chặn chạy script, cho phép script cục bộ trong riêng phiên hiện tại bằng `Set-ExecutionPolicy -Scope Process RemoteSigned` rồi chạy lại `./scripts/smoke-test.ps1`.

Dọn tài nguyên sau khi đo: `docker compose down -v` (xóa cả volume lab).

Chi tiết vận hành: `docs/infra/local-stack.md`. Kế hoạch kiểm thử T01–T16: `docs/testing/test-plan.md`. Hướng dẫn chạy trực tiếp trên Windows: `api/README_VI.md`. Kịch bản trình diễn trực tiếp: `docs/demo/kich-ban-demo-truc-tiep.md`.
