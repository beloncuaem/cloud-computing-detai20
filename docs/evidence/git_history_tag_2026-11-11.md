# Lịch sử Git 3 người đóng góp và tag nghiệm thu `v0.9.0-rc1` (11/11/2026)

Người ghi: SV3 — Bùi Ngô Anh Quang (`beloncuaem`). Bản ghi terminal chạy thật trên clone cục bộ ngày 11/11/2026, sau khi push nhánh `docs/report-sync-va-demo-script` (PR #10) và push tag.

## 1. Vì sao có biên bản này

Khung chấm điểm yêu cầu lịch sử Git thể hiện **đủ 3 thành viên đóng góp** và một **tag nghiệm thu**. Biên bản này ghi lại bằng chứng lệnh thật, giải thích một điểm dễ gây hiểu nhầm (4 tên hiển thị nhưng 3 người), và ghi rõ giới hạn về ảnh chụp màn hình.

## 2. Bản ghi terminal (nguyên văn)

```text
$ git shortlog -sne --all
    29	Bùi Ngô Anh Quang <anhquang24h123@gmail.com>
     4	Hieu0408 <hieunguyenn.006@gmail.com>
     3	Nguyen Minh Hieu <hieunguyenn.006@gmail.com>
     1	phu <hothienphufpt@gmail.com>

$ git log --all --format=%ae | sort | uniq -c
     29 anhquang24h123@gmail.com
      7 hieunguyenn.006@gmail.com
      1 hothienphufpt@gmail.com

$ git log --oneline --graph --decorate -12
* b333621 (HEAD -> docs/report-sync-va-demo-script, tag: v0.9.0-rc1, origin/docs/report-sync-va-demo-script) docs: đồng bộ báo cáo và bằng chứng tới 11/11, thêm kịch bản demo trực tiếp
* 8ad2e31 test(bench): đo bổ sung 6 lần chạy baseline A cho đủ 5 lần/mức VU
* 65721a0 fix(vault): bo keyword sai o generate_secret_id de vault-init hoan tat (D-09)
*   0ef9e6c (origin/main, origin/HEAD, main) Merge pull request #9 from beloncuaem/chore/externalize-api-keys
|\
| * 0dbf582 (origin/chore/externalize-api-keys, chore/externalize-api-keys) chore(security): require API_KEY and ADMIN_API_KEY from the environment
|/
*   28bd706 Merge pull request #8 from beloncuaem/student2-d01-d02-d03
|\
| * dc6a9f5 (origin/student2-d01-d02-d03) Sửa lại code api
| * b6ad654 feat(crypto): implement least privilege approle, secretid lifecycle, and dek rewrap (D-01, D-02, D-03)
|/
*   30dc813 Merge pull request #6 from beloncuaem/infra/fallback-compose
|\
| *   f598bbd (origin/infra/fallback-compose, infra/fallback-compose) chore: merge main to bring security-gate workflow into PR branch
| |\
| |/
|/|
* |   cd80c0d Merge pull request #7 from beloncuaem/sv1/t13-tls
|\ \
| * | 7654333 (origin/sv1/t13-tls) feat(infra): add docker-compose for Vault and PostgreSQL

$ git tag --list
v0.1
v0.9.0-rc1

$ git log -1 --format="HEAD %h %an %ad" --date=iso
HEAD b333621 Bùi Ngô Anh Quang 2026-11-11 21:09:15 +0700

$ git rev-list -n1 v0.9.0-rc1
b333621b67aaf4a589989a01aa2445e9ca73c642
```

## 3. Đọc kết quả: 4 tên hiển thị, 3 người thật

`git shortlog -sne --all` nhóm theo cặp (tên hiển thị, email), nên cho **4 dòng**. Nhóm theo email (`git log --all --format=%ae | sort | uniq -c`) cho **3 email** — đúng 3 thành viên:

| Thành viên | Vai trò | Email commit | Tên hiển thị đã dùng | Số commit |
|---|---|---|---|---:|
| Bùi Ngô Anh Quang (`beloncuaem`) | SV3 — Tester/DevSecOps, nhóm trưởng | `anhquang24h123@gmail.com` | Bùi Ngô Anh Quang | 29 |
| Nguyễn Minh Hiếu (`Hieu0408`) | SV2 — Dev & Automation | `hieunguyenn.006@gmail.com` | `Hieu0408` (4) và `Nguyen Minh Hieu` (3) | 7 |
| `hothienphu` | SV1 — Infra & Security | `hothienphufpt@gmail.com` | `phu` | 1 |

SV2 đã commit dưới hai tên hiển thị khác nhau nhưng **cùng một email**, nên vẫn là một người đóng góp. Đây là lỗi cấu hình `user.name` không nhất quán giữa các máy, **không** phải người thứ tư. Không viết lại lịch sử để gộp tên (thao tác phá hủy và không được yêu cầu); khuyến nghị các commit sau này của SV2 thống nhất một tên hiển thị. Số commit của SV1 còn ít (1) là phản ánh đúng thực tế đóng góp tới 11/11, không phải lỗi đếm.

## 4. Tag nghiệm thu

- Tag **`v0.9.0-rc1`** (annotated), đặt tại commit `b333621b67aaf4a589989a01aa2445e9ca73c642` — head nhánh `docs/report-sync-va-demo-script`, tức head của **PR #10** tại thời điểm nghiệm thu 11/11/2026. Đã push lên origin (`git push origin v0.9.0-rc1`).
- Tag **không** nằm trên `main` vì PR #10 chưa merge (ruleset `main-1` bắt buộc PR + 1 approval; owner không tự approve). Sau khi merge, trạng thái nghiệm thu trên `main` sẽ được đánh dấu bằng tag chính thức `v1.0.0` **chỉ khi** T13 đạt và D-05/D-08 được đóng hoặc chấp nhận rủi ro bằng văn bản (quy tắc mục 4.5 báo cáo). Không di chuyển tag `v0.9.0-rc1` sau khi đã push.
- Nội dung thông điệp tag (nguyên văn):

```text
v0.9.0-rc1 — bản nghiệm thu release candidate (11/11/2026)

Đạt: T01–T05, T07, T09–T12, T16; T06/T08 nghiệm thu 05/11 và tái kiểm
chứng độc lập 11/11; defect D-09 đóng; A đủ 5 lần chạy/mức VU.
Chưa đạt: T13 (lab chưa có TLS và mã hóa volume); D-05 và D-08 còn mở.

Không phải v1.0.0: chỉ gắn v1.0.0 khi T13 đạt và D-05/D-08 được đóng
hoặc được chấp nhận rủi ro bằng văn bản (quy tắc ở mục 4.5 báo cáo).

Tag đặt trên head nhánh docs/report-sync-va-demo-script (PR #10) tại
thời điểm nghiệm thu 11/11/2026, commit b333621.
```

- Tag cũ `v0.1` giữ nguyên làm mốc lịch sử, không xóa.

## 5. Giới hạn: chưa có ảnh chụp màn hình thật

Đã thử chụp màn hình thật từ phiên làm việc tự động: mở một cửa sổ PowerShell phóng to toàn màn hình chạy các lệnh trên rồi chụp toàn màn hình. Kết quả kiểm tra cho thấy mặt bàn mà phiên tự động chụp được **không có cửa sổ nào** (`EnumWindows` trả về 0 cửa sổ visible; ảnh chụp chỉ có hình nền), nên cửa sổ terminal mở từ phiên này không hiện lên đó. Ảnh chỉ-có-hình-nền đã **xóa, không commit**, vì không chứng minh được điều gì.

Vì vậy bằng chứng lịch sử Git hiện là **bản ghi terminal ở mục 2** (đúng quy ước các biên bản khác trong thư mục này). Ảnh chụp màn hình thật vẫn là mục còn mở trong `README.md` của thư mục bằng chứng: thành viên nào ngồi trước máy hãy mở PowerShell tại gốc repo, chạy đúng các lệnh mục 2 và chụp lại, đặt tên `git_log_3_authors.png`.

## 6. Tái lập

```powershell
git shortlog -sne --all
git log --all --format='%ae' | sort | uniq -c
git log --oneline --graph --decorate -12
git tag --list
git rev-list -n1 v0.9.0-rc1
```
