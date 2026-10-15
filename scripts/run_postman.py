from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading

ROOT = Path(__file__).resolve().parents[1]


def main():
    node = shutil.which("node")
    if not node:
        raise SystemExit("Node.js not found. Install Node.js 22 or newer first.")
    subprocess.run([node, str(ROOT / "scripts/export_postman.cjs")], cwd=ROOT, check=True)
    spec = importlib.util.spec_from_file_location("postman_test_server", ROOT / "local-api/server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.BookingAPI.log_message = lambda *args: None
    template = json.loads((ROOT / "tests/data/booking.json").read_text(encoding="utf-8"))
    directory = ROOT / "reports/postman" / datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d/%H%M%S-%f")
    directory.mkdir(parents=True)
    records = []
    for mode in ("normal", "expiry"):
        report = directory / mode
        report.mkdir()
        server = module.BookingServer(("127.0.0.1", 0), token_ttl=2 if mode == "expiry" else 3600)
        for booking_id in range(1, 4):
            server.bookings[booking_id] = {**deepcopy(template), "lastname": f"Existing_{booking_id}"}
        server.next_id = 4
        original = deepcopy(server.bookings)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            result = subprocess.run([node, str(ROOT / "scripts/run_newman.cjs"), mode,
                                     f"http://127.0.0.1:{server.server_port}", str(report)],
                                    cwd=ROOT, env={**os.environ, "NO_COLOR": "1"},
                                    capture_output=True, encoding="utf-8", errors="replace", timeout=180)
            (report / "test-output.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
            result_path = report / "newman-results.json"
            if not result_path.is_file():
                raise RuntimeError(f"Newman exited with code {result.returncode} without producing a report. See {report / 'test-output.txt'}")
            raw = json.loads(result_path.read_text(encoding="utf-8"))
            checks = {"existing_bookings_unchanged": server.bookings == original,
                      "no_test_tokens_remaining": not server.tokens}
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)
        checks["service_thread_stopped"] = not worker.is_alive()
        record = {"mode": mode, "iterations": 2, "exit_code": result.returncode,
                  "stats": raw["run"]["stats"], "failures": len(raw["run"]["failures"]), "cleanup_checks": checks}
        (report / "run-record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        records.append(record)
        print(f"{mode}: {record['stats']['requests']['total']} requests, {record['stats']['assertions']['total']} assertions, {record['failures']} failures", flush=True)
    success = all(r["exit_code"] == 0 and r["failures"] == 0 and all(r["cleanup_checks"].values()) for r in records)
    summary = "# Postman完整集合验证\n\n执行工具：Newman，验证当前YAML导出的JSON；各组连续两轮，普通与过期场景使用独立临时服务。\n\n"
    summary += "| 组别 | 请求数 | 断言数 | 失败 | 清理检查 |\n|---|---:|---:|---:|---|\n"
    for r in records:
        summary += f"| [{r['mode']}](./{r['mode']}/run-record.json) | {r['stats']['requests']['total']} | {r['stats']['assertions']['total']} | {r['failures']} | {all(r['cleanup_checks'].values())} |\n"
    summary += "\n结果：" + ("通过" if success else "失败，请查看组内输出和JSON报告") + "。此记录来自命令行验证。\n"
    (directory / "summary.md").write_text(summary, encoding="utf-8")
    (ROOT / "reports/postman/latest.json").write_text(json.dumps({"directory": directory.relative_to(ROOT).as_posix(), "status": "passed" if success else "failed", "runs": records}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved report: {directory / 'summary.md'}")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
