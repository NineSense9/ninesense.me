# NineSense

NineSense 个人网站及其自建留言板的正式代码仓库。公开页面仍是纯静态站点，留言 API 使用 FastAPI 与 SQLite，并由同源 Nginx 入口代理。

## 目录

- `site/`：可直接发布的静态网站、留言板和管理后台
- `server/`：FastAPI 服务、Alembic 迁移和自动化测试
- `deploy/`：Nginx、systemd、备份与发布脚本
- `tests/`：静态契约、部署配置和浏览器端到端测试
- `docs/`：已确认的产品与技术设计文档

禁止将生产密钥、数据库、备份、访客联系方式、密码、会话值或服务器日志提交到仓库。

## 本地开发与检查

```powershell
python -m venv server/.venv
server/.venv/Scripts/python -m pip install -e 'server[dev]'
server/.venv/Scripts/python -m ruff check server/src server/tests server/alembic
server/.venv/Scripts/python -W 'error::ResourceWarning' -m pytest server/tests
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-static-release.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-deploy-config.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File tests/test-public-repo.ps1
npm install
npm run test:e2e
```

浏览器测试会在 `127.0.0.1:8123` 启动一次性服务，使用独立测试数据库和测试管理员，不读取生产凭据。

## 生产路径

- 后端版本：`/opt/ninesense-guestbook/releases/<timestamp>`
- 后端当前版本：`/opt/ninesense-guestbook/current`
- 静态版本：`/var/www/ninesense/releases/<timestamp>`
- 静态当前版本：`/var/www/ninesense/current`
- 数据库：`/var/lib/ninesense/guestbook.sqlite3`
- 私密配置：`/etc/ninesense/guestbook.env`
- 备份：`/var/backups/ninesense/guestbook/`

API 只能监听 `127.0.0.1:8812`，公网仅通过现有 8811 Nginx 入口访问。不得为 API 单独开放安全组端口。

## 管理账户

首次创建账户和以后修改密码都在服务器终端交互完成，密码不会出现在命令历史中：

```bash
sudo -u ninesense bash -c 'set -a; . /etc/ninesense/guestbook.env; set +a; /opt/ninesense-guestbook/current/venv/bin/python -m ninesense_guestbook.cli create-admin --username ninesense'
sudo -u ninesense bash -c 'set -a; . /etc/ninesense/guestbook.env; set +a; /opt/ninesense-guestbook/current/venv/bin/python -m ninesense_guestbook.cli reset-admin-password --username ninesense'
```

正式管理登录必须通过 HTTPS。域名和证书尚未接入时，HTTP 后台只用于受控验收。

## 迁移、备份与恢复

迁移前先执行一次即时备份：

```bash
systemctl start ninesense-guestbook-backup.service
sudo -u ninesense bash -c 'set -a; . /etc/ninesense/guestbook.env; set +a; cd /opt/ninesense-guestbook/current/server; ../venv/bin/alembic -c alembic.ini upgrade head'
```

日备份保留 30 天，每月第一天另存月备份并保留 12 份。查看定时器与最新文件：

```bash
systemctl status ninesense-guestbook-backup.timer
find /var/backups/ninesense/guestbook/daily -maxdepth 1 -type f -printf '%T@ %p\n' | sort -rn | head
```

恢复时先停服务并保留当前数据库副本，再复制备份、修正权限、检查完整性和迁移版本：

```bash
systemctl stop ninesense-guestbook.service
cp -a /var/lib/ninesense/guestbook.sqlite3 /var/backups/ninesense/guestbook/pre-restore.sqlite3
cp /var/backups/ninesense/guestbook/daily/<backup>.sqlite3 /var/lib/ninesense/guestbook.sqlite3
chown ninesense:ninesense /var/lib/ninesense/guestbook.sqlite3
chmod 600 /var/lib/ninesense/guestbook.sqlite3
sqlite3 /var/lib/ninesense/guestbook.sqlite3 'PRAGMA integrity_check;'
sudo -u ninesense bash -c 'set -a; . /etc/ninesense/guestbook.env; set +a; cd /opt/ninesense-guestbook/current/server; ../venv/bin/alembic -c alembic.ini current'
systemctl start ninesense-guestbook.service
```

## 发布与回滚

发布包应包含 `site/`、`server/`、`deploy/` 和本说明。`deploy/deploy-guestbook.sh` 会创建时间戳版本、迁移数据库、验证本机 API、检查 Nginx、切换静态版本并运行首次备份；任何关键检查失败都会恢复之前的静态链接和 Nginx 配置。

代码回滚通过切换 `current` 软链接完成。若旧代码不兼容新数据库结构，必须先创建即时备份，再执行已经验证的降级迁移或恢复发布前备份，不能直接删除新留言。

## 邮件提醒与 HTTPS

邮件提醒需要在 `/etc/ninesense/guestbook.env` 中设置 SMTP 主机、端口、账户、应用专用密码、收件地址和后台公开地址。修改后执行：

```bash
systemctl restart ninesense-guestbook.service
```

域名与证书接入后，将 `NINESENSE_COOKIE_SECURE=true`、`NINESENSE_PUBLIC_ADMIN_URL=https://ninesense.me/admin/`，再重启服务。HTTPS 只改变入口和 Cookie 安全标记，不改变 `/guestbook/`、`/admin/` 或 `/api/` 路径。

## 日志边界

日志只能记录事件类型、结果和不透明短期标识，不能记录完整正文、联系方式、原始 IP、密码、Cookie、会话、CSRF、加密密钥或 SMTP 密码。生产服务默认关闭 Uvicorn 访问日志。
