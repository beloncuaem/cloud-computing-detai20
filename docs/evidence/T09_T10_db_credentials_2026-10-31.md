# T09/T10 — Dynamic DB credentials, rotation và lease (31/10/2026)

Bản ghi terminal trên stack dự phòng. Cần chụp ảnh màn hình khi nộp.

## Thiết lập

- API chạy với `USE_VAULT_DB_CREDS=true`.
- `/ready` trả 200; PostgreSQL có role do Vault cấp (tên dạng `v-<identity>-app-role-...`).
- Vault role: `database/creds/app-role`, TTL 1h.

## T09 — Xoay credential DB dưới tải

- k6: 20 VUs, 1 phút, `mixed.js`.
- Sau 20 giây gọi `POST /admin/rotation/database` hai lần (một lần ở lần chạy đầu, một lần trong lần đo có CSV).
- Phản hồi: `{"status":"rotated", ... "new_lease_duration_seconds":3600, "previous_lease_duration_seconds":3600}`.

Kết quả k6:

```text
checks.........................: 100.00% 6399 out of 6399
http_req_duration.............: avg=187.44ms p(90)=233.87ms p(95)=250.52ms p(99)=284.43ms
http_req_failed...............: 0.00%   0 out of 6399
http_reqs.....................: 6399    106.41/s
```

Role động sau xoay (rút gọn):

```text
v-approle-app-role-... | 2026-10-31 14:15:38+00
v-approle-app-role-... | 2026-10-31 14:14:51+00
v-approle-app-role-... | 2026-10-31 14:13:33+00
```

Kết luận: không có lỗi trong cửa sổ xoay; pool mới dùng credential mới, pool cũ được giữ đến khi lease hết hạn.

## T10 — Gia hạn và thu hồi lease

```text
T10 username=v-token-app-role-...
T10 lease_id=database/creds/app-role/...
T10 lease_duration=3600
Login before revoke: <username>
Renew: lease_duration=1m, lease_renewable=true
Revoke: All revocation operations queued successfully!
Login after revoke: FATAL: role "<username>" does not exist
```

Kết luận: lease gia hạn được; sau khi thu hồi, credential không còn đăng nhập được.

## Ghi chú

- Tên role phụ thuộc danh tính gọi Vault (`v-approle-...` cho app, `v-token-...` cho root), nên truy vấn dùng `LIKE 'v-%app-role-%'`.
- Đây là kiểm thử chức năng ngắn (1 phút); số liệu H1/H2 chính thức vẫn cần chạy T14 với 10/50/100 VUs.
- Sau kiểm thử, API được đưa về `USE_VAULT_DB_CREDS=false` để khớp cấu hình mặc định của runbook.
