# Go-Live Checklist

> 上线前逐项确认和修复，按优先级排列。

---

## CRITICAL — 必须立刻处理

### 1. 更换 SECRET_KEY

当前 `.env.example` 中为 `DJANGO_SECRET_KEY=change-me`，如果服务器 `.env` 用的就是这个值，任何人都可以伪造 session cookie，冒充任意用户（包括 superuser）登录系统。

**修复方式**：在服务器上生成一个真随机 key：

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

把输出写入 `/opt/oa-system/.env` 的 `DJANGO_SECRET_KEY=` 一行，然后重启服务。

---

## HIGH — 今晚改完

### 2. finance 三个 view 缺少 @login_required

**文件**：`apps/finance/views.py`

`submit_reimbursement`、`check_reimbursement`、`approve_reject_reimbursement` 三个函数 view 没有加 `@login_required` 装饰器。目前靠 `AnonymousUser` 语义「碰巧」安全，但任何代码变更可能导致未登录即可操作。

**修复**：给这三个函数都加上 `@login_required`。

### 3. 报销详情页数据泄露

**文件**：`apps/finance/views.py` — `ReimbursementDetailView.get_queryset()`

当前返回 `ReimbursementRequest.objects.all()`，任何登录用户输入 URL 都能看到他人的报销金额和明细（模板渲染了 requester、total_amount、expense items）。

**修复**：将 queryset 限制为与当前用户相关的记录：
```python
def get_queryset(self):
    user = self.request.user
    if user.is_superuser:
        return ReimbursementRequest.objects.all()
    return ReimbursementRequest.objects.filter(
        Q(requester=user) | Q(checker=user) | Q(approver=user)
    ).distinct()
```

### 4. 任何用户都能通过 API 增删改公告

**文件**：`apps/admin_office/views.py` — `NoticeViewSet`

当前 `permission_classes = [IsAuthenticatedOrReadOnly]`，意味着任何登录员工都能通过 API 创建、修改、删除公司公告。

**修复**：改为仅 staff 可写：
```python
from rest_framework.permissions import IsAuthenticated, IsAdminUser, SAFE_METHODS

class IsStaffOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(request.user and request.user.is_staff)

permission_classes = [IsStaffOrReadOnly]
```

---

## MEDIUM — 建议改完再上线

### 5. SQLite 强制 WAL 模式

**文件**：`oa_system/settings.py` — `DATABASES` 配置

WAL 模式目前仅靠手动执行一行 SQL（`DEPLOY.md` 中有文档记录）。一旦数据库文件重建（如 fresh migrate），就会退回到默认的 rollback journal 模式，多用户并发写入时会报 `database is locked`。

**修复**：在 `DATABASES['default']['OPTIONS']` 中加 `init_command`：

```python
"OPTIONS": {
    "init_command": (
        "PRAGMA journal_mode=WAL;"
        "PRAGMA busy_timeout=5000;"
        "PRAGMA synchronous=NORMAL;"
    ),
    "timeout": 20,
}
```

**验证**：连上生产数据库执行：
```bash
sqlite3 /data/oa-system/db.sqlite3 "PRAGMA journal_mode;"
# 预期输出: wal
```

### 6. 确认 .env 配置正确

登录服务器，确认 `/opt/oa-system/.env` 中以下值与实际环境一致：

| 变量 | 正确值 | 说明 |
|---|---|---|
| `DJANGO_DEBUG` | `0` | 调试模式必须关闭 |
| `DJANGO_SECRET_KEY` | 随机生成的真实 key | 不能是 change-me |
| `CORS_ALLOW_ALL_ORIGINS` | `0` | 禁止跨域 |
| `ALLOWED_HOSTS` | 实际域名（如 `oa.example.com`） | 不匹配则全站 400 |
| `CSRF_TRUSTED_ORIGINS` | `https://实际域名` | HTTPS 下 CSRF 必需 |
| `DISABLED_MODULES` | `finance,trading` | 隐藏 sidebar 中不需要的模块 |
| `DJANGO_SECURE_SSL_REDIRECT` | `1` | 强制 HTTPS |

### 7. 静态文件收集 + 验证

```bash
# 确保 collectstatic 已执行
cd /opt/oa-system/current
source venv/bin/activate
python manage.py collectstatic --noinput

# 验证 nginx 正确服务静态文件
curl -sI https://你的域名/static/css/style.css | head -1
# 预期: HTTP/1.1 200 OK
```

### 8. 数据库备份确认

确认 `DEPLOY.md` 中的备份脚本正在运行：
```bash
# 备份目录里应有按小时生成的 db-*.sqlite3 文件
ls -lt /data/oa-system/backups/ | head -5

# 日志应每小时新增一行 "Backup completed"
sudo tail -20 /data/oa-system/backups/backup.log
```

> 注意：备份日志必须写到 `/data/oa-system/backups/backup.log`（数据盘），
> 不能写 `/var/log/` —— www-data 无权在那里创建文件，重定向失败会导致
> cron 里的备份脚本完全不会执行且无任何报错。

---

## LOW — 上线后尽快处理

### 9. 媒体文件无认证

`media/docs/` 下的文件由 nginx 直接服务，绕过 Django 登录校验。设为非公开（`is_public=False`）的文档，任何人知道 URL 就能直接下载。如果文档模块存放敏感文件，需要改为通过 Django view 代理下载（`X-Accel-Redirect`）。

### 10. 无登录限速

`/accounts/login/` 和 `/admin/` 目前没有失败重试限制。对于 20 人内网风险较低，但后续可加 `django-axes` 或在 nginx 层配置 rate limit。

### 11. DRF 中的 BasicAuthentication

`settings.py` 中 `REST_FRAMEWORK` 的 `DEFAULT_AUTHENTICATION_CLASSES` 包含了 `BasicAuthentication`。这意味着 API 支持用户名密码 base64 传参，在非 HTTPS 下容易泄露。如果不需要 API basic auth，移除该项仅保留 `SessionAuthentication`。

### 12. COOKIE 安全标记

上线 HTTPS 确认正常后，在 `settings.py` 添加：
```python
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
```

---

## 快速上线检查清单

上线当天逐条打勾：

- [ ] `DJANGO_SECRET_KEY` 已替换为真随机值
- [ ] `DJANGO_DEBUG=0` 确认
- [ ] finance views 已加 `@login_required`
- [ ] 报销详情 queryset 已限制
- [ ] 公告 API 写权限已限制为 staff
- [ ] SQLite WAL 已确认开启
- [ ] `collectstatic` 已执行
- [ ] 首页能正常打开
- [ ] 登录 / 登出正常
- [ ] 数据库备份 timer 运行中
