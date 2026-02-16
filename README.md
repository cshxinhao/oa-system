# OA System

基于 Django 4.2 的简易 OA 系统，提供模板页后台与 DRF API，适合中小团队快速落地内部流程。

## 已实现功能

- 组织与员工
  - 自定义用户（工号、部门、职位、手机号）
  - 部门管理（含上级部门、负责人）
- 公告
  - 公告模型与 API（`/api/v1/notices/`）
  - 仪表盘展示最新公告
- 请假管理
  - 发起请假、查看我的请假
  - 审批/拒绝（按部门权限控制）
- 文档中心
  - 上传文档、公开/私有可见
- 会议室预订
  - 会议室资源（名称、位置、容量、可用状态）
  - 预订会议室（主题、开始/结束时间，冲突校验）
  - 可用时间查询
    - 按时间窗查询可用会议室
    - 按会议室查询某日空闲时段

## 运行方式（开发）

建议在本地开启调试模式（否则 Django admin 的静态资源不会由 `runserver` 提供，表现为“只有文字和链接、没有样式”）。

```bash
export DJANGO_DEBUG=1
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

如果你不想改环境变量，也可以临时用：

```bash
python manage.py runserver --insecure 0.0.0.0:8000
```

数据库默认 SQLite（`db.sqlite3`），可通过环境变量 `DJANGO_SQLITE_PATH` 指定路径。

## Web 页面入口

- 仪表盘：`/`
- 请假：`/hr/leaves/`
- 文档：`/docs/documents/`
- 会议室预订：`/meeting/bookings/`
- 可用时间查询：`/meeting/availability/`
- 管理后台：`/admin/`

## API（/api/v1）

- 用户：`/api/v1/users/`（只读）
- 部门：`/api/v1/departments/`（只读）
- 公告：`/api/v1/notices/`
- 会议室：`/api/v1/meeting-rooms/`
  - 可用会议室：`/api/v1/meeting-rooms/available?start_at=...&end_at=...`
  - 空闲时段：`/api/v1/meeting-rooms/{id}/free-slots?date=YYYY-MM-DD&day_start=09:00&day_end=18:00`
- 会议室预订：`/api/v1/room-bookings/`
  - 取消预订：`POST /api/v1/room-bookings/{id}/cancel/`

## 部署建议（生产）

建议使用 Nginx 反向代理 + Gunicorn（WSGI）+ systemd；静态文件与媒体文件由 Nginx 托管。
