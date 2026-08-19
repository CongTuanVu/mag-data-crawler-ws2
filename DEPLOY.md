# Chạy pipeline trên server (qua code_proxy)

Kiến trúc trên server giống hệt máy cá nhân — không cần `ANTHROPIC_API_KEY`:

```
run_batch.sh ──▶ discover_sources.py / extract_llm.py
                          │  HTTP  http://127.0.0.1:11439/v1/messages
                          ▼
                     code_proxy ──▶ claude --print   (phiên đăng nhập Claude Code)
```

Điều kiện tiên quyết duy nhất khác máy cá nhân: **Claude Code CLI phải đăng nhập được trên
server**, mà server thì không có trình duyệt. Mục 2 xử lý đúng chỗ đó.

> Đọc `code_proxy/README.md` trước khi đưa lên production: proxy chạy bằng tài khoản Claude
> cá nhân của bạn, và dùng gói subscription cho tải tự động trên server có thể nằm ngoài
> phạm vi cho phép — kiểm tra điều khoản. Ở môi trường production, `ANTHROPIC_API_KEY` mới
> là đường đúng (code đã tự nhận biết: có key thì gọi thẳng `api.anthropic.com`).

## 0. Yêu cầu máy

| Hạng mục | Tối thiểu | Vì sao |
|---|---|---|
| RAM | 8 GB | mỗi tiến trình `claude --print` ~400 MB × 4 đồng thời, cộng Chromium |
| Disk | 20 GB | raw ~1 MB/trang; 104 khu ≈ 1–2 GB, chưa kể Chromium |
| CPU | 4 core | 4 luồng batch chạy song song |
| OS | Ubuntu 22.04+ | hướng dẫn dưới đây theo apt |

Chạy dài nhiều giờ nên **tắt sleep/suspend** — log proxy cũ có lỗi
`Your computer went to sleep mid-response` làm hỏng nguyên một request.

```bash
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
```

## 1. Cài đặt

```bash
sudo apt update
sudo apt install -y python3-pip git curl

# Node.js 20+ cho Claude Code CLI
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

git clone <repo> /opt/mag-data-crawler
cd /opt/mag-data-crawler
pip install -r requirements.txt
python3 -m playwright install --with-deps chromium   # --with-deps là bắt buộc trên server trắng
```

Kiểm tra Chromium chạy được headless:

```bash
python3 -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); print('chromium OK'); b.close()"
```

## 2. Đăng nhập Claude Code CLI trên máy không có trình duyệt

Ba cách, chọn một:

**Cách A — đăng nhập trên chính server, mở URL ở máy bạn**

```bash
claude auth login          # in ra một URL
```

Copy URL sang trình duyệt máy cá nhân, đăng nhập, dán mã trả về vào terminal server.

**Cách B — copy phiên đăng nhập từ máy cá nhân** (nhanh nhất)

```bash
# trên máy cá nhân — đã đăng nhập sẵn
tar czf claude-auth.tgz -C ~ .claude/.credentials.json .claude.json 2>/dev/null
scp claude-auth.tgz user@server:~
# trên server
tar xzf claude-auth.tgz -C ~ && rm claude-auth.tgz
```

**Cách C — SSH tunnel** nếu luồng đăng nhập cần callback localhost:

```bash
ssh -L 8484:localhost:8484 user@server   # rồi chạy claude auth login trong phiên này
```

Xác nhận:

```bash
claude auth status        # phải thấy "loggedIn": true
```

Token có hạn — nếu pipeline đột nhiên lỗi 502 hàng loạt, kiểm tra lại lệnh này trước khi
debug bất cứ thứ gì khác.

## 3. Chạy proxy như một service

```bash
sudo tee /etc/systemd/system/code-proxy.service > /dev/null <<'EOF'
[Unit]
Description=code_proxy - Claude CLI proxy cho mag-data-crawler
After=network.target

[Service]
Type=simple
User=congvt3
WorkingDirectory=/opt/mag-data-crawler
Environment=CLAUDE_PROXY_MODEL=claude-opus-5
Environment=LLM_PROXY_MAX_CONCURRENCY=4
# proxy chạy bằng phiên đăng nhập của User ở trên -> HOME phải trỏ đúng
Environment=HOME=/home/congvt3
ExecStart=/opt/mag-data-crawler/code_proxy/start.sh --timeout 900
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now code-proxy
curl -s http://127.0.0.1:11439/healthz     # {"status":"ok","model":"claude-opus-5"}
```

`LLM_PROXY_MAX_CONCURRENCY` phải **≥ số luồng batch** ở bước sau, nếu không request xếp hàng
và dễ chạm timeout.

## 4. Chạy pipeline từ đầu

Đầu vào duy nhất là `refer_file/aerotropolis.txt`. Không cần chuẩn bị gì thêm.

```bash
cd /opt/mag-data-crawler
export ANTHROPIC_BASE_URL=http://127.0.0.1:11439

# một khu, để kiểm chứng toàn tuyến trước khi chạy hàng loạt
python3 scripts/run_ws.py ws1_airport --cases zhengzhou
```

Chạy toàn bộ, 4 luồng song song (mỗi luồng tuần tự trong nhóm của nó):

```bash
# chia danh sách khu chưa có feature thành 4 nhóm
python3 - <<'PY'
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("b", "scripts/build_source_registry.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
reg, taken = m.load_registry(), set(m.load_registry())
feat = Path("raw_data/output/ws1_airport/features")
todo = [cid for cid in (m.match_case_id(e, reg, taken) for e in m.parse_case_list())
        if not (feat / f"{cid}_airport_city.json").exists()]
for i in range(4):
    Path(f"/tmp/group{i+1}.txt").write_text(" ".join(todo[i::4]))
print(f"{len(todo)} khu cần chạy, chia 4 nhóm")
PY

for i in 1 2 3 4; do
    nohup ./scripts/run_batch.sh "n$i" $(cat /tmp/group$i.txt) > /tmp/batch$i.out 2>&1 &
done
```

Dùng `tmux` / `screen` hoặc `systemd-run --user` nếu muốn job sống qua khi đóng SSH —
`nohup` ở trên đã đủ cho hầu hết trường hợp.

**Chạy lại được sau khi gián đoạn.** Mỗi bước tự bỏ qua phần đã xong: discover bỏ khu đã có
`refer_file/_discovered/<case>.csv`, crawl append-only, extract có `--skip-done`. Ngắt giữa
chừng rồi chạy lại đúng lệnh trên là tiếp tục, không mất gì và không làm lại.

## 5. Theo dõi

```bash
tail -3 raw_data/output/ws1_airport/_batch_n*.log            # tiến độ từng nhóm
ls raw_data/output/ws1_airport/features/*_airport_city.json | wc -l
ps aux | grep -c "[r]un_batch.sh"                             # 0 = xong hết
sudo journalctl -u code-proxy -f                              # log proxy
```

## 6. Bước cuối + xuất bản trang web

```bash
python3 scripts/build_source_registry.py     # gộp nguồn -> refer_file/sources.csv|.xlsx
python3 scripts/validate_features.py         # kiểm kiểu + bảng độ phủ
python3 html/build_portal.py                 # -> html/index.html
```

`html/index.html` là file tĩnh tự chứa — không backend, không database:

```bash
sudo cp html/index.html /var/www/html/index.html
```

nginx nên bật gzip (1,8 MB → ~400 KB):

```nginx
server {
    listen 80;
    root /var/www/html;
    gzip on;
    gzip_types text/html;
    gzip_min_length 1024;
}
```

Muốn nhẹ hơn: `python3 html/build_portal.py --no-images` → ~140 KB (bỏ ảnh hero).

## 7. Cập nhật định kỳ

```cron
0 3 * * 0 cd /opt/mag-data-crawler && ANTHROPIC_BASE_URL=http://127.0.0.1:11439 \
  python3 scripts/run_ws.py ws1_airport --steps registry,crawl,extract,validate,web \
  >> /var/log/mag-crawler.log 2>&1 && cp html/index.html /var/www/html/index.html
```

Bỏ `discover` khỏi cron: nó chỉ cần chạy khi thêm khu mới, và là bước tốn nhất.

## Sự cố thường gặp

| Hiện tượng | Nguyên nhân | Xử lý |
|---|---|---|
| `502` hàng loạt từ proxy | phiên CLI hết hạn, hoặc máy ngủ | `claude auth status`; mask sleep target (mục 0) |
| `Connection refused :11439` | proxy chưa chạy | `systemctl status code-proxy` |
| Request xếp hàng, timeout | `LLM_PROXY_MAX_CONCURRENCY` < số luồng batch | nâng lên bằng số luồng, restart proxy |
| Chromium lỗi thiếu thư viện | quên `--with-deps` | `python3 -m playwright install --with-deps chromium` |
| Disk đầy | raw tích luỹ | crawler mặc định không chụp ảnh; kiểm tra không ai bật `--shots` |
| Crawl ra trang rỗng | trang chặn bot / render chậm | `--timeout 60`, hoặc bỏ URL khỏi `sources.csv` |
