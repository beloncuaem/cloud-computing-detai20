# KỊCH BẢN THUYẾT TRÌNH — ĐỀ TÀI 20

**Bảo vệ dữ liệu bằng mã hóa, quản lý khóa và vòng đời bí mật**

- **Hình thức:** thuyết trình trực tiếp bằng slide (UTH theme), **không dùng video**. Demo chạy thật trên máy ở slide 18.
- **Thời lượng:** 15 phút (900 giây), chưa gồm Q&A. Demo trực tiếp chiếm ~4 phút (240 giây).
- **Người trình bày:**
  - **SV1 — Hồ Thiên Phú (MSSV 052205010238):** hạ tầng, TLS, ranh giới bảo mật (slide 5–8); giải thích phía Vault trong demo.
  - **SV2 — Nguyễn Minh Hiếu (MSSV 075206006264):** vòng đời bí mật, envelope, credential động, DevSecOps (slide 9–12); thao tác demo; rủi ro còn lại (slide 19).
  - **SV3 — Bùi Ngô Anh Quang (MSSV 066206019831):** mở đầu, thiết kế đo, kết quả, kết luận (slide 1–4, 13–17, 20); đọc số liệu trong demo; điều phối chung.
- **Slide:** `docs/slides/de-tai-20.pptx` (20 slide). Ghi chú người nói đã nhúng trong notes từng slide.
- **Demo gốc:** `docs/demo/kich-ban-demo-truc-tiep.md` (bản đầy đủ 15–20 phút). Ở đây rút gọn còn ~4 phút theo mục 3 bên dưới.

---

## 1. Bảng phân công và thời lượng

| Slide | Nội dung | Người nói | Thời lượng |
|---:|---|---|---:|
| 1 | Mở đầu, giới thiệu đề tài | SV3 | 0:30 |
| 2 | Nội dung và phân công | SV3 | 0:20 |
| 3 | Vấn đề: mã hóa chưa đủ nếu khóa quản lý sai | SV3 | 0:35 |
| 4 | Mục tiêu và phạm vi | SV3 | 0:30 |
| 5 | Ba trạng thái dữ liệu và lớp bảo vệ | SV1 | 0:35 |
| 6 | Mã hóa phong bì: DEK và KEK | SV1 | 0:40 |
| 7 | Kiến trúc lab: TLS kết thúc tại nginx | SV1 | 0:40 |
| 8 | Ranh giới bảo mật và least privilege | SV1 | 0:35 |
| 9 | Vòng đời bí mật 5 bước | SV2 | 0:35 |
| 10 | Hiện thực envelope trong API | SV2 | 0:35 |
| 11 | Credential động không gián đoạn | SV2 | 0:35 |
| 12 | DevSecOps: chặn secret từ CI | SV2 | 0:35 |
| 13 | Thiết kế đo lường | SV3 | 0:35 |
| 14 | Kết quả kiểm thử T01–T16 | SV3 | 0:40 |
| 15 | Hiệu năng qua TLS (bảng) | SV3 | 0:40 |
| 16 | H1 và H2: kết luận thẳng thắn | SV3 | 0:40 |
| 17 | T13: TLS thật, at-rest chấp nhận rủi ro | SV3 | 0:35 |
| 18 | **DEMO TRỰC TIẾP** | SV2 thao tác, SV1+SV3 thuyết minh | 4:00 |
| 19 | Rủi ro còn lại và hướng phát triển | SV2 | 0:35 |
| 20 | Kết luận — cảm ơn và Q&A | SV3 | 0:30 |
| | **Tổng** | | **15:00** |

---

## 2. Lời nói từng slide

### Slide 1 — Mở đầu (SV3, 0:30)
"Kính chào thầy/cô và các bạn. Nhóm em gồm ba thành viên: Thiên Phú, Minh Hiếu và Anh Quang, xin trình bày **Đề tài 20: Bảo vệ dữ liệu bằng mã hóa, quản lý khóa và vòng đời bí mật**. Câu hỏi xuyên suốt của đồ án là: *mã hóa chỉ có ý nghĩa bảo vệ đến đâu nếu khóa, secret ứng dụng và quyền giải mã không được quản lý tách biệt?* Nhóm em trả lời bằng một nguyên mẫu chạy thật, đo thật và demo trực tiếp hôm nay."

### Slide 2 — Nội dung và phân công (SV3, 0:20)
"Bài gồm sáu phần: vấn đề và mục tiêu; nền tảng lý thuyết; kiến trúc và hạ tầng của Thiên Phú; hiện thực envelope và vòng đời bí mật của Minh Hiếu; đo lường và DevSecOps của Anh Quang; cuối cùng là demo trực tiếp khoảng 4 phút và kết luận. Tổng thời gian khoảng 15 phút, chưa gồm hỏi đáp."

### Slide 3 — Vấn đề (SV3, 0:35)
"Nhiều hệ thống vẫn mã hóa dữ liệu nhưng để khóa ngay cạnh dữ liệu: khóa hard-code trong mã nguồn, mật khẩu DB tĩnh trong file cấu hình, một tài khoản vừa ghi vừa giải mã vừa quản trị. Khi đó đọc được database hoặc đọc được repo là đọc được tất cả — mã hóa trở thành hình thức. Bốn lỗ hổng quản lý khóa và secret này chính là thứ đồ án nhắm tới, và là lý do nhóm chọn **mã hóa phong bì** tách khóa khỏi dữ liệu."

### Slide 4 — Mục tiêu và phạm vi (SV3, 0:30)
"Sáu mục tiêu: envelope AES-256-GCM với KEK trong Vault; credential DB cấp động; workload identity AppRole; xoay vòng KEK và credential không gián đoạn; kiểm chứng bằng 16 ca kiểm thử T01–T16; và đo tải k6. Phạm vi là lab Docker Desktop trên một máy với dữ liệu giả; demo trực tiếp, không video. Nhóm em **không** tuyên bố đây là giải pháp production."

### Slide 5 — Ba trạng thái dữ liệu (SV1, 0:35)
"Dữ liệu cần bảo vệ ở ba trạng thái: at-rest trên đĩa, in-transit trên đường truyền, và in-use khi xử lý. Đồ án tập trung lớp in-use bằng envelope và phủ TLS cho các biên client–server và API–database. Riêng at-rest cấp volume, do BitLocker trên máy cá nhân đang tắt, nhóm em **chấp nhận rủi ro bằng văn bản** thay vì tự bật — sẽ nói rõ ở slide 17."

### Slide 6 — Mã hóa phong bì (SV1, 0:40)
"Mỗi bản ghi có một **DEK 256-bit riêng**, sinh bởi Vault Transit; DEK được bọc bởi **KEK** nằm trong Vault và không bao giờ export ra ngoài. Database chỉ lưu ciphertext và DEK đã bọc, không có cột plaintext. **AAD** gắn `record_id:record_type` để chống tráo payload giữa các bản ghi. Nhờ tách DEK/KEK, xoay KEK không phải giải mã lại toàn bộ dữ liệu — chỉ rewrap lớp vỏ."

### Slide 7 — Kiến trúc lab, TLS tại nginx (SV1, 0:40)
"Đây là kiến trúc lab: **nginx kết thúc TLS** ở biên, chuyển 8200 về Vault, 8443 về API, 8444 về baseline. Vault chạy dev mode HTTP trong mạng Docker nội bộ một máy; PostgreSQL bật `ssl=on`; API chạy 2 Uvicorn worker với pool 20+20. Chứng chỉ lab tự ký sinh bằng `gen-certs.sh`. Mọi kênh client–server và API–database đều qua TLS thật, không còn plaintext ở biên."

### Slide 8 — Ranh giới bảo mật, least privilege (SV1, 0:35)
"AppRole của ứng dụng chỉ chạm đúng bốn path cần thiết và bị deny các path quản trị; operator giữ quyền xoay khóa và **không** mount vào API. SecretID TTL 10 phút, dùng một lần. Admin key chỉ đọc từ biến môi trường. Kết quả là một tài khoản bị lộ cũng không tự xoay khóa hay đọc secret khác được — tách nhiệm vụ thật, không chỉ trên giấy."

### Slide 9 — Vòng đời bí mật 5 bước (SV2, 0:35)
"Vòng đời bí mật gồm năm bước: cấp phát, sử dụng, xoay vòng, thu hồi, hủy. Điểm đáng nhớ: credential DB mới phải được **kiểm tra SELECT 1 trước khi đổi pool**, và mọi thao tác đều để lại audit trail. Khi lộ, thu hồi lease và hủy SecretID ngay. Vòng đời khép kín này là thứ khiến 'quản lý khóa' khác với 'có khóa'."

### Slide 10 — Hiện thực envelope trong API (SV2, 0:35)
"Trong API, mỗi lần ghi gọi `transit/datakey` bits=256, nonce 12 byte từ `os.urandom`, mã hóa AES-256-GCM kèm AAD. Không lưu plaintext DEK; schema không có cột plaintext. Mỗi lần đọc gọi `transit/decrypt` để mở DEK rồi giải mã payload. Lỗi giải mã trả 4xx/5xx có kiểm soát, không rò rỉ thông tin khóa."

### Slide 11 — Credential động không gián đoạn (SV2, 0:35)
"Credential PostgreSQL do Vault Database engine cấp động theo lease. Khi xoay, engine mới được kiểm tra trước khi nhận tải; pool cũ giữ đến hết lease rồi mới dispose, nên không có cửa sổ 502/503. Ca T09 ghi nhận **6.399 request, 0 lỗi** khi xoay credential ở giây 20 — bằng chứng xoay vòng không gián đoạn."

### Slide 12 — DevSecOps (SV2, 0:35)
"Lớp DevSecOps chặn secret từ sớm: gitleaks quét trong CI, ruleset `main-1` bắt buộc PR + approval + hai check xanh. Cảnh báo ngưỡng hơn 200 lượt decrypt trong 60 giây đọc từ audit trail. Smoke test 9 điểm, gồm truy vấn thẳng PostgreSQL để chứng minh không còn plaintext. Bảo mật được kiểm soát bằng quy trình, không bằng lời hứa."

### Slide 13 — Thiết kế đo lường (SV3, 0:35)
"Đo bằng k6 constant-vus trên bốn cấu hình qua TLS: **B** baseline plaintext, **D** envelope, **D'** envelope + cache DEK 120 giây, **E** envelope + xoay vòng. Mỗi cấu hình 5 lần × 3 phút ở 10/50/100 VUs, lấy trung vị p95. Cấu hình **C** (at-rest) không đo vì BitLocker Off và đã risk-accepted. Ma trận này tách bạch chi phí mã hóa và lợi ích cache."

### Slide 14 — Kết quả T01–T16 (SV3, 0:40)
"16 ca kiểm thử: 15 ca ĐẠT, riêng T13 đạt phần TLS và chấp nhận rủi ro at-rest có văn bản. T06/T08 chứng minh least privilege và xoay vòng đủ 7 bước; T15 xác nhận tái lập từ `main` sạch; T16 bắt burst trong 0,4 giây. Mỗi ca ĐẠT đều kèm lệnh tái lập chạy được, không chỉ kết luận suông."

### Slide 15 — Hiệu năng qua TLS (SV3, 0:40)
"Bảng này là trung vị 5 lần chạy cho bốn cấu hình ở ba mức tải. So **B với D** để thấy overhead của envelope; so **D với D'** để thấy lợi ích cache DEK; đối chiếu cột lỗi để thấy xoay vòng ở E không gây lỗi. Mức nào sụp bão hòa được đánh dấu và không dùng tính H1. Số liệu đo trên một máy, không suy diễn production."

### Slide 16 — H1 và H2 (SV3, 0:40)
"Kết luận thẳng thắn theo ngưỡng đã đặt. **H1 — overhead p95 ≤ 30%: đạt một phần.** Overhead đo được của D so với B là +30,95% ở 10 VUs và +25,29% ở 50 VUs; với D' còn +37,90% và +26,26%. **H2 — lỗi < 0,1% khi xoay: đạt.** Cache DEK cho lợi ích rõ: so với D, D' thay đổi p95 +5,30% ở 10 VUs, p95 +0,77% ở 50 VUs, p95 -1,29% ở 100 VUs. Nhóm em không tuyên bố production từ số liệu một máy."

### Slide 17 — T13: TLS thật, at-rest risk-accepted (SV3, 0:35)
"Chứng từ T13: `curl -k` qua nginx trả 200; `openssl s_client` thương lượng TLSv1.2 và TLSv1.3; PostgreSQL `SHOW ssl` = on và `pg_stat_ssl` ghi nhận connection TLS từ API. BitLocker Off nên at-rest được **chấp nhận rủi ro bằng văn bản**, không đo C. Chứng từ lưu tại `docs/evidence/T13_2026-11-16.md`. Giới hạn còn lại: cert tự ký và đoạn nội bộ nginx→Vault vẫn HTTP trong mạng một máy."

### Slide 18 — DEMO TRỰC TIẾP (SV2 thao tác, SV1+SV3 thuyết minh, 4:00)
Xem mục 3 bên dưới. Chuyển sang màn hình terminal + slide demo; chạy thật, không video.

### Slide 19 — Rủi ro còn lại, hướng phát triển (SV2, 0:35)
"Rủi ro còn lại của lab: Vault dev mode một nút, plaintext DEK trong RAM khi cache, rotation process-local, chưa backup tự động. Hướng phát triển: Vault file storage + HA, mTLS nội bộ, HSM cho KEK, và đưa tái lập vào CI. Nhóm em nêu rõ giới hạn để kết luận đúng phạm vi đo."

### Slide 20 — Kết luận, cảm ơn, Q&A (SV3, 0:30)
"Thông điệp chính: **mã hóa chỉ có giá trị khi khóa và quyền giải mã tách khỏi dữ liệu.** Đồ án đạt 15/16 ca, T13 risk-accepted minh bạch; tag `v1.0.0` chỉ gắn khi đủ điều kiện nghiệm thu. Nhóm em cảm ơn thầy/cô và các bạn đã lắng nghe, và sẵn sàng trả lời câu hỏi."

---

## 3. Demo trực tiếp rút gọn (~4 phút, slide 18)

Nối từ `docs/demo/kich-ban-demo-truc-tiep.md`, rút còn 4 cảnh. **Điều kiện tiên quyết:** stack đã dựng, smoke 9/9 đã chạy trước giờ demo (mục 2 của kịch bản demo); nếu smoke hỏng thì KHÔNG demo.

| Thời điểm | Cảnh | Người | Lệnh / thao tác | Điểm chốt |
|---|---|---|---|---|
| 0:00–0:40 | Luồng bình thường + T02 | SV2 | create → read qua `https://…:8443`; rồi `pg_dump` bảng bản ghi | ciphertext trong DB, không plaintext; SV3 đọc kết quả |
| 0:40–1:40 | Least privilege T06 | SV2 | `check_approle_privileges.py`; thử xoay KEK bằng danh tính app | 9/9 PASS; rotate → **403**; SV1 giải thích ma trận quyền |
| 1:40–3:00 | Xoay vòng T08/T09 | SV2 chạy, SV3 giải thích | operator xoay KEK → đọc bản ghi cũ → rewrap → chặn version cũ; xoay credential DB giữa tải k6 | đọc cũ OK trước rewrap, ciphertext v1 bị từ chối sau; **0 lỗi** khi xoay |
| 3:00–4:00 | Burst T16 + số liệu | SV3 | burst 200 decrypt; mở bảng audit | cảnh báo burst bắt trong ~0,4 s; chốt H2 |

**Phương án dự phòng:** nếu Vault/API hỏng giữa demo, chuyển sang ảnh chụp chứng từ trong `docs/evidence/` và nói rõ "đây là chứng từ đã chạy, không phải chạy live"; không cố sửa trước mặt giảng viên quá 30 giây.

**Dọn sau demo (SV1):** gỡ CA lab khỏi store người dùng, `docker compose down` (giữ volume), theo mục 7 kịch bản demo.

---

## 4. Q&A dự kiến

1. **Vì sao không bật BitLocker để đo C?** — Máy cá nhân, bật BitLocker ảnh hưởng dữ liệu người dùng ngoài phạm vi đồ án; nhóm chọn risk-accepted có văn bản thay vì tự thay đổi máy. At-rest vẫn được nêu là giới hạn còn lại.
2. **Overhead envelope có chấp nhận được không?** — Đọc đúng bảng slide 15/16: overhead p95 của D so với B và mức giảm khi dùng D'. Kết luận theo ngưỡng 30%, mức bão hòa bị loại. Không tuyên bố production.
3. **Cache DEK có làm lộ khóa không?** — DEK plaintext chỉ trong RAM có TTL 120 s và giới hạn số entry; đánh đổi với cửa sổ plaintext trong bộ nhớ được nêu ở mục rủi ro. KEK không bao giờ rời Vault.
4. **Xoay KEK có phải giải mã lại toàn bộ dữ liệu?** — Không; chỉ rewrap DEK (T08 đủ 7 bước). Payload không bị giải mã trong quá trình rewrap.
5. **Vault dev mode có an toàn cho production?** — Không; đây là lab. Hướng phát triển là file storage + HA + mTLS + HSM. Nhóm nêu rõ giới hạn.
6. **Vì sao số liệu một máy vẫn có giá trị?** — Để so sánh tương đối giữa các cấu hình trên cùng phần cứng, cùng DB; không dùng để suy diễn tuyệt đối. Mọi ca ĐẠT kèm lệnh tái lập.
7. **SecretID dùng một lần thì API restart thế nào?** — Mỗi lần restart phải cấp SecretID mới bằng danh tính operator (D-02); kịch bản demo có bước này ở mục 2(d).

---

## 5. Ghi chú điều phối

- SV3 giữ đồng hồ; nếu vượt 15 phút, cắt slide 14 còn 20 giây và gộp slide 19 vào 20.
- Chuyển người nói bằng câu nối cuối mỗi slide ("Phần hạ tầng xin nhường cho Thiên Phú", …) để không chết thời gian.
- Demo là phần dễ tràn giờ nhất: bấm giờ riêng 4 phút, quá 4 phút thì bỏ cảnh burst và chốt bằng chứng từ.
- Không đọc nguyên văn slide; lời nói ở mục 2 là ý chính, diễn đạt tự nhiên.