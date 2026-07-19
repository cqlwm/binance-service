"""binance_service.service 辅助函数的单元测试。

不依赖真实 Chrome/Playwright，只测纯逻辑：
- _kill_process_tree：杀真实 subprocess 进程树
- _playwright_driver_pid：对伪造对象返回 None（容错）

e2e 测试（test_e2e.py）覆盖真实 BinanceService 流程。
"""

from __future__ import annotations

import subprocess
import sys
import time

import psutil

from binance_service.service import _kill_process_tree
from binance_service.service import _playwright_driver_pid


def _is_truly_dead(pid: int) -> bool:
    """进程是否真的死了（pid_exists 对 zombie 仍返回 True，需用 status 判断）。"""
    if not psutil.pid_exists(pid):
        return True
    try:
        return psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return True


def _spawn_tree() -> tuple[int, int]:
    """启动一个父进程，父进程再启动一个子进程，返回 (parent_pid, child_pid)。

    用 Python -c 起一个会 fork 子进程的常驻脚本。
    """
    script = (
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
        f"open(r'{__file__}.childpid', 'w').write(str(child.pid))\n"
        "time.sleep(30)\n"
    )
    parent = subprocess.Popen([sys.executable, "-c", script])
    # 等父进程把子进程 pid 写到文件
    pid_file = f"{__file__}.childpid"
    for _ in range(50):
        try:
            with open(pid_file) as f:
                child_pid = int(f.read().strip())
                return parent.pid, child_pid
        except FileNotFoundError:
            time.sleep(0.1)
    raise RuntimeError("子进程 pid 文件未生成")


def test_kill_process_tree_kills_parent_and_children() -> None:
    """_kill_process_tree 应杀掉父进程及其全部子孙进程。"""
    parent_pid, child_pid = _spawn_tree()
    # 确认两个进程都还活着
    assert psutil.pid_exists(parent_pid), "父进程应存活"
    assert psutil.pid_exists(child_pid), "子进程应存活"

    _kill_process_tree(parent_pid)

    # 给 OS 一点时间回收（kill 后进程可能进入 zombie 态待父进程回收，
    # 视为已死）
    for _ in range(50):
        if _is_truly_dead(parent_pid) and _is_truly_dead(child_pid):
            break
        time.sleep(0.1)

    assert _is_truly_dead(parent_pid), f"父进程 {parent_pid} 应被杀"
    assert _is_truly_dead(child_pid), f"子进程 {child_pid} 应被杀"


def test_kill_process_tree_no_such_process_is_noop() -> None:
    """杀一个不存在的 PID 应静默返回，不抛异常。"""
    # 找一个几乎不可能在用的 pid
    nonexistent_pid = 2_000_000
    _kill_process_tree(nonexistent_pid)  # 不抛异常即可


def test_playwright_driver_pid_returns_none_for_non_browser() -> None:
    """对没有 Playwright 内部结构的对象，_playwright_driver_pid 应返回 None。"""
    # 传一个普通对象，反射访问 _impl_obj 会 AttributeError，被 try/except 接住
    assert _playwright_driver_pid(object()) is None  # type: ignore[arg-type]


def test_kill_process_tree_twice_is_safe() -> None:
    """连续杀同一个进程树，第二次应静默返回（幂等）。"""
    parent_pid, _child_pid = _spawn_tree()
    _kill_process_tree(parent_pid)
    # 第二次杀，进程已不存在，不应抛异常
    _kill_process_tree(parent_pid)
