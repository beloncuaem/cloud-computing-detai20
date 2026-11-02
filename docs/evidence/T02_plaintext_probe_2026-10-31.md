# T02 — Không có plaintext trong DB, dump, log và image (31/10/2026)

Bản ghi terminal. Giá trị dò là dữ liệu giả, sinh ngẫu nhiên theo thời gian.

```text
T02 probe=t02-1793457643-0901234567
time=2026-10-31T21:40:43+07:00
--- POST ---
{"id":"ab7e8e21-4af0-4ddc-be8b-95eddb078f8a","record_type":"plaintext_probe","status":"encrypted_and_stored","created_at":"2026-10-31T14:40:43.851681Z"}
id=ab7e8e21-4af0-4ddc-be8b-95eddb078f8a
--- DB count ---
0
--- dump count ---
0
--- API files count ---
0
--- image count ---
0
--- cleanup ---
DELETE 1
DELETE 1
done=2026-10-31T21:40:51+07:00
```

## Cách kiểm tra

1. Tạo bản ghi qua API với giá trị dò duy nhất `t02-...-0901234567`.
2. Tìm chuỗi trong `sensitive_records` (ciphertext + encrypted_dek).
3. `pg_dump` toàn bộ database rồi `grep -a -c`.
4. `grep` trong `/app` và `/tmp` của container API.
5. `grep` trong `/app` của image `detai20-api:local` (không mount volume dữ liệu).
6. Xóa bản ghi và audit event của ca test.

## Kết luận

Cả bốn vị trí đều trả `0`: không có plaintext trong bảng, dump, file/log container hay image. **T02 ĐẠT.** Giá trị dò không trùng fixture `0901234567` trong `tests/`, nên kết quả 0 không phải do thiếu dữ liệu mẫu. Bản ghi test đã được xóa sau khi đo.

## Ảnh cần chụp bổ sung

- Bốn kết quả `0` và hai dòng `DELETE 1`.

