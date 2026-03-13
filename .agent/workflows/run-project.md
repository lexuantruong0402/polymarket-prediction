---
description: Cách chạy frontend và backend cho dự án Polymarket Prediction
---

Để chạy dự án, bạn cần chạy đồng thời cả Backend (API) và Frontend (Server).

1. **Khởi chạy Backend (FastAPI)**
Mở một terminal mới và chạy lệnh sau:
// turbo
```bash
python3 -m predict_market_bot.api
```
Backend sẽ chạy tại: `http://localhost:8000`

2. **Khởi chạy Frontend (HTTP Server)**
Mở một terminal khác và chạy lệnh sau trong thư mục `frontend`:
// turbo
```bash
python3 -m http.server 8080 --directory frontend
```
Frontend sẽ chạy tại: `http://localhost:8080`

3. **Sử dụng**
- Mở trình duyệt và truy cập `http://localhost:8080`.
- Nhập URL một phiên chợ từ Polymarket (ví dụ: `https://polymarket.com/event/will-the-fed-cut-rates-in-march`).
- Nhấn **Process** để xem quá trình đánh giá từng bước qua 6 giai đoạn.
