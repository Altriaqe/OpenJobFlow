# 城市岗位统计只读 API 设计

日期：2026-08-05

状态：设计已确认，等待实现计划

## 1. 背景与目标

JobFlow 已经建立 PostgreSQL 普通 View `mart.city_job_counts`，用于统计 `core.jobs` 中当前全部岗位的城市数量。下一阶段为这个指标增加一个固定的 FastAPI 只读接口，供 Dashboard、AI Summary Service 和其他外部客户端使用。

本阶段只实现一个固定接口，不建设通用 SQL 查询协议。

## 2. 接口范围

接口：

```http
GET /analytics/cities?limit=20
```

响应直接返回数组：

```json
[
  {"city": "兰州", "job_count": 12},
  {"city": "杭州", "job_count": 8}
]
```

`limit` 规则：

- 默认值为 `20`。
- 最小值为 `1`。
- 最大值为 `100`。
- 缺少、为 `0` 或超过 `100` 时，由 FastAPI 参数校验返回 `422`。

查询结果按 `job_count DESC, city ASC` 排序。岗位数量相同时按城市名称升序，保证结果顺序稳定。

## 3. 数据流与模块边界

```text
HTTP 请求
    ↓
FastAPI /analytics/cities 路由
    ↓
list_city_job_counts() 查询函数
    ↓
mart.city_job_counts
    ↓
JSON 响应
```

计划新增文件：

```text
src/jobflow/api/__init__.py
src/jobflow/api/app.py
src/jobflow/api/analytics.py
src/jobflow/db/analytics.py
tests/api/test_analytics.py
```

职责划分：

- `src/jobflow/db/analytics.py`：执行固定的参数化查询，并把数据库行转换为查询结果。
- `src/jobflow/api/analytics.py`：定义 `/analytics/cities` 路由，接收 `limit`，调用查询函数并返回响应。
- `src/jobflow/api/app.py`：创建 FastAPI 应用并注册路由。
- `tests/api/test_analytics.py`：验证 HTTP 响应、参数边界和错误行为。

真实 PostgreSQL 的链路验证继续放在 `tests/integration/` 中。

## 4. 查询约束

查询函数只执行固定的只读 SQL：

```sql
SELECT city, job_count
FROM mart.city_job_counts
ORDER BY job_count DESC, city ASC
LIMIT %s;
```

请求方不能传入任意 SQL、表名、字段名、排序表达式或写操作。API 不直接读取 `raw` 表，也不公开单条岗位或招聘者信息。

## 5. 响应与错误处理

当 View 有数据时，返回 HTTP `200` 和城市统计数组。

当 View 没有数据时，返回 HTTP `200` 和空数组：

```json
[]
```

空数据是正常业务状态，不视为服务器错误。

当数据库连接或查询失败时，返回 HTTP `503` 和通用错误信息：

```json
{"detail": "analytics database unavailable"}
```

不得向调用方返回 SQL、连接字符串、数据库密码或内部堆栈。

## 6. 依赖与部署边界

实现阶段需要补充 FastAPI 运行依赖，并确认本地启动方式。第一版不引入 Django、SQLAlchemy ORM、复杂权限系统或通用查询构建器。

本地学习阶段可以复用现有 PostgreSQL 连接配置。生产部署阶段必须为 API 使用只读数据库凭据，保持写入与读取分离：

```text
ETL Worker：写数据库
FastAPI：读聚合结果
AI 服务和机器人：调用 FastAPI
```

## 7. 测试设计

### 查询函数测试

- 验证查询使用 `mart.city_job_counts`。
- 验证 `limit` 作为参数传入，而不是拼接 SQL。
- 验证数据库行正确转换为 `city` 和 `job_count`。

### API 路由测试

- 默认 `limit=20`。
- 合法自定义 limit 可以生效。
- `limit=0` 和 `limit=101` 返回 `422`。
- 有数据时返回正确 JSON。
- 无数据时返回 `[]`。
- 数据库异常时返回 `503`，且不暴露内部错误细节。

### PostgreSQL 集成测试

使用真实 PostgreSQL 验证：

```text
core.jobs
→ mart.city_job_counts
→ API 查询结果
```

现有 `mart.city_job_counts` 动态 View 测试已经证明基础数据变化会自动反映到 View；API 测试将继续验证该结果能被安全地通过 HTTP 读取。

## 8. 成功标准

- FastAPI 应用可以在本地启动。
- `GET /analytics/cities` 返回城市和岗位数量。
- `limit` 的默认值和边界校验符合本设计。
- API 只执行聚合只读查询。
- 单元测试、API 测试和相关集成测试通过。
- Ruff、格式检查和 Git 差异检查通过。
- 不修改 Worker 的写库事务边界。
- 不公开 `raw` 数据、单条岗位详情或数据库凭据。
