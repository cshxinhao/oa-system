# oa-system 部署指南（阿里云 ECS）

默认架构：Nginx 反代 → Gunicorn（WSGI）→ systemd 常驻。

## 前提

- 阿里云 ECS 实例（Ubuntu 22.04 / 24.04）
- 一块**单独的数据盘**（存放数据库、上传文件、备份）—— ECS 实例释放后数据不丢
- 一个域名（可选，但推荐；用于 HTTPS）

---

## 目录规划

| 用途 | 路径 | 所在磁盘 |
|---|---|---|
| 代码 | `/opt/oa-system/current` | 系统盘 |
| Python 虚拟环境 | `/opt/oa-system/venv` | 系统盘 |
| 静态文件（collectstatic） | `/opt/oa-system/shared/staticfiles` | 系统盘 |
| 数据库 | `/data/oa-system/db.sqlite3` | **数据盘** |
| 用户上传文件 | `/data/oa-system/media` | **数据盘** |
| 数据库备份 | `/data/oa-system/backups` | **数据盘** |
| 环境变量 | `/opt/oa-system/.env` | 系统盘 |

> 原则：系统盘只放可重建的内容（代码、venv），数据盘放所有不可恢复的数据。

---

## 第一步：挂载数据盘

在阿里云控制台为 ECS 挂载数据盘后，SSH 登录服务器执行：

```bash
# 查看数据盘设备名（通常是 /dev/vdb）
lsblk

# 格式化（如果新盘）
sudo mkfs.ext4 /dev/vdb

# 创建挂载点并挂载
sudo mkdir -p /data
sudo mount /dev/vdb /data

# 设置开机自动挂载
echo '/dev/vdb /data ext4 defaults 0 0' | sudo tee -a /etc/fstab

# 创建 OA 数据目录，并将属主设为你当前的部署用户（后续会改为 www-data）
sudo mkdir -p /data/oa-system/media /data/oa-system/backups
sudo chown -R $USER:$USER /data/oa-system
```

---

## 第二步：服务器准备

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx sqlite3
```

---

## 第三步：获取代码与依赖

```bash
# 创建目录
sudo mkdir -p /opt/oa-system/shared/staticfiles
sudo chown -R $USER:$USER /opt/oa-system

# 拉取代码
git clone <你的仓库地址> /opt/oa-system/current

# 创建虚拟环境并安装依赖
python3 -m venv /opt/oa-system/venv
/opt/oa-system/venv/bin/pip install -U pip
/opt/oa-system/venv/bin/pip install -r /opt/oa-system/current/requirements.txt
```

---

## 第四步：配置环境变量

```bash
cp /opt/oa-system/current/deploy/.env.example /opt/oa-system/.env
```

然后编辑 `/opt/oa-system/.env`，**至少修改以下项**：

| 变量 | 说明 |
|---|---|
| `DJANGO_SECRET_KEY` | 生成一个随机字符串：`python3 -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DJANGO_ALLOWED_HOSTS` | 你的域名或 ECS 公网 IP |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | 带 `https://` 前缀的域名 |
| `DJANGO_SQLITE_PATH` | 指向数据盘：`/data/oa-system/db.sqlite3` |
| `DJANGO_MEDIA_ROOT` | 指向数据盘：`/data/oa-system/media` |

---

## 第五步：数据库迁移与静态文件

```bash
cd /opt/oa-system/current

# 加载环境变量
set -a
. /opt/oa-system/.env
set +a

# 数据库迁移
/opt/oa-system/venv/bin/python manage.py migrate

# 收集静态文件
/opt/oa-system/venv/bin/python manage.py collectstatic --noinput

# 创建管理员账号
/opt/oa-system/venv/bin/python manage.py createsuperuser
```

### 开启 SQLite WAL 模式

WAL（Write-Ahead Logging）允许并发读写，显著减少「database is locked」错误：

```bash
sqlite3 /data/oa-system/db.sqlite3 'PRAGMA journal_mode=WAL;'
```

> WAL 模式只需设置一次，重启后仍然有效。

---

## 第六步：权限配置

`www-data` 用户（Gunicorn/Nginx 的运行用户）需要写数据库和上传目录。部署完成后，将数据目录交给 www-data：

```bash
sudo chown -R www-data:www-data /data/oa-system
sudo chown -R www-data:www-data /opt/oa-system/shared/staticfiles
```

---

## 第七步：配置 systemd（Gunicorn）

```bash
sudo cp /opt/oa-system/current/deploy/oa-system.service /etc/systemd/system/oa-system.service
sudo systemctl daemon-reload
sudo systemctl enable --now oa-system
sudo systemctl status oa-system --no-pager
```

验证 socket 已创建：

```bash
ls -la /run/oa-system/gunicorn.sock
```

---

## 第八步：配置 Nginx

```bash
sudo cp /opt/oa-system/current/deploy/nginx-oa-system.conf /etc/nginx/sites-available/oa-system.conf
```

```bash
编辑 `/etc/nginx/sites-available/oa-system.conf`，将 `server_name` 改为你的域名或 IP。

或者用 sudo sed -i 's/server_name your-domain.com;/server_name oasystem.avenue.limited;/' /etc/nginx/sites-available/oa-system.conf
```

```bash
sudo ln -sf /etc/nginx/sites-available/oa-system.conf /etc/nginx/sites-enabled/oa-system.conf

# 删除默认站点（避免冲突）
sudo rm -f /etc/nginx/sites-enabled/default

sudo nginx -t
sudo systemctl reload nginx
```

---

## 第九步：配置防火墙 / 安全组

在**阿里云控制台 → ECS → 安全组**中开放以下端口：

| 端口 | 用途 |
|---|---|
| 80 | HTTP |
| 443 | HTTPS（配置证书后开放） |

不建议直接开放 8000（Gunicorn 端口），外部流量应全部经过 Nginx。

服务器本地防火墙（如果开启了 ufw）：

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp   # SSH
sudo ufw enable
```

---

## 第十步：数据库备份

创建备份脚本 `/opt/oa-system/scripts/backup-db.sh`：

```bash
#!/bin/bash
BACKUP_DIR="/data/oa-system/backups"
DB_PATH="/data/oa-system/db.sqlite3"
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"
sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/db-$(date +%Y%m%d-%H%M%S).sqlite3'"
find "$BACKUP_DIR" -name "db-*.sqlite3" -mtime +$RETENTION_DAYS -delete
echo "[$(date)] Backup completed"
```

设置权限和定时任务：

```bash
sudo chmod +x /opt/oa-system/scripts/backup-db.sh

# 每小时备份，保留 30 天
# 注意：日志必须写到 www-data 有写权限的路径（数据盘），
# 不能写 /var/log —— www-data 无权在那里创建文件，
# 重定向失败会导致脚本完全不会执行（且无任何报错）。
echo "0 * * * * /opt/oa-system/scripts/backup-db.sh >> /data/oa-system/backups/backup.log 2>&1" | sudo crontab -u www-data -
```

> 如需远程备份，可在脚本末尾添加 `ossutil cp` 或 `rsync` 将备份同步到 OSS/其他服务器。

### 验证备份

```bash
# 备份目录里应有按小时生成的 db-*.sqlite3 文件
ls -lt /data/oa-system/backups/ | head -5

# 日志应每小时新增一行 "Backup completed"
sudo tail -20 /data/oa-system/backups/backup.log

# 确认 crontab 已注册
sudo crontab -u www-data -l
```

---

## HTTPS（推荐）

如果你已绑定域名，使用 certbot 配置免费 HTTPS 证书：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

证书配置成功后，在 `/opt/oa-system/.env` 中开启：

```
DJANGO_SECURE_SSL_REDIRECT=1
```

然后重启：`sudo systemctl restart oa-system`

---

## 更新部署

后续代码更新流程：

```bash
cd /opt/oa-system/current
git pull
/opt/oa-system/venv/bin/pip install -r requirements.txt
sudo chown devuser:devuser /data/oa-system /data/oa-system/db.sqlite3
/opt/oa-system/venv/bin/python manage.py migrate
/opt/oa-system/venv/bin/python manage.py collectstatic --noinput
sudo chown -R www-data:www-data /data/oa-system
sudo systemctl restart oa-system
```

---

## 日志与排错

```bash
# Gunicorn / Django 日志
sudo journalctl -u oa-system -f

# Nginx 访问日志
sudo tail -f /var/log/nginx/access.log

# Nginx 错误日志
sudo tail -f /var/log/nginx/error.log

# 备份日志
sudo tail -f /var/log/oa-backup.log
```
