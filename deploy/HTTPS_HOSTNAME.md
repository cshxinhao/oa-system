# 域名绑定 & HTTPS 配置指南

在服务器已完成基本部署（DEPLOY.md）的基础上，绑定域名并开启 HTTPS。

## 前提

- 已完成 `deploy/DEPLOY.md` 的前八步
- IT 已为你的 ECS 公网 IP 配置 DNS A 记录（例如 `oasystem.avenue.limited → 47.243.197.247`）

## 第一步：更新 Nginx 域名

将 Nginx 的 `server_name` 从占位符改为你的域名：

```bash
sudo sed -i 's/server_name your-domain.com;/server_name oasystem.avenue.limited;/' /etc/nginx/sites-available/oa-system.conf
sudo nginx -t && sudo systemctl reload nginx
```

## 第二步：更新项目环境变量

编辑 `/opt/oa-system/.env`，更新以下三项：

```
DJANGO_ALLOWED_HOSTS=oasystem.avenue.limited,47.243.197.247
DJANGO_CSRF_TRUSTED_ORIGINS=https://oasystem.avenue.limited
DJANGO_SECURE_SSL_REDIRECT=0
```

> `SECURE_SSL_REDIRECT` 先保持 `0`，等 HTTPS 配置好后再改为 `1`。

## 第三步：配置 HTTPS 证书

使用 Let's Encrypt 免费证书：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d oasystem.avenue.limited
```

按提示输入邮箱地址，同意服务条款。certbot 会自动验证域名所有权，生成证书，并修改 Nginx 配置。

> 证书有效期 90 天，certbot 会自动添加定时任务续期，无需手动操作。

## 第四步：开启 HTTPS 重定向

编辑 `/opt/oa-system/.env`，把最后一项改为：

```
DJANGO_SECURE_SSL_REDIRECT=1
```

然后重启应用服务：

```bash
sudo systemctl restart oa-system
```

## 验证

浏览器访问 `https://oasystem.avenue.limited/`，地址栏应显示小锁图标，页面正常加载。
