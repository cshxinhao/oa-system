# oa-system 部署（阿里云 ECS）

默认使用：Nginx 反代 + Gunicorn（WSGI）+ systemd 常驻。

## 目录规划

- /opt/oa-system/current：代码目录（git 拉取到这里）
- /opt/oa-system/venv：Python 虚拟环境
- /opt/oa-system/.env：环境变量文件（参考 deploy/.env.example）
- /opt/oa-system/shared/staticfiles：collectstatic 输出目录
- /opt/oa-system/shared/media：上传文件持久化目录
- /opt/oa-system/shared/db.sqlite3：SQLite 数据库（可选，推荐放 shared 便于权限管理）

## 服务器准备

安装基础依赖（以 Ubuntu 为例）：

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx
```

## 获取代码与依赖

```bash
sudo mkdir -p /opt/oa-system
sudo chown -R $USER:$USER /opt/oa-system
git clone <你的仓库地址> /opt/oa-system/current
python3 -m venv /opt/oa-system/venv
/opt/oa-system/venv/bin/pip install -U pip
/opt/oa-system/venv/bin/pip install -r /opt/oa-system/current/requirements.txt
```

## 配置环境变量

```bash
cp /opt/oa-system/current/deploy/.env.example /opt/oa-system/.env
```

至少需要修改：

- DJANGO_SECRET_KEY
- DJANGO_ALLOWED_HOSTS（域名或公网 IP）
- DJANGO_CSRF_TRUSTED_ORIGINS（带 https:// 的域名）
- CORS_*（如需跨域再配置）

## 数据库迁移与静态文件

```bash
cd /opt/oa-system/current
mkdir -p /opt/oa-system/shared/staticfiles /opt/oa-system/shared/media
touch /opt/oa-system/shared/db.sqlite3
set -a
. /opt/oa-system/.env
set +a
/opt/oa-system/venv/bin/python manage.py migrate
/opt/oa-system/venv/bin/python manage.py collectstatic --noinput
```

如果你暂时使用 SQLite，db.sqlite3 位于 current 目录；升级到 PostgreSQL/MySQL 时建议将数据库改为独立服务。

如果你暂时使用 SQLite，建议通过环境变量 DJANGO_SQLITE_PATH 把数据库放在 shared 目录（避免代码目录权限问题）；升级到 PostgreSQL/MySQL 时建议将数据库改为独立服务。

## 配置 systemd（Gunicorn）

```bash
sudo cp /opt/oa-system/current/deploy/oa-system.service /etc/systemd/system/oa-system.service
sudo systemctl daemon-reload
sudo systemctl enable --now oa-system
sudo systemctl status oa-system --no-pager
```

## 配置 Nginx

```bash
sudo cp /opt/oa-system/current/deploy/nginx-oa-system.conf /etc/nginx/sites-available/oa-system.conf
sudo ln -sf /etc/nginx/sites-available/oa-system.conf /etc/nginx/sites-enabled/oa-system.conf
sudo nginx -t
sudo systemctl reload nginx
```

## HTTPS（可选但推荐）

如果你已经绑定域名，建议用 certbot 配置 HTTPS，并在 .env 中开启：

- DJANGO_SECURE_SSL_REDIRECT=1

## 日志与排错

```bash
sudo journalctl -u oa-system -f
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```
