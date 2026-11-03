# T15 — Dọn tài nguyên và tái lập từ clone sạch (31/10/2026)

**Mục tiêu:** chứng minh stack dựng lại được từ repo, smoke test chạy qua, và dọn sạch tài nguyên sau khi đo.

**Phạm vi:** nhánh `infra/fallback-compose` tại commit `03adad2` (PR #6 chưa merge vào `main`). Vì vậy kết quả chứng minh nhánh dự phòng tái lập được, **chưa** chứng minh `main` tái lập được cho đến khi PR #6 merge.

## 1. Dọn stack cũ

```text
$ docker compose down -v --remove-orphans
 Container detai20-api-1 Removed
 Container detai20-vault-audit-1 Removed
 Container detai20-vault-init-1 Removed
 Container detai20-postgres-1 Removed
 Container detai20-vault-1 Removed
 Network detai20_default Removed
 Volume detai20_approle Removed
 Volume detai20_pgdata Removed

$ docker image rm detai20-api:local
Untagged: detai20-api:local
```

## 2. Clone sạch và dựng lại

```text
$ git clone --branch infra/fallback-compose --single-branch <repo> /c/tmp/detai20-repro-hcGCPf/repo
$ git rev-parse --short HEAD
03adad2

$ docker compose up -d --build
 Image detai20-api:local Built
 Container detai20-postgres-1 Healthy
 Container detai20-vault-1 Healthy
 Container detai20-vault-init-1 Exited (0)
 Container detai20-api-1 Started
ready=1 elapsed_seconds=24
```

Thời gian 24 giây tính từ lúc bắt đầu `up` đến khi `/ready` trả 200. Máy đã có sẵn base image `python:3.12-slim`, `postgres:16-alpine`, `hashicorp/vault:1.20` và build cache; trên máy mới sẽ lâu hơn do phải tải image.

## 3. Smoke test

```text
PASS  health endpoint
PASS  ready endpoint (DB + Vault)
PASS  create encrypted record
PASS  read back plaintext
PASS  metadata exposes ciphertext size
PASS  missing API key rejected
PASS  wrong API key rejected
PASS  record key cannot call admin
PASS  plaintext absent from database
smoke_exit=0
```

9/9 kiểm tra đạt, gồm cả kiểm tra không có plaintext trong PostgreSQL.

## 4. Dọn sau đo

```text
$ docker compose down -v --remove-orphans
 Network detai20_default Removed
 Volume detai20_pgdata Removed
 Volume detai20_approle Removed

remaining detai20 containers: (none)
remaining detai20 volumes: (none)

$ docker system df
TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE
Images          8         1         2.233GB   1.585GB (70%)
Containers      1         0         16.38kB   16.38kB (100%)
Local Volumes   4         0         0B        0B
Build Cache     38        0         992.3MB   344.3MB
```

Không còn container hay volume mang tên `detai20`. Image `detai20-api:local` được dựng lại phục vụ smoke test và vẫn còn trong cache; muốn xóa hoàn toàn dùng `docker image rm detai20-api:local` và `docker builder prune`.

## 5. Chi phí

- Toàn bộ chạy cục bộ trên máy cá nhân, **không phát sinh chi phí cloud**.
- Dung lượng sau đo: image 2,233 GB (1,585 GB reclaimable), build cache 992,3 MB (344,3 MB reclaimable), volume 0 B.
- Thời gian dựng lại: 24 giây với cache; smoke test 3 giây.

## 6. Kế hoạch khi mất khóa

Đã trình bày ở mục 5.1 của báo cáo: Vault dev mode lưu khóa trong RAM, mất container là mất KEK; với production phải dùng Shamir shares/auto-unseal, backup và quy trình `min_decryption_version`/rewrap (D-03). Trong lab, dữ liệu mã hóa cũ không thể giải mã sau khi Vault mất trạng thái — đây là giới hạn được ghi nhận, không phải sự cố cần khắc phục.

## 7. Kết luận

**T15 ĐẠT trong phạm vi nhánh dự phòng.** Có thể dựng lại, kiểm tra và dọn sạch bằng lệnh trong repo. Chưa thể tuyên bố `main` tái lập được vì PR #6 đang chờ approval.
