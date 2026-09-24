# Đặc tả SSD (System Sequence Diagram) — CSMS

> **SSD là gì trong tài liệu này**: sơ đồ tuần tự actor ↔ hệ thống, chỉ vẽ *thao
> tác nào gọi cái gì, theo thứ tự nào, ai chịu trách nhiệm quyết định gì* — không
> vẽ chi tiết nội bộ class. Mỗi SSD đi kèm **bảng ràng buộc** lấy thẳng từ AC/NFR
> trong backlog của bạn, để AI vide code không được tự suy diễn khác đi.
>
> Nếu bạn dùng "SSD" với nghĩa khác (ví dụ Solution Structure Document), nói tôi
> biết để chỉnh lại định dạng — nhưng nội dung ràng buộc bên dưới vẫn dùng được.

Áp dụng cho 6 luồng lõi, ưu tiên đúng thứ tự sprint 1–5 trong backlog (Ready/Next
tier). Các epic Later (đặt chỗ, phân bổ công suất, đối soát) làm SSD theo đúng
mẫu này khi tới sprint tương ứng.

---

## SSD-1. Đăng nhập (S-02)

```mermaid
sequenceDiagram
    actor U as Người dùng
    participant API as POST /auth/login
    participant DB as users

    U->>API: email, password
    API->>DB: tìm user theo email
    alt sai thông tin
        API-->>U: 401 "email hoặc mật khẩu không đúng" (KHÔNG nói rõ email tồn tại hay không)
        API->>DB: +1 số lần sai (theo tài khoản VÀ theo IP)
    else đúng thông tin, chưa bị khoá
        API->>DB: tạo phiên, reset số lần sai
        API-->>U: 200 + cookie httpOnly, chuyển trang theo vai trò
    else đã sai ≥5 lần liên tiếp
        API-->>U: 401 "tài khoản tạm khoá 15 phút" (dù lần này nhập đúng)
    end
```

**Ràng buộc bắt buộc:**
- Đếm sai lưu ở DB (cột trên `users`), **không** lưu biến trong tiến trình.
- Thông báo lỗi sai mật khẩu và sai email phải **giống hệt nhau**.
- Mọi API khác: phiên hết hạn → 401 + chuyển về trang đăng nhập.

---

## SSD-2. Trụ sạc kết nối OCPP + BootNotification (S-06, S-08, T-12, T-13, T-16, T-17)

```mermaid
sequenceDiagram
    participant CP as Trụ sạc (WebSocket client)
    participant GW as WS Gateway /ocpp/{code}
    participant DB as charge_points

    CP->>GW: mở WebSocket, subprotocol "ocpp1.6"
    GW->>DB: tra mã trụ trong đường dẫn
    alt mã không tồn tại
        GW-->>CP: đóng kết nối ngay
        GW->>GW: log CẢNH BÁO (mã lạ + IP), không lộ lý do cho trụ
    else mã hợp lệ, đã có kết nối cũ cùng mã
        GW->>GW: đóng kết nối CŨ trước, giữ kết nối MỚI
        GW-->>CP: chấp nhận kết nối
    else mã hợp lệ, chưa có kết nối
        GW-->>CP: chấp nhận, giữ mở
    end

    CP->>GW: CALL BootNotification (vendor, model, firmware)
    alt trạm bị khoá bởi quản trị viên
        GW-->>CP: CALLRESULT Rejected
    else bình thường
        GW->>DB: lưu vendor/model/firmware, đánh dấu trực tuyến
        GW-->>CP: CALLRESULT Accepted, currentTime (UTC), interval=<cấu hình>
    end

    CP->>GW: bất kỳ CALL nào KHÁC trước khi được Accepted
    GW-->>CP: CALLERROR SecurityError
```

**Ràng buộc bắt buộc:**
- Mã trụ được kiểm tra ở **đường dẫn WebSocket**, không tin dữ liệu trong thân
  tin nhắn.
- `interval` (khoảng nhịp tim) là tham số cấu hình, không hardcode.
- Đúng 1 kết nối sống cho mỗi mã trụ tại một thời điểm.
- Log chỉ ghi mã lạ + IP, **không log toàn bộ header**.

---

## SSD-3. Vòng đời một phiên sạc (S-17 → S-21, T-36 đến T-46)

Đây là luồng **lõi nhất** của cả hệ thống — mọi handler OCPP sau này bám theo
khung này.

```mermaid
sequenceDiagram
    actor D as Tài xế
    participant CP as Trụ sạc
    participant GW as OCPP Dispatcher
    participant DB as charging_sessions / meter_values / ocpp_messages

    D->>CP: quẹt thẻ, cắm súng
    CP->>GW: CALL StartTransaction (idTag, connectorId, meterStart)

    GW->>DB: tra ocpp_messages theo (mã trụ, messageId) — CHỐNG TRÙNG
    alt tin nhắn đã xử lý trước đó (gửi lại)
        GW-->>CP: trả lại ĐÚNG câu trả lời cũ, KHÔNG chạy lại logic
    else tin nhắn mới
        GW->>DB: kiểm idTag (Accepted/Blocked/Expired/Invalid)
        alt đầu nối đang có phiên mở
            GW->>DB: đóng phiên cũ, lý do "bất thường" + cảnh báo
        end
        GW->>DB: INSERT charging_sessions (transactionId = id tự tăng, meterStart, started_at)
        GW-->>CP: CALLRESULT { transactionId, idTagInfo }
    end

    loop mỗi 10s trong lúc sạc
        CP->>GW: CALL MeterValues (Energy.Active.Import.Register, timestamp)
        GW->>DB: so timestamp với số đo mới nhất CÙNG PHIÊN (trong 1 transaction)
        alt timestamp cũ hơn số đo đã lưu
            GW->>GW: bỏ qua + log cảnh báo
        else timestamp mới, giá trị nhỏ hơn số đo đã lưu
            GW->>DB: lưu NHƯNG đánh dấu phiên "cần xem xét"
        else bình thường
            GW->>DB: INSERT meter_values
        end
        GW-->>CP: CALLRESULT (trả lời trước, ghi bảng sau — không làm chậm >200ms)
    end

    opt trụ mất kết nối giữa phiên
        Note over CP,GW: kết nối đứt — KHÔNG tự đóng phiên chỉ vì ngoại tuyến
        CP->>GW: nối lại, StatusNotification "Charging"
        GW->>DB: giữ nguyên phiên (không tạo phiên mới)
    end

    D->>CP: rút súng
    CP->>GW: CALL StopTransaction (meterStop, timestamp, reason)
    GW->>DB: kWh = (meterStop − meterStart) / 1000
    alt meterStop < meterStart
        GW->>DB: đánh dấu "cần xem xét", KHÔNG ghi số âm
    else transactionId không tồn tại
        GW->>DB: ghi vào orphan_messages + cảnh báo
    else bình thường
        GW->>DB: đóng phiên, lưu kWh, thời điểm, lý do
    end
    GW-->>CP: CALLRESULT theo đặc tả
```

**Ràng buộc bắt buộc (đây là phần hay bị AI vide code làm sai nhất):**
- `transactionId` = số nguyên tăng dần **do DB cấp**, không dùng timestamp.
- kWh = hiệu số đo cuối trừ số đo đầu, **không cộng dồn** từng lần `MeterValues`.
- So sánh thời gian số đo theo **mốc thời gian trong tin nhắn OCPP**, không theo
  giờ máy chủ lúc nhận.
- Chống trùng tin nhắn dựa vào bảng `ocpp_messages` ở DB, không dựa biến RAM.
- Tra bảng chống trùng + gọi handler nằm **cùng 1 transaction DB**.
- Trụ ngoại tuyến **không tự đóng phiên** — chỉ job nền (SSD-4) đánh dấu "cần
  xem xét" sau ngưỡng cấu hình (mặc định 6 giờ).

---

## SSD-4. Job nền phát hiện trụ/phiên bất thường (T-26, T-53)

```mermaid
sequenceDiagram
    participant J as Job nền (chạy mỗi phút)
    participant DB as charge_points / charging_sessions

    loop mỗi phút
        J->>DB: SELECT trụ có last_seen_at cũ hơn 2 × interval
        J->>DB: UPDATE trạng thái -> ngoại tuyến

        J->>DB: SELECT phiên đang sạc có trụ ngoại tuyến > ngưỡng cấu hình (mặc định 6h)
        J->>DB: UPDATE trạng thái phiên -> "bất thường" (KHÔNG đóng phiên)
    end
```

**Ràng buộc bắt buộc:**
- Job chạy 2 lần liên tiếp mà không có gì đổi → **không được** ghi thêm gì (idempotent).
- Trạng thái ngoại tuyến phải **suy được từ `last_seen_at`** ngay cả khi job vừa
  khởi động lại và chưa kịp chạy — không phụ thuộc job có đang chạy hay không.
- Job chỉ **đánh dấu**, không tự đóng phiên — đóng là quyết định của người
  (vận hành viên, qua SSD-5 mở rộng).

---

## SSD-5. Vận hành viên dừng phiên từ xa (S-23, T-49, T-50)

```mermaid
sequenceDiagram
    actor OP as Vận hành viên
    participant API as POST /sessions/{id}/remote-stop
    participant OUT as Outbound CALL dispatcher (T-34)
    participant CP as Trụ sạc

    OP->>API: bấm "dừng phiên"
    alt trụ ngoại tuyến
        API-->>OP: báo lỗi ngay, KHÔNG gửi lệnh, phiên không đổi trạng thái
    else trụ trực tuyến
        API->>OUT: gửi CALL RemoteStopTransaction(transactionId)
        OUT->>CP: CALL
        alt CP trả Rejected
            CP-->>OUT: CALLRESULT Rejected
            OUT-->>API: phiên VẪN đang sạc, báo "trụ từ chối"
        else CP trả Accepted
            CP-->>OUT: CALLRESULT Accepted
            Note over API: KHÔNG đóng phiên ngay — chờ StopTransaction thật
            OUT->>OUT: đặt mốc chờ 2 phút
            CP->>API: CALL StopTransaction (thật) -> phiên đóng, lý do "Remote"
            opt quá 2 phút không có StopTransaction
                API->>API: đánh dấu phiên "cần xem xét" (qua job T-53)
            end
        end
    end
```

**Ràng buộc bắt buộc:**
- Phiên **chỉ đóng khi có `StopTransaction` thật** từ trụ, không đóng ngay khi
  nhận `Accepted` từ `RemoteStopTransaction`.
- Mọi lệnh điều khiển từ xa (`Reset`, `RemoteStopTransaction`...) ghi 1 dòng
  `audit_logs`: người, lệnh, đối tượng, thời điểm, kết quả.

---

## SSD-6. Nạp ví qua webhook + trừ ví khi kết thúc phiên (S-35, S-37, S-39, S-41)

```mermaid
sequenceDiagram
    actor D as Tài xế
    participant API as Backend
    participant PG as Cổng thanh toán (sandbox)
    participant DB as wallets / ledger_entries

    D->>API: chọn số tiền nạp
    API->>DB: tạo giao dịch "chờ"
    API-->>D: chuyển hướng sang trang cổng sandbox
    D->>PG: thanh toán trên trang cổng

    PG-->>API: webhook xác nhận (có chữ ký)
    alt chữ ký sai/thiếu
        API-->>PG: 401, KHÔNG đổi số dư, log cảnh báo kèm IP
    else giao dịch không tồn tại
        API-->>PG: 404 + cảnh báo
    else webhook gửi LẠI (đã xử lý trước đó, theo mã giao dịch cổng)
        API-->>PG: 200 (idempotent — không tăng số dư lần 2)
    else hợp lệ, lần đầu
        API->>DB: INSERT ledger_entries (loại: nạp), số dư suy ra = tổng nạp − tổng tiêu
        API-->>PG: 200
    end

    Note over API,DB: --- Khi một phiên sạc kết thúc (SSD-3 hoàn tất) ---
    API->>DB: BẮT ĐẦU 1 TRANSACTION
    API->>DB: lập hoá đơn bất biến (snapshot biểu giá tại thời điểm sạc)
    API->>DB: INSERT ledger_entries (loại: trừ, tham chiếu tới phiên)
    API->>DB: COMMIT
    Note over DB: số dư có thể ÂM — không chặn, chỉ đánh dấu tài khoản "nợ"
```

**Ràng buộc bắt buộc:**
- `ledger_entries` **chỉ INSERT**, không UPDATE tại chỗ — số dư luôn là **tổng
  cộng dồn từ sổ**, không lưu một cột "số dư hiện tại" làm nguồn sự thật riêng
  (nếu có cột cache, job đối chiếu phải phát hiện lệch và khoá giao dịch mới cho
  tới khi xử lý).
- Chống trùng webhook theo **mã giao dịch của cổng**, lưu ở DB — cùng nguyên
  tắc với SSD-3 (chống trùng OCPP).
- Trừ ví + lập hoá đơn nằm **trong cùng 1 transaction DB** — một phiên không
  bao giờ bị trừ 2 lần kể cả khi 2 phiên của cùng tài xế kết thúc đồng thời.
- Không lưu thông tin thẻ thanh toán ở đâu cả.

---

## Cách mở rộng SSD cho epic còn lại

Khi làm tới các epic Later (E-07 đặt chỗ, E-08 phân bổ công suất, E-09 đối soát),
tạo file `SSD-7...`, `SSD-8...` theo đúng khuôn:

1. Vẽ sequence diagram actor ↔ hệ thống ↔ (trụ sạc nếu có).
2. Bảng "Ràng buộc bắt buộc" **chỉ lấy từ cột AC/NFR trong file backlog gốc**,
   không tự bịa thêm ràng buộc mới.
3. Đánh dấu rõ bước nào phải nằm trong cùng 1 transaction DB.
4. Đánh dấu rõ đâu là hàm thuần (không đọc DB) cần tách riêng để test theo bảng.

Khi đưa cho AI vide code một story cụ thể, luôn dán kèm đúng đoạn SSD tương ứng
+ bảng ràng buộc — đó chính là "hợp đồng" AI phải tuân theo, không phải tự suy
diễn từ tên story.
