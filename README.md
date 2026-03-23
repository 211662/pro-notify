# 📬 Pro-Notify

**Email Keyword Monitor → Telegram Notification**

Tự động quét email (Gmail, Outlook, Yahoo...), khi phát hiện nội dung chứa keyword đã cấu hình → gửi thông báo sang Telegram Bot. **Hỗ trợ nhiều tài khoản email**, mỗi tài khoản có keyword riêng và gửi tới chat Telegram riêng.

```
                          ┌──────────────┐
┌──────────┐    poll      │  Keyword     │   match?    ┌──────────────┐
│ Email 1  │ ──────────▶  │  Matcher 1   │ ─────────▶  │  Chat ID A   │
└──────────┘              └──────────────┘             └──────────────┘
┌──────────┐    poll      ┌──────────────┐   match?    ┌──────────────┐
│ Email 2  │ ──────────▶  │  Matcher 2   │ ─────────▶  │  Chat ID B   │
└──────────┘              └──────────────┘             └──────────────┘
        ...                     ...                         ...
```

---

## 🏗 Cấu trúc project

```
pro-notify/
├── main.py                    # Entry point — poll loop đa tài khoản
├── accounts.example.yml       # Template cấu hình multi-account
├── requirements.txt           # Python dependencies
├── .env.example               # Template biến môi trường (single account)
├── .gitignore
└── src/
    ├── __init__.py
    ├── config.py              # Load config từ .env (backward compat)
    ├── account_manager.py     # Load & validate accounts.yml
    ├── email_service.py       # IMAP email service (multi-provider)
    ├── gmail_service.py       # Backward compat alias → email_service
    ├── telegram_service.py    # Telegram Bot API — gửi message
    ├── keyword_matcher.py     # Quét keyword trong email content
    └── encryption.py          # Mã hóa .env bằng AES (Fernet)
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
   - Truy cập URL sau trên trình duyệt:
     ```
     https://api.telegram.org/botTOKEN_CUA_BAN/getUpdates
     ```
   - Trong kết quả JSON, tìm `"chat":{"id": 123456789}` → con số đó là CHAT_ID

### 3. Tạo Gmail App Password (không cần Google Cloud!)

1. Bật **Xác minh 2 bước** (2FA) cho tài khoản Google:
   - Vào [myaccount.google.com/security](https://myaccount.google.com/security)
   - Tìm "2-Step Verification" → Bật lên
2. Tạo **App Password**:
   - Vào [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
   - Đặt tên app: `pro-notify` → **Create** → copy mật khẩu `xxxx xxxx xxxx xxxx`

> ⚠️ Nếu không thấy mục "App passwords", hãy chắc chắn đã bật 2FA trước.

---

## 📧 Cấu hình Multi-Account (Khuyến nghị)

### Tạo `accounts.yml`

```bash
cp accounts.example.yml accounts.yml
```

Sửa `accounts.yml`:

```yaml
accounts:
  - name: "Personal Gmail"
    email: "your-email@gmail.com"
    app_password: "xxxx xxxx xxxx xxxx"
    imap_server: "imap.gmail.com"
    imap_port: 993
    keywords:
      - "dmca"
      - "copyright"
      - "invoice"
      - "urgent"
    telegram:
      bot_token: "7012345678:AAH...your_token"
      chat_id: "123456789"

  - name: "Work Outlook"
    email: "work@outlook.com"
    app_password: "your-password"
    imap_server: "outlook.office365.com"
    imap_port: 993
    keywords:
      - "invoice"
      - "payment"
      - "thanh toán"
    telegram:
      bot_token: "7012345678:AAH...your_token"
      chat_id: "987654321"

settings:
  poll_interval: 60
  max_results: 20
```

Mỗi account có thể:
- **Keyword riêng** — monitor những từ khóa khác nhau
- **Chat Telegram riêng** — gửi tới group/person khác nhau
- **IMAP server riêng** — Gmail, Outlook, Yahoo, bất kỳ IMAP nào

### Chạy

```bash
python main.py
```

---

## 📧 Cấu hình Single Account (Backward compat)

Nếu chỉ có 1 tài khoản, dùng `.env` như Phase 1:

```bash
cp .env.example .env
```

```env
TELEGRAM_BOT_TOKEN=7012345678:AAH...your_token_here
TELEGRAM_CHAT_ID=123456789
EMAIL_ADDRESS=your_email@gmail.com
EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993
POLL_INTERVAL=60
KEYWORDS=dmca,copyright,invoice,urgent,thanh toán
```

> Khi KHÔNG có `accounts.yml`, app tự động fallback sang `.env`.

```bash
python main.py
```

---

## ⚙️ Cách hoạt động

1. **Load accounts**: Đọc `accounts.yml` (hoặc fallback `.env` nếu chỉ có 1 tài khoản)
2. **Poll**: Mỗi `poll_interval` giây, kết nối IMAP cho **từng account**, lấy email UNSEEN
3. **Match**: Quét `subject` + `body` + `snippet` → tìm keyword (case-insensitive)
4. **Notify**: Nếu match → gửi thông báo chi tiết qua Telegram Bot tới chat tương ứng
5. **Mark read**: Email đã xử lý được đánh dấu đã đọc → tránh gửi trùng

### Telegram notification mẫu

```
📧 Email Alert
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Account: Personal Gmail
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

## 🗺 Roadmap

- [x] MVP — Gmail keyword monitor → Telegram
- [x] IMAP + App Password (không cần Google Cloud)
- [x] Encryption (.env.encrypted)
- [x] GitHub Actions / VPS deployment
- [x] **Phase 2** — Multi-account, per-account keywords & routing
- [ ] **Phase 3** — Gold price bot, Weather bot
- [ ] Regex pattern cho keyword matching
- [ ] Web dashboard quản lý keyword
- [ ] Docker container hóa
- [ ] Lưu history vào SQLite

---

## License

MIT
