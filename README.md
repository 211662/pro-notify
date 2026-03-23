# 📬 Pro-Notify

**Email Keyword Monitor → Telegram Notification**

Tự động quét email Gmail, khi phát hiện nội dung chứa keyword đã cấu hình → gửi thông báo sang Telegram Bot.

```
┌──────────┐    poll     ┌───────────────┐   match?   ┌──────────────┐
│  Gmail   │ ─────────▶  │ Keyword       │ ────────▶  │  Telegram    │
│  Inbox   │  (unread)   │ Matcher       │  (yes)     │  Bot API     │
└──────────┘             └───────────────┘            └──────────────┘
```

---

## 🏗 Cấu trúc project

```
pro-notify/
├── main.py                  # Entry point — chạy polling loop
├── requirements.txt         # Python dependencies
├── .env.example             # Template biến môi trường
├── .gitignore
└── src/
    ├── __init__.py
    ├── config.py            # Load config từ .env
    ├── gmail_service.py     # Gmail API — OAuth2, fetch, mark-read
    ├── telegram_service.py  # Telegram Bot API — gửi message
    └── keyword_matcher.py   # Quét keyword trong email content
```

---

## 🚀 Hướng dẫn Setup

### 1. Cài đặt dependencies

```bash
cd pro-notify
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
pip install -r requirements.txt
```

### 2. Tạo Telegram Bot

1. Mở Telegram, tìm **@BotFather**
2. Gửi `/newbot` → đặt tên → nhận **BOT TOKEN**
3. Tạo group/channel hoặc chat riêng với bot
4. Lấy **CHAT_ID**:
   - Gửi 1 tin nhắn bất kỳ cho bot (ví dụ gửi "hello")
   - Truy cập URL sau trên trình duyệt (**thay TOKEN bằng token thật, KHÔNG giữ dấu `<>`**):
     ```
     https://api.telegram.org/botTOKEN_CUA_BAN/getUpdates
     ```
     Ví dụ nếu token là `7012345678:AAHxxxxx` thì URL sẽ là:
     ```
     https://api.telegram.org/bot7012345678:AAHxxxxx/getUpdates
     ```
   - Trong kết quả JSON, tìm `"chat":{"id": 123456789}` → con số đó là CHAT_ID

### 3. Tạo Gmail App Password (không cần Google Cloud!)

1. Bật **Xác minh 2 bước** (2FA) cho tài khoản Google:
   - Vào [myaccount.google.com/security](https://myaccount.google.com/security)
   - Tìm "2-Step Verification" → Bật lên
2. Tạo **App Password**:
   - Vào [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
   - Hoặc: Google Account → Security → 2-Step Verification → App passwords
   - Đặt tên app: `pro-notify`
   - Nhấn **Create** → Google sẽ hiện mật khẩu dạng `xxxx xxxx xxxx xxxx`
   - **Copy lại ngay** — chỉ hiện 1 lần!

> ⚠️ Nếu không thấy mục "App passwords", hãy chắc chắn đã bật 2FA trước.

### 4. Cấu hình .env

```bash
cp .env.example .env
```

Sửa file `.env`:

```env
TELEGRAM_BOT_TOKEN=7012345678:AAH...your_token_here
TELEGRAM_CHAT_ID=123456789
EMAIL_ADDRESS=your_email@gmail.com
EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993
POLL_INTERVAL=60
KEYWORDS=abc,def,urgent,invoice,thanh toán
```

> **KEYWORDS** là danh sách keyword cách nhau bởi dấu phẩy.
> Matching **không phân biệt** hoa thường.

### 5. Chạy

```bash
python main.py
```

- Không cần đăng nhập trình duyệt — IMAP + App Password kết nối trực tiếp
- Bot sẽ gửi tin nhắn "🟢 Pro-Notify started" vào Telegram khi chạy thành công

---

## ⚙️ Cách hoạt động

1. **Poll**: Mỗi `POLL_INTERVAL` giây, app kết nối Gmail qua IMAP, lấy email chưa đọc (UNSEEN)
2. **Match**: Quét `subject` + `body` + `snippet` → tìm keyword (case-insensitive)
3. **Notify**: Nếu match → gửi thông báo chi tiết qua Telegram Bot
4. **Mark read**: Email đã xử lý được đánh dấu đã đọc → tránh gửi trùng

### Telegram notification mẫu

```
📧 Email Alert
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
From: boss@company.com
Subject: Invoice tháng 3 - cần thanh toán
Date: Mon, 23 Mar 2026 10:30:00 +0700
Keywords: #invoice #thanh_toán
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Content:
Gửi bạn invoice tháng 3, vui lòng thanh toán
trước ngày 30/03...
```

---

## 🧪 Test nhanh

Gửi cho chính mình 1 email có nội dung chứa keyword (vd: "abc") → chờ poll cycle → kiểm tra Telegram.

---

## 📌 Lưu ý

- **Quota**: Gmail IMAP không có quota limit như API, nhưng tránh poll quá nhanh (< 10s)
- **Security**: Không commit file `.env` lên git (đã có trong .gitignore)
- **Scaling**: Muốn real-time hơn → giảm `POLL_INTERVAL` (tối thiểu 10s recommended)
- **Multi-account**: Có thể chạy nhiều instance với `.env` khác nhau

---

## 🔐 Mã hóa credentials (khuyến nghị)

Nếu bạn muốn commit project lên GitHub mà **không lộ token/password**:

### Bước 1: Mã hóa file `.env`

```bash
python -m src.encryption encrypt
```

- Nhập master password (nhớ kỹ!) → tạo ra file `.env.encrypted` + `.salt`
- **Xóa file `.env`** sau khi mã hóa xong

### Bước 2: Commit an toàn

```bash
rm .env                              # Xóa file plaintext
git add .env.encrypted .salt         # Commit file đã mã hóa
git commit -m "Add encrypted config"
git push
```

### Bước 3: Chạy app từ file mã hóa

```bash
python main.py
# App sẽ hỏi master password → giải mã trong memory → KHÔNG tạo lại .env
```

### Kiểm tra giải mã

```bash
python -m src.encryption decrypt     # Xem các biến đã mã hóa (hiện masked)
```

> ⚠️ **Master password không thể khôi phục** — nếu quên thì phải tạo lại `.env` và mã hóa lại.

---

## ☁️ Chạy 24/7 với GitHub Actions (miễn phí)

Không cần mở máy — GitHub tự động chạy check email mỗi 2 phút.

### Bước 1: Thêm Secrets vào GitHub repo

Vào repo trên GitHub → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Thêm lần lượt 5 secrets:

| Secret name | Value |
|-------------|-------|
| `TELEGRAM_BOT_TOKEN` | Token bot Telegram |
| `TELEGRAM_CHAT_ID` | Chat ID Telegram |
| `EMAIL_ADDRESS` | Email Gmail |
| `EMAIL_APP_PASSWORD` | App Password Gmail |
| `KEYWORDS` | `dmca,copyright,invoice,...` |

### Bước 2: Push code lên GitHub

```bash
git add .
git commit -m "Add GitHub Actions workflow"
git push
```

### Bước 3: Xong!

- GitHub Actions sẽ **tự động chạy mỗi 2 phút**
- Kiểm tra tại: repo → tab **Actions** → workflow "Pro-Notify Email Monitor"
- Có thể nhấn **Run workflow** để test thủ công

### Tùy chỉnh tần suất

Sửa cron trong `.github/workflows/notify.yml`:

```yaml
schedule:
  - cron: '*/2 * * * *'   # Mỗi 2 phút
  - cron: '*/5 * * * *'   # Mỗi 5 phút
  - cron: '*/10 * * * *'  # Mỗi 10 phút
```

> 📌 GitHub Actions free: **2,000 phút/tháng**. Mỗi 2 phút ≈ 720 lần/ngày × ~0.5 phút = ~360 phút/ngày → đủ dùng nếu chạy mỗi 5 phút.

---

## 🗺 Roadmap (sau MVP)

- [ ] Hỗ trợ regex pattern cho keyword matching
- [ ] Web dashboard quản lý keyword
- [ ] Gmail Push Notification (Pub/Sub) thay vì polling
- [ ] Hỗ trợ nhiều email provider (Outlook, Yahoo)
- [ ] Lưu history vào SQLite/PostgreSQL
- [ ] Docker container hóa

---

## License

MIT
