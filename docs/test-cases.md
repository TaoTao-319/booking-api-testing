# API 测试场景

43 条 pytest 场景，参数化输入分别计数。执行证据见 [运行摘要](verification.json) 和 [HTML 报告](../examples/pytest/report.html)。

| 编号 | 操作和输入 | 预期结果 | pytest用例 | 本次结果 |
|---|---|---|---|---|
| API-001 | POST /auth，正确账号配错误密码 | 401，Bad credentials，没有token键 | `tests/test_auth.py::test_login_with_wrong_password` | 通过 |
| API-002 | PUT或DELETE自己的预约，缺少或伪造token；PUT无token | 403，完整预约保持原样 | `tests/test_auth.py::test_booking_rejects_bad_credentials[put_without_token]` | 通过 |
| API-003 | PUT或DELETE自己的预约，缺少或伪造token；PUT伪造token | 403，完整预约保持原样 | `tests/test_auth.py::test_booking_rejects_bad_credentials[put_with_invalid_token]` | 通过 |
| API-004 | PUT或DELETE自己的预约，缺少或伪造token；DELETE无token | 403，完整预约保持原样 | `tests/test_auth.py::test_booking_rejects_bad_credentials[delete_without_token]` | 通过 |
| API-005 | PUT或DELETE自己的预约，缺少或伪造token；DELETE伪造token | 403，完整预约保持原样 | `tests/test_auth.py::test_booking_rejects_bad_credentials[delete_with_invalid_token]` | 通过 |
| API-006 | 登录并创建预约，注销后使用旧token更新 | 403，完整预约保持原样 | `tests/test_auth.py::test_logged_out_token_cannot_update_booking` | 通过 |
| API-007 | 检查fixture创建预约的响应 | 200，正整数动态ID及完整数据一致 | `tests/test_booking.py::test_create_booking` | 通过 |
| API-008 | GET /booking | 200，列表包含本次创建的ID | `tests/test_booking.py::test_list_bookings` | 通过 |
| API-009 | GET本次预约详情 | 200，完整数据与创建输入一致 | `tests/test_booking.py::test_get_booking` | 通过 |
| API-010 | 按唯一姓名查询，再使用不匹配姓氏 | 200，分别返回本次预约或空列表 | `tests/test_booking.py::test_filter_booking_by_name` | 通过 |
| API-011 | PUT把价格200改为300，再次GET | 200，响应及再次查询均是更新后的数据 | `tests/test_booking.py::test_put_booking` | 通过 |
| API-012 | 用有效token删除本次预约 | 201，Booking deleted | `tests/test_booking.py::test_delete_booking` | 通过 |
| API-013 | GET /ping | 200，status为ok | `tests/test_health.py::test_ping` | 通过 |
| API-014 | 创建并删除后GET同一ID | 404，Booking or endpoint not found | `tests/test_not_found.py::test_get_deleted_booking` | 通过 |
| API-015 | 创建并删除后，用有效token PUT同一ID | 404，Booking not found | `tests/test_not_found.py::test_put_deleted_booking` | 通过 |
| API-016 | 创建并删除后，用有效token再次DELETE | 404，Booking not found | `tests/test_not_found.py::test_delete_deleted_booking` | 通过 |
| API-017 | 按唯一姓名查询三条预约，不带分页 | 200，ID完整且格式正确 | `tests/test_query.py::test_query_without_pagination` | 通过 |
| API-018 | 唯一姓名加已付或未付订金筛选；已支付订金 | 200，只包含同时满足条件的ID | `tests/test_query.py::test_filter_by_name_and_deposit[name_and_paid]` | 通过 |
| API-019 | 唯一姓名加已付或未付订金筛选；未支付订金 | 200，只包含同时满足条件的ID | `tests/test_query.py::test_filter_by_name_and_deposit[name_and_unpaid]` | 通过 |
| API-020 | 查询价格范围200至300 | 200，包含200和300，排除100 | `tests/test_query.py::test_filter_by_price_range` | 通过 |
| API-021 | 唯一姓名加入住、退房或组合日期；入住日期 | 200，精确匹配对应预约ID | `tests/test_query.py::test_filter_by_dates[checkin]` | 通过 |
| API-022 | 唯一姓名加入住、退房或组合日期；退房日期 | 200，精确匹配对应预约ID | `tests/test_query.py::test_filter_by_dates[checkout]` | 通过 |
| API-023 | 唯一姓名加入住、退房或组合日期；入住和退房组合 | 200，精确匹配对应预约ID | `tests/test_query.py::test_filter_by_dates[checkin_and_checkout]` | 通过 |
| API-024 | 三条预约，每页2条，读取前三页 | 每页2、1、0条，总数3，无重复遗漏 | `tests/test_query.py::test_pagination_and_completeness` | 通过 |
| API-025 | 不匹配的唯一姓氏，分别普通或分页查询；普通列表 | 200，空列表或total为0的分页对象 | `tests/test_query.py::test_query_without_matches[plain_list]` | 通过 |
| API-026 | 不匹配的唯一姓氏，分别普通或分页查询；分页对象 | 200，空列表或total为0的分页对象 | `tests/test_query.py::test_query_without_matches[paginated]` | 通过 |
| API-027 | 非法页码或每页数量；page为0 | 400，场景对应的具体校验错误 | `tests/test_query.py::test_invalid_pagination_parameters[page_zero]` | 通过 |
| API-028 | 非法页码或每页数量；page为abc | 400，场景对应的具体校验错误 | `tests/test_query.py::test_invalid_pagination_parameters[page_wrong_type]` | 通过 |
| API-029 | 非法页码或每页数量；page_size为101 | 400，场景对应的具体校验错误 | `tests/test_query.py::test_invalid_pagination_parameters[page_size_too_large]` | 通过 |
| API-030 | 登录，GET带firstname参数的查询，退出 | 各步200，有token、编号列表和Logged out | `tests/test_requests_basics.py::test_login_query_and_logout` | 通过 |
| API-031 | 2秒有效期token，等3秒后PUT | 403，Token has expired，预约完整保留 | `tests/test_token_expiry.py::test_expired_token_cannot_update_booking` | 通过 |
| API-032 | 从合法模板制造单一创建输入异常；删除firstname | 400，精确匹配场景的错误原因 | `tests/test_validation.py::test_booking_input_validation[missing_firstname]` | 通过 |
| API-033 | 从合法模板制造单一创建输入异常；删除bookingdates.checkout | 400，精确匹配场景的错误原因 | `tests/test_validation.py::test_booking_input_validation[missing_checkout]` | 通过 |
| API-034 | 从合法模板制造单一创建输入异常；价格字符串200 | 400，精确匹配场景的错误原因 | `tests/test_validation.py::test_booking_input_validation[price_wrong_type]` | 通过 |
| API-035 | 从合法模板制造单一创建输入异常；订金字符串true | 400，精确匹配场景的错误原因 | `tests/test_validation.py::test_booking_input_validation[deposit_wrong_type]` | 通过 |
| API-036 | 从合法模板制造单一创建输入异常；价格为负1 | 400，精确匹配场景的错误原因 | `tests/test_validation.py::test_booking_input_validation[negative_price]` | 通过 |
| API-037 | 从合法模板制造单一创建输入异常；firstname只含空格 | 400，精确匹配场景的错误原因 | `tests/test_validation.py::test_booking_input_validation[blank_firstname]` | 通过 |
| API-038 | 从合法模板制造单一创建输入异常；退房日期为2026-02-30 | 400，精确匹配场景的错误原因 | `tests/test_validation.py::test_booking_input_validation[invalid_checkout_date]` | 通过 |
| API-039 | POST发送末尾逗号的错误JSON原文 | 400，Invalid JSON body | `tests/test_validation.py::test_invalid_json_body` | 通过 |
| API-040 | PATCH仅提交totalprice为350，再次GET | 200，价格350，其余完整字段与创建时一致 | `tests/test_patch.py::test_patch_only_price` | 通过 |
| API-041 | PATCH提交空JSON对象{}，再次GET | 400，Patch body must not be empty，完整数据未变 | `tests/test_patch.py::test_patch_empty_object_rejected` | 通过 |
| API-042 | PATCH提交unexpected_field，再次GET | 400，Unknown field: unexpected_field，完整数据未变 | `tests/test_patch.py::test_patch_unknown_field_rejected` | 通过 |
| API-043 | 注销后使用旧token DELETE，再次GET | 403，预约仍存在且完整数据未变，使用新token清理 | `tests/test_auth.py::test_logged_out_token_cannot_delete_booking` | 通过 |
