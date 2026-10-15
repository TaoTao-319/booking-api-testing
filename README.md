# 本地预约 API 测试

针对随项目提供的预约服务，使用 Postman/Newman 与 Python Requests/pytest 验证接口。覆盖鉴权、预约 CRUD、PATCH、输入异常、凭证失效、组合筛选和分页。

## 安装与运行

需要 Python 3.14 与 Node.js 22 或更高版本。创建并激活 Python 虚拟环境后执行：

```bash
python -m pip install -r requirements.txt
python scripts/run_tests.py
npm ci
python scripts/run_postman.py
```

pytest 入口自动创建临时服务，运行 43 个场景，核对数据清理并关闭服务。Postman 入口从 YAML 导出 JSON，分别运行普通与短有效期集合，各执行两轮。原生集合包含 113 条请求；请求数、断言数与 pytest 用例数分别统计。

报告保存到 `reports`，最近一次结果入口分别为 `reports/latest.json` 与 `reports/postman/latest.json`。将生成的 `postman/collection.json` 和环境 JSON 导入 Postman 可交互调试；需要先运行 `python local-api/server.py` 启动服务。

默认地址 `http://127.0.0.1:8000`，演示账号 `admin`，演示密码 `password123`，更新与删除使用 token Cookie。服务使用内存存储，重启后清空。测试脚本使用独立数据并检查清理，不接管其他服务。

`local-api` 是被测服务，`tests` 是 pytest 用例，`postman` 是集合与环境，`scripts` 是自动执行入口。接口契约以本地服务为准，不能直接替换成公开 RESTful Booker 地址沿用全部断言。

[接口契约](docs/api.md) · [测试场景](docs/test-cases.md)

## 验证记录

43 条 pytest 用例通过；Postman 两组各运行两轮，合计 226 次请求、300 项断言，无失败，清理检查通过。[执行摘要](docs/verification.json) · [HTML 报告](examples/pytest/report.html)
