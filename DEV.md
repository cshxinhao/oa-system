# OA System — 开发者文档

> 面向 20–50 人规模公司的内部 OA 系统，部署在阿里云 ECS 上。

## 目录

- [项目概览](#项目概览)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [模块说明](#模块说明)
- [数据库设计](#数据库设计)
- [关键设计决策](#关键设计决策)
- [部署架构](#部署架构)
- [安全性分析](#安全性分析)
- [并发与数据一致性](#并发与数据一致性)
- [数据库备份与恢复](#数据库备份与恢复)
- [代码质量评审](#代码质量评审)
- [改进路线图](#改进路线图)

---

## 项目概览

这是一个基于 Django 4.2 的 **全栈 MVC（MTV）OA 系统**，前端使用 Bootstrap 5 服务端渲染模板，后端通过 Django REST Framework 提供 API。系统围绕小型企业的日常办公需求设计，涵盖组织架构、公告、请假、报销、会议室预订、文档管理等模块。

| 属性 | 值 |
|---|---|
| 框架 | Django 4.2 + DRF 3.16 |
| 数据库 | SQLite（可切换） |
| 前端 | Django Templates + Bootstrap 5.3 CDN |
| 部署 | Gunicorn + Nginx + systemd |
| 目标用户 | 20–50 人 |
| 当前状态 | 功能基本完备，可投入使用 |

---

## 技术栈

| 层级 | 技术 | 说明 |
|---|---|---|
| **语言** | Python 3.11 | README 推荐 conda 环境 |
| **Web 框架** | Django 4.2.x | 固定 `<5.0` |
| **API** | Django REST Framework 3.16 | Session + Basic 认证 |
| **数据库** | SQLite 3 | 通过 `DJANGO_SQLITE_PATH` 环境变量配置路径 |
| **状态机** | django-fsm 3.0 | 用于请假审批工作流 |
| **表单** | django-crispy-forms + Bootstrap 5 | 服务端渲染表单 |
| **过滤** | django-filter 25.1 | DRF 全局过滤器 |
| **WSGI 服务器** | Gunicorn 23 | 3 个 sync worker，Unix socket 绑定 |
| **反向代理** | Nginx | 静态/媒体文件直接服务 |
| **进程管理** | systemd | 生产环境常驻 |
| **声明但未使用** | Celery 5.6 + Redis 7.0 | 已在 `requirements.txt` 中，但代码中无任何引用 |

> **注意**：Celery 和 Redis 虽然已安装，但项目中没有 `celery.py`、没有 broker 配置、没有任何异步任务。如果暂时不需要异步任务队列，建议从 `requirements.txt` 中移除以减少依赖面。

---

## 项目结构

```
oa-system/
├── manage.py                    # Django 入口
├── requirements.txt             # Python 依赖
├── db.sqlite3                   # SQLite 数据库（开发环境）
├── README.md                    # 项目说明（中英文）
├── demands_tracking.md          # 需求跟踪表
├── oa_system/                   # Django 项目配置
│   ├── settings.py              # 全局设置（环境变量驱动）
│   ├── urls.py                  # 根 URL 配置 + DRF Router
│   ├── wsgi.py / asgi.py        # WSGI/ASGI 入口
├── apps/                        # 业务应用（sys.path 注入）
│   ├── core/                    # 用户、部门、仪表盘、权限管理
│   ├── hr/                      # 请假申请（django-fsm 工作流）
│   ├── finance/                 # 报销申请 + 费用明细
│   ├── admin_office/            # 公告管理
│   ├── docs/                    # 文档中心（文件上传）
│   └── meeting/                 # 会议室预订 + 可用性查询
├── trading/                     # 交易请求（纯信息页，无 model）
├── templates/                   # 全局 + 各 app 模板
│   ├── base.html                # 主布局（导航栏 + 侧边栏）
│   ├── index.html               # 仪表盘
│   ├── registration/login.html  # 登录页
│   └── <app>/                   # 各模块模板
├── static/                      # 静态资源（CSS + 图片）
├── media/                       # 用户上传文件
├── deploy/                      # 生产部署配置
│   ├── DEPLOY.md                # 部署文档
│   ├── .env.example             # 环境变量模板
│   ├── gunicorn.conf.py         # Gunicorn 配置
│   ├── nginx-oa-system.conf     # Nginx 配置
│   └── oa-system.service        # systemd 单元文件
├── scripts/run.sh               # 开发环境一键启动脚本
└── .trae/documents/             # 12 份设计文档（开发历程）
```

---

## 模块说明

### 1. 组织与用户（core）

- **User**：继承 `AbstractUser`，扩展 `employee_id`（工号）、`department`、`position`（职位）、`phone`
- **Department**：支持树形结构（`parent` 自引用），每个部门有 `manager`（部门负责人）
- **权限管理页**：超级用户可批量开关用户的 `docs.add_document` 和 `finance.can_check_reimbursement` 权限
- **Dashboard**：欢迎卡片 + 快捷入口 + 最新公告 + 待办列表（请假审批 + 报销审核/审批）

### 2. 请假管理（hr）

- **状态机**：`draft → pending → approved / rejected / withdrawn`（django-fsm 管理转换）
- **请假类型**：病假、年假、生日假、产假、陪产假、恩恤假、无薪假
- **半天假**：支持选择上午/下午
- **不连续日期**：通过 `LeaveApplicationDate` 存储多天，不要求连续日期
- **审批人选择**：提交时从候选列表选择审批人（部门负责人；申请人本人是部门负责人时为其上级部门负责人 + 全局审批人），表单预选部门负责人；全局审批人（`User.can_approve_all_leaves`，超管在 admin 后台设置）可审批所有请假，无部门员工也能通过全局审批人完成审批
- **审批留痕**：`approver` 为员工提交时选择的审批人，提交后不变；`reviewer` 记录实际处理（批准/拒绝）的人——全局审批人或超管代批时二者可能不同
- **年假额度**：`LeaveQuota` 按人按年按假种设置额度（admin 后台维护，`leave_type` 字段预留未来其他假种额度），已批准的年假自动计入已用；提交年假时余额不足禁止提交并提示；列表页最左侧 **Leave Quota** tab 展示本人全部额度（类型/年份/总额/已用/剩余），"我的申请" tab 显示年假使用 tag，待审批 tab 显示申请人的年假使用情况
- **工作日计算**：所有假种的请假天数均**排除周末**（按周一至周五计算，年假额度扣减与提交校验同此规则）；年假纯周末区间禁止提交
- **审批历史**：列表页三个 Tab（我的申请 / 待审批 / 审批历史），历史 = 分配给本人且已处理（批准/拒绝）的申请

### 3. 会议室预订（meeting）

- **MeetingRoom**：名称、位置、容量、启用状态
- **RoomBooking**：房间、组织者、标题、备注、访客人数、时间段、状态（booked / canceled）
- **冲突检测**：`conflicting_bookings()` 方法，检查 `start_at < end AND end_at > start` 重叠逻辑
- **可用性查询**：
  - 时间窗口可用房间查询（哪些房间在指定时间段空闲）
  - 某日空闲时段查询（merge busy ranges → invert → free slots）
- **取消**：仅限预订者本人或 staff

### 4. 报销管理（finance）

- **状态流转**：`DRAFT → SUBMITTED → CHECKED → APPROVED / REJECTED → PAID`
- **费用明细**：支持多币种（HKD/USD/CNY/EUR/GBP/JPY），汇率换算到 HKD
- **双人审批**：checker（持有 `can_check_reimbursement` 权限）+ approver（部门负责人层级）
- **审批人计算**：从申请人的部门层级自动推导

### 5. 公告（admin_office）

- 基本的 CRUD，staff 可创建，所有人可查看已发布公告

### 6. 文档中心（docs）

- 文件上传到 `docs/%Y/%m/`，支持公开/私有两种可见性
- 上传需 `docs.add_document` 权限

### 7. 交易请求（trading）

- 纯静态信息页，链接到外部 e-form 系统 `https://eform.avenue.limited/`
- 无 model、无 API，仅作入口

---

## 数据库设计

当前使用 **SQLite**，数据库文件路径可通过 `DJANGO_SQLITE_PATH` 环境变量配置。

### 核心表关系

```
Department ──┬── User (members)
             └── Department (parent, 自引用树形结构)

User ──┬── LeaveApplication (applicant / approver / reviewer)
       ├── LeaveQuota (user / year)
       ├── RoomBooking (organizer)
       ├── ReimbursementRequest (requester / checker / approver)
       ├── Notice (author)
       └── Document (uploader)

MeetingRoom ─── RoomBooking

ReimbursementRequest ─── ExpenseItem
```

### 关键索引

- `RoomBooking`: `(room, status, start_at, end_at)` — 冲突查询优化
- `RoomBooking`: `(organizer, status, start_at)` — 用户预订列表优化

### 数据量预估（50 人规模）

| 表 | 预估年增量 |
|---|---|
| User | ~50 行 |
| Department | ~10 行 |
| LeaveApplication | ~500–1000 行 |
| RoomBooking | ~2000–5000 行 |
| ReimbursementRequest | ~500–1000 行 |
| Document | ~200–500 行 |

数据量极小，SQLite 在性能上完全足够。真正的考量在于**并发写入**和**备份策略**（见下文）。

---

## 关键设计决策

### 1. 为什么是 Django MTV 而不是 SPA？

项目最初的 `.trae/documents/` 记录显示曾计划使用 React + Ant Design 前后端分离架构，但最终选择了 Django 全栈方案。对于 20–50 人的内部工具而言，这是合理的取舍——减少技术栈复杂度，降低维护成本，且服务端渲染对 OA 系统这种表单密集型应用天然友好。

### 2. 为什么是 SQLite？

简单、零运维成本。但存在并发写入限制和备份不够便利的问题。下文会详细讨论迁移到 PostgreSQL 的路线。

### 3. django-fsm 状态机

请假流程使用 `django-fsm` 管理状态转换，`FSMField(protected=True)` 确保状态不能直接赋值修改（必须通过 transition 方法）。这比手写状态检查更可靠。

### 4. 审批路由

请假采用「员工从候选列表自选审批人」的方式：候选 = 部门负责人（申请人本人是部门负责人时为其上级部门负责人）+ 全局审批人（`User.can_approve_all_leaves`）。审批权限检查同时保留组织层级规则，因此部门负责人、全局审批人、超管均可在待审批列表处理。报销仍采用「部门负责人 → 上级部门负责人」的层级路由规则。

---

## 部署架构

```
用户浏览器
    │
    ▼
Nginx (端口 80/443)
    │
    ├── /static/   → /opt/oa-system/shared/staticfiles/
    ├── /media/    → /opt/oa-system/shared/media/
    └── /           → Unix Socket → Gunicorn (3 sync workers)
                                        │
                                        ▼
                                  Django WSGI
                                        │
                                        ▼
                                  SQLite (WAL 模式)
```

### 服务器目录规划

```
/opt/oa-system/
├── current/          # Git 仓库（代码）
├── venv/             # Python 虚拟环境
├── .env              # 环境变量
└── shared/
    ├── staticfiles/  # collectstatic 输出
    ├── media/        # 用户上传文件
    └── db.sqlite3    # 数据库文件
```

### 更新部署流程

```bash
cd /opt/oa-system/current
git pull
/opt/oa-system/venv/bin/pip install -r requirements.txt
/opt/oa-system/venv/bin/python manage.py migrate
/opt/oa-system/venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart oa-system
```

---

## 安全性分析

### 已做好的

- 环境变量驱动的敏感配置（SECRET_KEY、ALLOWED_HOSTS）
- CSRF 保护（Django 内置）
- `LoginRequiredMixin` 覆盖所有页面视图
- DRF 权限类（IsAuthenticated、IsStaffOrReadOnly、IsStaffOrBookingOwner）
- 对象级权限控制（普通用户只能取消自己的预订、只能看自己的报销等）
- Session 认证（无 Token 泄露风险）

### 需要改进的

| 问题 | 严重度 | 说明 | 修复建议 |
|---|---|---|---|
| **SECRET_KEY 有硬编码回退值** | 🔴 高 | `settings.py:44` 包含一个不安全的 dev key 作为默认值 | 删除默认值，强制从环境变量读取；或在生产环境检测到默认 key 时拒绝启动 |
| **DEBUG 默认为 True** | 🔴 高 | `settings.py:48`，生产环境如果忘记设 `DJANGO_DEBUG=0` 将暴露详细错误信息 | 改为默认 `False` |
| **CORS_ALLOW_ALL_ORIGINS 默认为 True** | 🟡 中 | `settings.py:186`，对于仅内部使用的系统风险有限，但仍是坏实践 | 改为默认 `False` |
| **db.sqlite3 提交到仓库** | 🟡 中 | `.gitignore` 有 `*.sqlite3` 规则，但文件已被 Git 跟踪 | `git rm --cached db.sqlite3` 并确认 `.gitignore` 生效 |
| **API Basic Auth** | 🟡 中 | Basic Auth 通过 HTTP 头明文传输密码（除非强制 HTTPS） | 对于内部 OA 可接受；如果未来开放外部 API，改用 Token Auth 或 JWT |
| **Admin 路径未修改** | 🟢 低 | `/admin/` 是 Django 默认路径，容易成为自动扫描目标 | 可改为自定义路径，但内网系统影响有限 |

---

## 并发与数据一致性

### 会议室预订的并发问题

这是系统中最需要关注的并发场景。当多人同时预订同一会议室的时间段时，存在 **TOCTOU（Time-of-Check, Time-of-Use）竞态条件**。

#### 当前实现

```python
# apps/meeting/views.py (页面预订)
with transaction.atomic():
    self.object = form.save(commit=False)
    self.object.full_clean()    # ← SELECT 检查冲突
    self.object.save()           # ← INSERT 写入

# apps/meeting/api.py (API 预订)
booking = RoomBooking(organizer=..., status=..., **validated)
booking.full_clean()             # ← SELECT 检查冲突
booking.save()                   # ← INSERT 写入
```

#### 问题分析

```
时间线 →

请求 A                          请求 B
  │                               │
  ├─ BEGIN                        │
  ├─ SELECT (无冲突) ✓            ├─ BEGIN
  │                               ├─ SELECT (无冲突) ✓  ← 此时 A 还没写入！
  ├─ INSERT ✓                    ├─ INSERT ✓  ← 两个都成功了！
  ├─ COMMIT                      ├─ COMMIT

结果：同一会议室、同一时间段被重复预订 ❌
```

**为什么 SQLite 不能防止这个问题？**

- Django 对 SQLite 使用 `BEGIN`（延迟事务），写锁在实际写入时才获取
- 两个事务可以在检查阶段同时读取，然后都认为没有冲突
- SQLite 同一时间只允许一个 writer，但这里的问题是**都通过了检查**

#### 解决方案

**方案 A：`select_for_update()` 行锁（推荐短期方案）**

```python
from django.db import transaction

with transaction.atomic():
    # 锁定房间行，阻止其他事务并发读取
    room = MeetingRoom.objects.select_for_update().get(pk=room_id)
    if not room.is_active:
        raise ValidationError("房间不可用")
    
    # 现在冲突检查是安全的
    if RoomBooking.objects.filter(
        room=room, status='booked',
        start_at__lt=end_at, end_at__gt=start_at
    ).exists():
        raise ValidationError("时间段已被预订")
    
    RoomBooking.objects.create(room=room, ...)
```

> ⚠️ **SQLite 的 `select_for_update()` 行为**：在 SQLite 中，`select_for_update()` 实际上会获取一个表级保留锁。它不如 PostgreSQL 的 row-level lock 精确，但足以解决这个场景——因为它保证了在事务内，其他写事务无法修改被锁定的行。

**方案 B：数据库排除约束（推荐长期方案，需 PostgreSQL）**

```python
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField
from django.db.models import Func, Q

class RoomBooking(models.Model):
    # ... 现有字段 ...
    
    class Meta:
        constraints = [
            ExclusionConstraint(
                name='exclude_overlapping_booking',
                expressions=[
                    ('room', '='),
                    # 使用 tstzrange 排除重叠时间段
                    (Func('start_at', 'end_at', function='tstzrange'), '&&'),
                ],
                condition=Q(status='booked'),
            ),
        ]
```

这是最可靠的方案——数据库层面保证不可能插入冲突的预订。但需要 PostgreSQL。

**方案 C：乐观锁（适合 SQLite，实现简单）**

在 `RoomBooking` 上保留当前逻辑，但在 `perform_create` 中捕获 `IntegrityError` 并重试：

```python
def perform_create(self, serializer):
    for attempt in range(3):
        try:
            with transaction.atomic():
                booking = RoomBooking(...)
                booking.full_clean()
                booking.save()
                return
        except ValidationError:
            raise  # 真正的验证错误直接抛出
        except IntegrityError:
            if attempt == 2:
                raise ValidationError("预订失败，请重试")
```

> 但当前设计中没有数据库层唯一约束能触发 `IntegrityError`。这个方案需要配合一个额外的唯一约束，比如在该场景中不自然。

#### 实际风险评估

对于 20–50 人的公司：
- 同时预订同一会议室的概率非常低
- 即使发生了，当前的 `full_clean()` + `transaction.atomic()` 在大多数情况下有效
- **但如果这个系统要扩展到更大的规模，这个问题必须修复**

**建议**：短期内实施 **方案 A**（改动量小），中长期迁移 PostgreSQL 后使用 **方案 B**。

### 请假审批的并发

请假审批使用 `django-fsm` 的 `FSMField(protected=True)`，状态在 Python 层面通过 transition 方法修改。并发风险场景：

- 申请人撤回 + 审批人批准 同时发生

当前代码已经在 `LeaveApproveView.post()` 中检查了 `status != STATUS_PENDING` 的前置条件，并在 `transaction.atomic()` 中执行。django-fsm 在 transition 时会再次检查当前状态是否匹配 source——如果状态已变，会抛 `TransitionNotAllowed`。

**评估**：基本安全。django-fsm 的 transition 检查和 `transaction.atomic()` 的组合可以防止状态冲突。

---

## 数据库备份与恢复

### 当前状态

项目**没有任何数据库备份机制**——没有脚本、没有 cron job、没有备份文档。

### SQLite 备份方案

SQLite 的备份最简单也最可靠的方式是使用 SQLite 内置的 `.backup` 命令或在 Python 中使用 `sqlite3` 的连接备份 API。

#### 方案 1：定时文件复制（配合 WAL 模式）

```bash
#!/bin/bash
# /opt/oa-system/scripts/backup-db.sh

BACKUP_DIR="/opt/oa-system/backups"
DB_PATH="/opt/oa-system/shared/db.sqlite3"
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"

# 使用 sqlite3 .backup 命令（比直接 cp 更安全，处理 WAL 文件）
sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/db-$(date +%Y%m%d-%H%M%S).sqlite3'"

# 删除旧备份
find "$BACKUP_DIR" -name "db-*.sqlite3" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $(date)"
```

#### 方案 2：Python 备份 API（更可靠）

```python
# 通过 Django management command 执行
import sqlite3
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    def handle(self, **options):
        source = sqlite3.connect(settings.DATABASES['default']['NAME'])
        dest = sqlite3.connect(f'/backups/db-{timestamp}.sqlite3')
        source.backup(dest)
        dest.close()
        source.close()
```

#### 方案 3：阿里云 OSS 自动同步

将备份文件同步到阿里云 OSS：

```bash
# 备份后上传到 OSS
/opt/oa-system/venv/bin/python manage.py backup_db  # 自定义命令
# 或用 ossutil
ossutil cp /opt/oa-system/backups/db-*.sqlite3 oss://oa-backups/
```

#### 建议的备份策略

| 频率 | 方式 | 保留 |
|---|---|---|
| 每 1 小时 | `sqlite3 .backup` 本地文件 | 保留 24 个 |
| 每天 | 本地备份 + 上传到 OSS | 保留 30 天 |
| 每周 | 本地完整备份（含 media 文件） | 保留 12 周 |

**Cron 配置**：
```
0 * * * * /opt/oa-system/scripts/backup-db.sh           # 每小时
0 2 * * * /opt/oa-system/scripts/backup-full.sh          # 每天凌晨2点
0 3 * * 0 /opt/oa-system/scripts/backup-upload-oss.sh    # 每周日凌晨3点上传 OSS
```

### 数据库切换：SQLite → PostgreSQL

对于生产环境，建议在部署前或早期迁移到 PostgreSQL。阿里云提供：

- **云数据库 RDS for PostgreSQL**：托管服务，自动备份、监控、容灾，推荐
- **自建 PostgreSQL on ECS**：省钱但需要自己管理备份

#### 迁移步骤

1. 安装 `psycopg2-binary` 并更新 `requirements.txt`
2. 修改 `settings.py` 的 `DATABASES` 配置，通过 `DATABASE_URL` 环境变量切换
3. 使用 `django-admin dumpdata` / `loaddata` 迁移数据（数据量小，完全可行）
4. 添加 `django.contrib.postgres` 的 ExclusionConstraint（会议室预订）
5. 配置 RDS 的自动备份策略

```python
# settings.py 推荐的数据库配置
import dj_database_url  # 可选，简化配置

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}")

if DATABASE_URL.startswith('sqlite'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': DATABASE_URL.replace('sqlite:///', ''),
        }
    }
else:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL),
    }
```

---

## 代码质量评审

### 做得好的方面 ✅

1. **清晰的应用分层**：`apps/` 下每个模块职责明确，`models.py` / `views.py` / `services.py` / `api.py` 结构一致
2. **django-fsm 状态机**：请假流程的状态转换规则显式声明，优于手工 if-else 状态检查
3. **审批路由设计**：层级部门自动推导审批人，避免了硬编码
4. **服务层抽象**：`meeting/services.py` 的 `_merge_ranges` / `_invert_ranges` 算法清晰可测试
5. **DRF ViewSet + Router**：API 定义简洁，自定义 action 命名清晰
6. **SELECT 相关优化**：`select_related` / `prefetch_related` 使用得当，避免 N+1 查询
7. **环境变量驱动配置**：密钥、数据库路径、CORS 等都可通过环境变量覆盖
8. **部署文档**：`deploy/DEPLOY.md` 覆盖了从服务器准备到 HTTPS 配置的完整流程

### 需要改进的方面

#### 🔴 高优先级

1. **会议室预订竞态条件**
   - 文件：`apps/meeting/views.py:51-55`、`apps/meeting/api.py:67-76`
   - 问题：TOCTOU，详见上文并发分析
   - 修复：使用 `select_for_update()` 锁定房间行

2. **SECRET_KEY 硬编码默认值**
   - 文件：`oa_system/settings.py:44`
   - 修复：删除默认值；生产环境缺失时拒绝启动
   ```python
   SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
   if not SECRET_KEY:
       raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set")
   ```

3. **DEBUG 默认 True**
   - 文件：`oa_system/settings.py:48`
   - 修复：改为 `default=False`

4. **数据库无备份机制**
   - 详见上文备份方案

#### 🟡 中优先级

5. **代码重复：审批人计算逻辑**
   - 文件：`apps/core/views.py` 和 `apps/finance/views.py`
   - 问题：`get_approver_for_reimbursement` 在两个文件中独立实现
   - 修复：提取到 `apps/finance/services.py` 或 `apps/core/services.py`，统一调用

6. **Celery + Redis 声明但未使用**
   - 文件：`requirements.txt`
   - 建议：如果近期不需要异步任务（如邮件通知、定时报表），从依赖中移除；如果需要，应添加 `celery.py` 配置
   - 典型 OA 异步场景：发送邮件通知（请假审批结果、报销状态变更）、定时生成报表

7. **API 缺少速率限制**
   - 当前 DRF 没有配置 throttle
   - 建议添加：
   ```python
   REST_FRAMEWORK = {
       # ... 现有配置 ...
       'DEFAULT_THROTTLE_CLASSES': [
           'rest_framework.throttling.AnonRateThrottle',
           'rest_framework.throttling.UserRateThrottle',
       ],
       'DEFAULT_THROTTLE_RATES': {
           'anon': '100/hour',
           'user': '1000/hour',
       }
   }
   ```

8. **日志配置缺失**
   - `settings.py` 中没有 `LOGGING` 配置
   - 生产环境建议至少配置：
   ```python
   LOGGING = {
       'version': 1,
       'disable_existing_loggers': False,
       'handlers': {
           'file': {
               'level': 'WARNING',
               'class': 'logging.handlers.RotatingFileHandler',
               'filename': '/var/log/oa-system/django.log',
               'maxBytes': 10 * 1024 * 1024,  # 10 MB
               'backupCount': 5,
           },
       },
       'root': {
           'handlers': ['file'],
           'level': 'WARNING',
       },
   }
   ```

9. **CORS_ALLOW_ALL_ORIGINS 默认 True**
   - 文件：`oa_system/settings.py:186`
   - 建议：默认改为 `False`，生产环境通过 `.env` 显式配置

#### 🟢 低优先级

10. **trading 应用位置不一致**
    - 文件：`trading/` 位于项目根目录，而不是 `apps/trading/`
    - 影响：不影响功能，但破坏了项目结构约定
    - 建议：移动到 `apps/trading/`，或明确在 README 中说明

11. **测试覆盖**
    - 当前项目没有测试文件
    - 建议至少为核心模块（会议室冲突检测、请假状态机、审批路由）添加测试

12. **Gunicorn worker 数量**
    - `gunicorn.conf.py` 固定 3 个 sync worker
    - 对于 50 人并发使用，3 个 worker 基本够用（sync worker 一个请求阻塞一个 worker）
    - 建议：如果未来出现响应变慢，可以增加到 4–5 个，或改用 `gthread` worker class

13. **无健康检查端点**
    - 建议添加一个简单的 health check 供负载均衡或监控使用
    ```python
    # oa_system/urls.py
    path("health/", lambda r: HttpResponse("OK"))
    ```

14. **db.sqlite3 被 Git 跟踪**
    - `.gitignore` 已有 `*.sqlite3`，但文件之前被提交过
    - 修复：`git rm --cached db.sqlite3`

---

## 改进路线图

### 上线前（必须完成）

| 任务 | 工作量 | 说明 |
|---|---|---|
| SECRET_KEY 强制从环境变量读取 | 5 分钟 | 一行的修改 |
| DEBUG 默认改为 False | 1 分钟 | 一行修改 |
| 会议室预订加 `select_for_update()` | 30 分钟 | 防止并发冲突 |
| 数据库备份脚本 + cron | 1 小时 | 保命操作 |
| 确认 `.gitignore` 生效，移除 `db.sqlite3` | 5 分钟 | 防止泄露生产数据 |
| 生产环境 `.env` 配置检查 | 15 分钟 | 按 `.env.example` 逐项确认 |

### 上线后第一周

| 任务 | 工作量 | 说明 |
|---|---|---|
| 添加速率限制 | 15 分钟 | 防止滥用 API |
| 日志配置 | 30 分钟 | 排查问题必备 |
| 审批人计算逻辑去重 | 30 分钟 | 消除代码重复 |
| 添加健康检查端点 | 5 分钟 | 监控需要 |

### 第一个月

| 任务 | 工作量 | 说明 |
|---|---|---|
| 评估是否迁移 PostgreSQL | 取决于决策 | 如需迁移，预计 1–2 天含测试 |
| 添加核心模块测试 | 2–4 小时 | 会议室冲突、请假状态机、审批路由 |
| Celery/Redis 决策：启用或移除 | 取决于决策 | 如需异步通知，配置 Celery；否则移除依赖 |
| 会议室预订 ExclusionConstraint | 在迁移 PG 后实施 | 数据库层面防止冲突 |

### 远期优化

| 任务 | 说明 |
|---|---|
| 邮件/企业微信通知 | 审批请求实时通知 |
| ~~请假额度管理~~ | 每人每年请假天数追踪（已实现：LeaveQuota + 提交校验 + 列表展示） |
| 会议室预订提醒 | 会议开始前提醒 |
| 移动端适配 | 响应式优化（Bootstrap 5 本身已支持，但可进一步优化） |
| 操作审计日志 | 记录所有关键操作，满足合规需要 |
| 数据看板 | 请假统计、会议室使用率、报销分析 |

---

## 开发环境快速启动

```bash
# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 数据库迁移
python manage.py migrate

# 创建管理员
python manage.py createsuperuser

# 启动开发服务器
python manage.py runserver
```

或使用项目自带的脚本：
```bash
bash scripts/run.sh
```

访问 `http://localhost:8000` 即可使用。

---

*文档生成日期：2026-08-08*
*基于分支：main @ d8fc945*
