import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import html
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import os
import socket
import subprocess
import sys
import threading
import traceback
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SHANGHAI = timezone(timedelta(hours=8))


def now():
    return datetime.now(SHANGHAI)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def port_is_released(port):
    with socket.socket() as probe:
        probe.settimeout(1)
        return probe.connect_ex(("127.0.0.1", port)) != 0


def read_cases(path):
    if not path.exists():
        return []
    cases = []
    for case in ET.parse(path).getroot().iter("testcase"):
        outcome = "passed"
        details = ""
        for tag in ("failure", "error", "skipped"):
            node = case.find(tag)
            if node is not None:
                outcome = {"failure": "failed", "error": "error", "skipped": "skipped"}[tag]
                details = (node.get("message", "") + "\n" + (node.text or "")).strip()
                break
        cases.append({"class": case.get("classname", ""), "name": case.get("name", ""),
                      "status": outcome, "seconds": float(case.get("time", "0")), "details": details})
    return cases


def write_report(directory, record, cases):
    (directory / "run-record.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = "".join(
        f"<tr><td>{html.escape(c['class'])}</td><td>{html.escape(c['name'])}</td>"
        f"<td>{c['status']}</td><td>{c['seconds']:.3f}</td>"
        f"<td><pre>{html.escape(c['details'])}</pre></td></tr>" for c in cases)
    counts = record["test_results"]
    checks = "".join(f"<li>{html.escape(k)}: {html.escape(str(v))}</li>"
                     for k, v in record["cleanup_checks"].items())
    page = f"""<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>本地预约 API 测试报告</title>
<style>body{{font:16px/1.65 system-ui,sans-serif;margin:32px auto;padding:0 24px;max-width:1200px;color:#202124}}
table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{padding:10px;border:1px solid #d9d9d9;text-align:left;vertical-align:top}}
th{{background:#edf1f4}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;margin:0}}td{{overflow-wrap:anywhere}}a{{color:#1655a2}}</style>
<h1>本地预约 API 测试报告</h1>
<p>执行时间 {html.escape(record['started_at'])} 至 {html.escape(record['finished_at'])}</p>
<p>结果 {record['status']} · 总数 {counts['tests']} · 通过 {counts['passed']} · 失败 {counts['failed']} · 错误 {counts['errors']} · 跳过 {counts['skipped']}</p>
<p>本次使用本项目的独立临时服务 {html.escape(record['service_url'])}，运行结束后已关闭。</p>
<p><a href="test-output.txt">终端输出</a> · <a href="pytest-results.xml">JUnit XML</a> · <a href="run-record.json">运行记录</a></p>
<h2>用例结果</h2><table><thead><tr><th>测试模块</th><th>场景</th><th>结果</th><th>耗时 秒</th><th>异常详情</th></tr></thead><tbody>{rows}</tbody></table>
<h2>清理检查</h2><ul>{checks}</ul></html>"""
    (directory / "report.html").write_text(page, encoding="utf-8")
    summary = f"""# 本地预约 API 测试运行记录

本次运行使用本项目代码和独立临时服务。执行结果为 **{record['status']}**。

| 项目 | 结果 |
|---|---|
| 开始时间 | {record['started_at']} |
| 结束时间 | {record['finished_at']} |
| 用例总数 | {counts['tests']} |
| 通过 | {counts['passed']} |
| 失败 | {counts['failed']} |
| 错误 | {counts['errors']} |
| 跳过 | {counts['skipped']} |
| pytest 退出码 | {record['pytest_exit_code']} |
| 服务地址 | {record['service_url']} |

## 执行命令

```powershell
{record['entry_command']}
```

测试子进程实际命令和环境版本见 [run-record.json](run-record.json)。

## 测试证据

- [完整终端输出](test-output.txt)
- [逐条测试结果](pytest-results.xml)
- [浏览器报告](report.html)
- [机器可读执行记录](run-record.json)
- [服务请求日志](server-output.txt)

## 清理检查

""" + "\n".join(f"- `{k}`：`{v}`" for k, v in record["cleanup_checks"].items()) + "\n\n"
    summary += "本次预置了三条已有预约。清理检查由运行脚本额外执行，JUnit 本身只记录测试结果。\n"
    if record.get("execution_error"):
        summary += "\n## 执行异常\n\n```text\n" + record["execution_error"] + "\n```\n"
    (directory / "summary.md").write_text(summary, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="*", help="Optional pytest file or node IDs")
    args = parser.parse_args()
    started = now()
    directory = ROOT / "reports" / started.strftime("%Y-%m-%d") / started.strftime("%H%M%S-%f")
    directory.mkdir(parents=True)
    template = ROOT / "tests/data/booking.json"
    template_before = digest(template)
    spec = importlib.util.spec_from_file_location("booking_server", ROOT / "local-api/server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    service_log = (directory / "server-output.txt").open("w", encoding="utf-8")
    original_handler = module.BookingAPI

    class LoggedHandler(original_handler):
        def log_message(self, fmt, *values):
            service_log.write((fmt % values) + "\n")
            service_log.flush()

    module.BookingAPI = LoggedHandler
    server = module.BookingServer(("127.0.0.1", 0), token_ttl=3600)
    seed = json.loads(template.read_text(encoding="utf-8"))
    for index in range(1, 4):
        item = deepcopy(seed)
        item.update(firstname="QueryLearner", lastname=f"Existing_{index}", totalprice=index * 100)
        server.bookings[index] = item
    server.next_id = 4
    seeded_before = deepcopy(server.bookings)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    service_url = f"http://127.0.0.1:{server.server_port}"
    command = [sys.executable, "-B", "-m", "pytest", *(args.targets or ["tests"]),
               "-v", "-ra", "-p", "no:cacheprovider", "--tb=short",
               f"--junitxml={directory / 'pytest-results.xml'}"]
    environment = os.environ.copy()
    environment.update(BOOKING_BASE_URL=service_url, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    exit_code = 1
    execution_error = None
    output = ""
    checks = {}
    print(f"Local isolated service: {service_url}", flush=True)
    try:
        result = subprocess.run(command, cwd=ROOT, env=environment, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, encoding="utf-8", errors="replace", timeout=180)
        exit_code, output = result.returncode, result.stdout
        checks = {
            "existing_bookings_unchanged": all(server.bookings.get(k) == v for k, v in seeded_before.items()),
            "no_test_bookings_remaining": set(server.bookings) == set(seeded_before),
            "no_test_tokens_remaining": not server.tokens,
            "template_unchanged": digest(template) == template_before,
        }
    except Exception:
        execution_error = traceback.format_exc()
        output += execution_error
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
        checks["service_thread_stopped"] = not worker.is_alive()
        checks["normal_service_port_released"] = port_is_released(server.server_port)
        service_log.close()
    print(output, end="", flush=True)
    (directory / "test-output.txt").write_text(output, encoding="utf-8")
    cases = read_cases(directory / "pytest-results.xml")
    counts = {"tests": len(cases), "passed": sum(c["status"] == "passed" for c in cases),
              "failed": sum(c["status"] == "failed" for c in cases),
              "errors": sum(c["status"] == "error" for c in cases),
              "skipped": sum(c["status"] == "skipped" for c in cases)}
    success = exit_code == 0 and bool(cases) and all(checks.values()) and not execution_error
    record = {
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": now().isoformat(timespec="seconds"), "status": "passed" if success else "failed",
        "workspace": str(ROOT), "entry_command": ".\\.venv\\Scripts\\python.exe scripts/run_tests.py" +
            (" " + " ".join(args.targets) if args.targets else ""),
        "pytest_command": command, "pytest_exit_code": exit_code, "service_url": service_url,
        "test_results": counts, "cleanup_checks": checks, "seeded_booking_count": len(seeded_before),
        "remaining_booking_count": len(server.bookings), "remaining_token_count": len(server.tokens),
        "template_sha256_before": template_before, "template_sha256_after": digest(template),
        "environment": {"python": sys.version.split()[0], "python_executable": sys.executable,
                        "pytest": importlib.metadata.version("pytest"), "requests": importlib.metadata.version("requests")},
        "execution_error": execution_error,
    }
    write_report(directory, record, cases)
    (ROOT / "reports/latest.json").write_text(json.dumps({
        "directory": directory.relative_to(ROOT).as_posix(), "status": record["status"],
        "test_results": counts, "started_at": record["started_at"]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved report: {directory / 'report.html'}", flush=True)
    print(f"Cleanup checks: {checks}", flush=True)
    return 0 if success else (exit_code or 1)


if __name__ == "__main__":
    raise SystemExit(main())
