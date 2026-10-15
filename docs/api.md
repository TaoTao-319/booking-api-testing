# 预约接口契约

本项目测试随仓库提供的内存服务。默认监听 127.0.0.1:8000；自动执行入口使用系统分配的独立端口。

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | /ping | 健康检查 |
| POST | /auth | 使用演示账号获取 token |
| DELETE | /auth | 注销当前 token |
| GET | /booking | 列表、组合筛选及分页 |
| POST | /booking | 创建预约 |
| GET | /booking/{id} | 查询预约 |
| PUT | /booking/{id} | 完整更新，需要 token Cookie |
| PATCH | /booking/{id} | 部分更新，需要 token Cookie |
| DELETE | /booking/{id} | 删除预约，需要 token Cookie |

预约数据包含 firstname、lastname、totalprice、depositpaid、bookingdates；日期包含 checkin、checkout。示例见 tests/data/booking.json。输入校验、查询参数和完整响应约定分别由 tests/test_validation.py、tests/test_query.py 和 local-api/server.py 定义。

创建成功返回 200，删除成功返回 201。无效输入返回 400，错误登录返回 401，缺失或无效的操作凭证返回 403，不存在的资源返回 404。凭证过期与注销分别验证；不允许把被拒绝的操作视为数据修改成功。
