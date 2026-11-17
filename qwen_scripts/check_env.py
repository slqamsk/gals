#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Объединённый диагностический скрипт (v9).

Изменения относительно v8:
  • Секция 6 расширена: помимо файлов текущей папки (верхний уровень),
    рекурсивно сканируются docs/, migrations/, src/, z/ — если есть.
  • Добавлена константа EXCLUDE_DIRS — папки, которые не обходятся
    при рекурсивном сканировании (venv, __pycache__, .git и т.п.).
  • Добавлена подсекция «Наличие папок для рекурсивного сканирования» —
    показывает, какие из четырёх папок реально есть в проекте.
"""

import os
import sys
import platform
import subprocess
import shutil
import tempfile
import datetime
import hashlib
import socket
import getpass
import re
from pathlib import Path

IS_WINDOWS = platform.system() == "Windows"
HAS_BASH = shutil.which("bash") is not None

# Папки, которые НЕ обходятся при рекурсивном сканировании.
# Это типичный «мусор»: venv, кэши, .git, node_modules и т.п.
EXCLUDE_DIRS = {
    ".venv", "venv", "env", ".env",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".idea", ".vscode", ".git", ".hg", ".svn",
    "node_modules", "build", "dist", ".eggs",
}

# Папки, которые сканируются РЕКУРСИВНО (в дополнение к файлам
# верхнего уровня текущей папки).
RECURSIVE_DIRS = ("docs", "migrations", "src", "z")


# ----------------------------------------------------------------------
# Утилиты вывода
# ----------------------------------------------------------------------
def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def subsection(title):
    print("\n--- " + title + " ---")


def run_self(args, timeout=15):
    """Выполнить sys.executable -m args. НЕ shell. Кроссплатформенно."""
    try:
        r = subprocess.run(
            [sys.executable, *args],
            capture_output=True, text=True, timeout=timeout,
        )
        if r.stdout:
            print(r.stdout.rstrip())
        if r.returncode != 0 and r.stderr:
            print(r.stderr.rstrip())
        return r
    except Exception as e:
        print(f"(python:error) {e}")
        return None


def safe(fn, default="недоступно"):
    try:
        return fn()
    except Exception as e:
        return f"{default}: {e}"


def read_text(path, max_bytes=None):
    try:
        with open(path, "rb") as f:
            data = f.read() if max_bytes is None else f.read(max_bytes)
        return data.decode("utf-8", errors="replace")
    except Exception as e:
        return f"(не удалось прочитать {path}: {e})"


def run_native(win_cmd, lin_cmd, timeout=15):
    """Windows → PowerShell, Linux → bash. Вывод печатается как есть."""
    if IS_WINDOWS:
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", win_cmd],
                capture_output=True, text=True, timeout=timeout,
            )
            if r.stdout:
                print(r.stdout.rstrip())
            if r.returncode != 0 and r.stderr:
                print(r.stderr.rstrip())
            return r
        except Exception as e:
            print(f"(powershell:error) {e}")
            return None
    else:
        if not HAS_BASH:
            print("(bash недоступен)")
            return None
        try:
            r = subprocess.run(
                ["bash", "-c", lin_cmd],
                capture_output=True, text=True, timeout=timeout,
            )
            if r.stdout:
                print(r.stdout.rstrip())
            if r.returncode != 0 and r.stderr:
                print(r.stderr.rstrip())
            return r
        except Exception as e:
            print(f"(bash:error) {e}")
            return None


# ======================================================================
# 0. ОКРУЖЕНИЕ
# ======================================================================
section("0. ОКРУЖЕНИЕ")

subsection("platform.system()")
print(platform.system())

subsection("WSL-детекция")
is_wsl = ("WSL_DISTRO_NAME" in os.environ
          or "microsoft" in platform.release().lower())
if is_wsl:
    print("[!] Скрипт запущен из WSL (Windows Subsystem for Linux).")
    print(f"    WSL_DISTRO_NAME={os.environ.get('WSL_DISTRO_NAME', '—')}")
    print("    Если нужны Windows-нативные проверки — запускайте из cmd или PowerShell.")
else:
    print("[ok] скрипт запущен нативно (не из WSL)")


# ======================================================================
# 1. ЖЕЛЕЗО
# ======================================================================
section("1. ЖЕЛЕЗО")

subsection("os.cpu_count()")
print(safe(os.cpu_count))

subsection("platform.processor()")
print(repr(safe(platform.processor)))

subsection("Модель CPU (на Linux — из /proc/cpuinfo)")
if not IS_WINDOWS and Path("/proc/cpuinfo").exists():
    found = False
    for line in read_text("/proc/cpuinfo").splitlines():
        if line.startswith("model name"):
            print(line.split(":", 1)[1].strip())
            found = True
            break
    if not found:
        print("(model name не найден в /proc/cpuinfo)")
else:
    print("(не применимо на Windows — см. platform.processor())")

subsection("platform.machine()")
print(safe(platform.machine))

subsection("platform.architecture()")
print(safe(platform.architecture))

subsection("psutil.virtual_memory()")
try:
    import psutil
    print(psutil.virtual_memory())
except ImportError:
    print("psutil не установлен")

subsection("shutil.disk_usage(os.getcwd())")
print(safe(lambda: shutil.disk_usage(os.getcwd())))


# ======================================================================
# 2. ОПЕРАЦИОННАЯ СИСТЕМА
# ======================================================================
section("2. ОПЕРАЦИОННАЯ СИСТЕМА")

subsection("platform.uname()  — содержит system, release, version, machine")
print(safe(platform.uname))

subsection("platform.platform()  — сводная строка")
print(safe(platform.platform))

subsection("platform.freedesktop_os_release()")
print(safe(platform.freedesktop_os_release))

subsection("platform.win32_ver()")
print(safe(platform.win32_ver))

subsection("platform.win32_edition()")
print(safe(platform.win32_edition))

subsection("platform.win32_is_iot()")
print(safe(platform.win32_is_iot))

subsection("platform.libc_ver()")
print(safe(platform.libc_ver))


# ======================================================================
# 3. ПЛАТФОРМЕННЫЕ КОМАНДЫ
# (Pure Python даёт неполную картину — нужен shell: PowerShell/bash)
# ======================================================================
section("3. ПЛАТФОРМЕННЫЕ КОМАНДЫ (Pure Python неполон)")

subsection("Физические ядра CPU (os.cpu_count даёт только logical)")
run_native(
    win_cmd=(
        "Write-Host -NoNewline 'NumberOfCores: '; "
        "(Get-CimInstance Win32_Processor).NumberOfCores; "
        "Write-Host -NoNewline 'NumberOfLogicalProcessors: '; "
        "(Get-CimInstance Win32_Processor).NumberOfLogicalProcessors"
    ),
    lin_cmd=(
        "lscpu 2>/dev/null | grep -E '^(CPU\\(s\\)|Thread\\(s\\) per core|"
        "Core\\(s\\) per socket|Socket\\(s\\))' "
        "|| grep -E 'cpu cores|physical id' /proc/cpuinfo | sort -u"
    ),
)

subsection("Полная модель CPU (platform.processor пуст на Linux)")
run_native(
    win_cmd="(Get-CimInstance Win32_Processor).Name",
    lin_cmd="lscpu 2>/dev/null | grep 'Model name' || grep 'model name' /proc/cpuinfo | head -1",
)

subsection("Память — разбивка (KB)")
run_native(
    win_cmd=(
        "Get-CimInstance Win32_OperatingSystem | "
        "Select-Object TotalVisibleMemorySize, FreePhysicalMemory, "
        "TotalVirtualMemorySize, FreeVirtualMemory | Format-List"
    ),
    lin_cmd="head -5 /proc/meminfo",
)

subsection("Все смонтированные ФС (shutil.disk_usage видит только текущую)")
run_native(
    win_cmd="Get-PSDrive -PSProvider FileSystem | Select-Object Name, Used, Free",
    lin_cmd="df -hT 2>/dev/null || df -h",
)

subsection("Сетевые интерфейсы и IP-адреса")
run_native(
    win_cmd=(
        "Get-NetIPAddress -AddressFamily IPv4 | "
        "Select-Object InterfaceAlias, IPAddress | Format-Table -AutoSize"
    ),
    lin_cmd="ip -br addr 2>/dev/null || ifconfig -a 2>/dev/null",
)

subsection("Uptime / время загрузки (ISO 8601)")
run_native(
    win_cmd='(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToString("o")',
    lin_cmd="uptime",
)

subsection("Полная версия ядра / сборки ОС")
run_native(
    win_cmd=(
        "Get-CimInstance Win32_OperatingSystem | "
        "Select-Object Caption, Version, BuildNumber, OSArchitecture | Format-List"
    ),
    lin_cmd="uname -a",
)


# ======================================================================
# 4. ПОЛЬЗОВАТЕЛЬ
# ======================================================================
section("4. ПОЛЬЗОВАТЕЛЬ")

subsection("getpass.getuser()  — может отличаться от os.environ, если USER-переменных нет")
print(safe(getpass.getuser))

subsection("os.environ USERNAME / USER")
print(os.environ.get("USERNAME") or os.environ.get("USER") or "—")

subsection("os.getuid() / os.getgid()")
print(safe(lambda: (
    f"{os.getuid()}/{os.getgid()}" if hasattr(os, "getuid")
    else "недоступно на этой платформе")))


# ======================================================================
# 5. PYTHON И БИБЛИОТЕКИ
# ======================================================================
section("5. PYTHON И БИБЛИОТЕКИ")

subsection("sys.version  — версия + build + compiler + арх")
print(sys.version)

subsection("sys.version_info  — то же в структурированном виде")
print(sys.version_info)

subsection("sys.implementation.name")
print(sys.implementation.name)

subsection("platform.python_version()  — краткая версия")
print(safe(platform.python_version))

subsection("sys.executable  — путь к текущему интерпретатору")
print(sys.executable)

subsection("shutil.which('python') / shutil.which('python3')  — что найдётся в PATH")
print(f"python: {shutil.which('python')}")
print(f"python3: {shutil.which('python3')}")

subsection("python -m pip --version")
run_self(["-m", "pip", "--version"])

subsection("python -m pytest --version")
run_self(["-m", "pytest", "--version"])

subsection("python -m pip check  — целостность зависимостей")
run_self(["-m", "pip", "check"], timeout=60)

subsection("sys.path")
for p in sys.path:
    print(p)

subsection("ssl.OPENSSL_VERSION")
try:
    import ssl
    print(ssl.OPENSSL_VERSION)
except Exception as e:
    print(f"недоступно: {e}")


# ======================================================================
# 6. ФАЙЛЫ И ПАПКИ
# ======================================================================
section("6. ФАЙЛЫ И ПАПКИ")

subsection("os.getcwd()")
print(os.getcwd())

subsection("os.listdir('.')  — только верхний уровень текущей папки")
for name in sorted(os.listdir("..")):
    print(name)

subsection("Наличие папок для рекурсивного сканирования")
for d in RECURSIVE_DIRS:
    mark = "есть" if Path(d).is_dir() else "НЕТ"
    print(f"{d}: {mark}")

subsection("SHA-256 + размер: файлы текущей папки + рекурсивно docs/, migrations/, src/, z/")
files_to_check = []
seen = set()

# 1) файлы верхнего уровня текущей папки
for name in sorted(os.listdir("..")):
    p = Path(name)
    if p.is_file():
        rel = str(p)
        if rel not in seen:
            seen.add(rel)
            files_to_check.append((rel, p))

# 2) рекурсивный обход 4 папок (если есть)
for root in RECURSIVE_DIRS:
    root_path = Path(root)
    if not root_path.is_dir():
        continue
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # исключаем «мусорные» подпапки
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDE_DIRS)
        for fname in sorted(filenames):
            full = Path(dirpath) / fname
            rel = str(full)
            if rel not in seen:
                seen.add(rel)
                files_to_check.append((rel, full))

# 3) вывод, сортировка по относительному пути
for rel, full in sorted(files_to_check, key=lambda x: x[0]):
    try:
        data = full.read_bytes()
        print(f"{len(data):>12} {hashlib.sha256(data).hexdigest()}  {rel}")
    except Exception as e:
        print(f"{'':>12} {'':<64}  {rel}: {e}")


# ======================================================================
# 7. СЕТЬ
# ======================================================================
section("7. СЕТЬ")

subsection("socket.create_connection(('pypi.org', 443), timeout=3)")
try:
    with socket.create_connection(("pypi.org", 443), timeout=3):
        print("pypi:443 ok")
except Exception as e:
    print(f"pypi:443 fail: {e}")


# ======================================================================
# 8. ОКРУЖЕНИЕ И ВРЕМЯ
# ======================================================================
section("8. ОКРУЖЕНИЕ И ВРЕМЯ")

subsection("os.environ")
for k in sorted(os.environ):
    print(f"{k}={os.environ[k]}")

subsection("datetime.now()")
print(datetime.datetime.now().isoformat())

subsection("datetime.now(UTC)")
print(datetime.datetime.now(datetime.timezone.utc).isoformat())


# ======================================================================
# 9. ТЕСТИРОВАНИЕ (pytest)
# ======================================================================
section("9. ТЕСТИРОВАНИЕ (pytest)")

subsection("python -m pytest -q test_probe.py")
try:
    with tempfile.TemporaryDirectory() as td:
        test_file = Path(td) / "test_probe.py"
        test_file.write_text("def test_ok():\n    assert 1 + 1 == 2\n",
                             encoding="utf-8")
        env = os.environ.copy()
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--no-header",
             "-p", "no:cacheprovider", "--color=no", str(test_file)],
            capture_output=True, text=True, env=env, timeout=60,
        )
        out = (r.stdout or "").rstrip()
        err = (r.stderr or "").rstrip()
        if out:
            for line in out.splitlines()[-3:]:
                print(line)
        if r.returncode != 0 and err:
            for line in err.splitlines()[-3:]:
                print(line)
except Exception as e:
    print(f"error: {e}")


# ======================================================================
# 10. REQUIREMENTS.TXT vs УСТАНОВЛЕННОЕ
# ======================================================================
section("10. REQUIREMENTS.TXT vs УСТАНОВЛЕННОЕ")

subsection("requirements.txt vs importlib.metadata.distributions()")
req = Path("../requirements.txt")
if req.exists():
    required = [
        ln.strip()
        for ln in req.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
    installed = {}
    try:
        from importlib.metadata import distributions
        installed = {
            (d.metadata["Name"] or "").lower(): d.version
            for d in distributions()
        }
    except Exception as e:
        print(f"importlib.metadata недоступен: {e}")

    print(f"requirements.txt строк: {len(required)}")
    for line in required:
        name = re.split(r"[<>=!~; ]", line, 1)[0].lower()
        have = installed.get(name)
        mark = "OK  " if have else "MISS"
        extra = f"  (установлено {have})" if have else ""
        print(f"{mark} {line}{extra}")
else:
    print("requirements.txt не найден в текущей папке")


# ======================================================================
# 11. УСТАНОВЛЕННЫЕ ПАКЕТЫ
# ======================================================================
section("11. УСТАНОВЛЕННЫЕ ПАКЕТЫ")

subsection("python -m pip list --format=freeze")
run_self(["-m", "pip", "list", "--format=freeze"], timeout=60)


# ======================================================================
# 12. Завершение работы скрипта
# ======================================================================
section("Работа скрипта завершена")