# Đề tài 20 — Mã nguồn Sinh viên 2 (PostgreSQL cài trực tiếp trên Windows)

Bộ này **không dùng Docker**. PostgreSQL chạy trực tiếp trên Windows; FastAPI chạy bằng Python trong VS Code; Vault chạy riêng bằng `vault.exe` trên máy local.

## 1. Cấu trúc thư mục

```text
student2_project_windows/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── security.py
│   ├── routes/
│   │   ├── records.py
│   │   └── admin.py
│   └── services/
│       ├── encryption.py
│       └── vault_client.py
├── scripts/
│   ├── setup_vault.py
│   ├── rotate_dek.py
│   └── rotate_transit_key.py
├── sql/
│   ├── 00-create-roles.sql
│   └── 01-schema.sql
├── tests/
│   └── test_encryption_unit.py
├── .env.example
├── requirements.txt
└── README_VI.md
```

## 2. Tạo role và bảng trong PostgreSQL

1. Mở VS Code SQLTools hoặc pgAdmin và kết nối bằng tài khoản quản trị PostgreSQL, thường là `postgres`.
2. Mở `sql/00-create-roles.sql`, chạy khi kết nối vào `encryption_db` hoặc `postgres`. File tạo `app_user` và `vault_admin` nếu chưa có. **Đây là cấu hình demo cục bộ**; `vault_admin` được cấp SUPERUSER để đơn giản hóa thử nghiệm Vault Database Secrets Engine. Không dùng thiết kế quyền này cho môi trường thật.
3. Chuyển kết nối sang database `encryption_db`.
4. Mở `sql/01-schema.sql` và chạy để tạo hai bảng `sensitive_records`, `audit_events`.
5. Nếu bạn đã tạo hai bảng rồi thì chạy lại vẫn được vì có `CREATE TABLE IF NOT EXISTS`.

Mật khẩu mặc định trong SQL phải khớp với các giá trị tương ứng trong `.env`. Đổi mật khẩu nếu cần.

## 3. Cấu hình và cài Python

Trong Terminal PowerShell ở thư mục gốc của dự án:

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Mở `.env` và kiểm tra ít nhất:

```dotenv
DATABASE_URL=postgresql+psycopg://app_user:local_app_password@localhost:5432/encryption_db
USE_VAULT_DB_CREDS=false
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=encryption_db
VAULT_ADDR=http://127.0.0.1:8200
VAULT_SETUP_TOKEN=root
VAULT_APPROLE_FILE=./vault-credentials.json
VAULT_DB_ADMIN_USER=vault_admin
VAULT_DB_ADMIN_PASSWORD=local_vault_admin_password
```

`DATABASE_URL` phải có username/password đúng với role PostgreSQL. `USE_VAULT_DB_CREDS=false` giúp app dùng tài khoản `app_user` trong giai đoạn đầu; Vault vẫn được dùng để sinh/bọc DEK và giải mã DEK.

## 4. Khởi động Vault trực tiếp trên Windows

Cài Vault CLI cho Windows từ trang chính thức: https://developer.hashicorp.com/vault/install

Mở **Terminal 1** (giữ terminal này mở) và chạy:

```powershell
vault server -dev -dev-root-token-id=root
```

Đây là chế độ dev chỉ để học/demo trên máy cá nhân. Dữ liệu/key của dev server thường không bền khi dừng server. Không mở cổng ra mạng, không dùng chế độ này trong môi trường thật.

Nếu lệnh `vault` không được nhận diện, mở terminal tại thư mục chứa `vault.exe` hoặc thêm thư mục đó vào PATH.

## 5. Cấu hình Vault cho ứng dụng

Mở **Terminal 2** ở thư mục gốc dự án; kích hoạt `.venv` nếu chưa làm. Kiểm tra `.env` có `VAULT_SETUP_TOKEN=root` và Vault đang chạy ở `127.0.0.1:8200`, rồi thực hiện:

```powershell
python scripts/setup_vault.py
```

Script tạo Transit key, cấu hình Database Secrets Engine và AppRole; sau đó tạo `vault-credentials.json`. Ứng dụng sử dụng AppRole trong file này, không dùng token setup/root.

Nếu script báo lỗi đăng nhập PostgreSQL, kiểm tra `vault_admin` đã tồn tại và `VAULT_DB_ADMIN_PASSWORD` khớp chính xác với mật khẩu trong `sql/00-create-roles.sql`. Nếu báo lỗi Vault, kiểm tra Terminal 1 còn chạy và địa chỉ `VAULT_ADDR` đúng.

## 6. Khởi động ứng dụng Python

Vẫn ở thư mục gốc, với `.venv` đã kích hoạt:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Mở các địa chỉ:
- API docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health
- Readiness (cần cả PostgreSQL và Vault): http://127.0.0.1:8000/ready

Trong Swagger, gọi `POST /records` với header `X-API-Key` (giá trị ở `.env`, mặc định `local-demo-api-key-change-me`) và body:

```json
{
  "record_type": "customer_phone",
  "value": "0901234567"
}
```

Sau đó lấy ID trả về và gọi `GET /records/{record_id}`. Để kiểm tra PostgreSQL, chạy trong SQLTools khi kết nối `encryption_db`:

```sql
SELECT id, record_type, encode(ciphertext, 'base64') AS ciphertext_base64,
       encrypted_dek, kek_name, kek_version, created_at
FROM sensitive_records;
```

## 7. Xoay vòng khóa

Giữ PostgreSQL và Vault chạy. Mở Terminal khác tại thư mục gốc, kích hoạt `.venv`:

```powershell
python scripts/rotate_transit_key.py
python scripts/rotate_dek.py
```

Lệnh đầu tạo phiên bản KEK mới; không tự tạo DEK mới hay mã hóa lại dữ liệu cũ. Lệnh thứ hai tạo DEK mới và mã hóa lại các bản ghi đã lưu.

Để thử xoay vòng database credentials của Vault, trước tiên hãy kiểm tra endpoint Database Secrets Engine hoạt động. Sau đó đặt `USE_VAULT_DB_CREDS=true` trong `.env`, khởi động lại FastAPI và thử `POST /admin/rotation/database` với header `X-Admin-Key`. Nếu chưa cần phần nâng cao, để `false` để app dùng `app_user` cố định.

## 8. Unit test và Git

```powershell
python -m pytest -q
```

Không commit `.env`, `vault-credentials.json`, mật khẩu, token hay bất kỳ secret nào vào Git. Đổi các giá trị demo trước khi chia sẻ.

## Giới hạn và lưu ý bảo mật

- Vault dev mode dùng cho học tập; khi tắt server có thể mất cấu hình/khóa. Chạy lại `setup_vault.py` nếu cần dựng lại môi trường dev.
- Cấu hình PostgreSQL `vault_admin` trong file SQL được cấp SUPERUSER để giảm khó khăn khi thực hành plugin dynamic database. Đây là quyền quá rộng đối với hệ thống thật; production phải dùng quyền tối thiểu.
- TLS chưa được thiết lập trong hướng dẫn local này. Không dùng các endpoint/secret demo ở môi trường thật.
- Zero-downtime phải được chứng minh bằng kiểm thử tải khi xoay vòng; một request thành công không đủ chứng minh.
