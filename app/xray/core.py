import atexit
import re
import subprocess
import threading
import time
from collections import deque
from contextlib import contextmanager

from app import logger
from app.xray.config import XRayConfig
from config import DEBUG

# Minimum time between restarts to prevent infinite loops (seconds)
MIN_RESTART_INTERVAL = 30


class XRayCore:
    def __init__(self,
                 executable_path: str = "/usr/bin/xray",
                 assets_path: str = "/usr/share/xray"):
        self.executable_path = executable_path
        self.assets_path = assets_path

        self.version = self.get_version()
        self.process = None
        self.restarting = False
        self._last_restart_time = 0
        self._restart_count = 0

        self._logs_buffer = deque(maxlen=100)
        self._temp_log_buffers = {}
        self._on_start_funcs = []
        self._on_stop_funcs = []
        self._env = {
            "XRAY_LOCATION_ASSET": assets_path
        }

        atexit.register(lambda: self.stop() if self.started else None)

    def get_version(self):
        cmd = [self.executable_path, "version"]
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode('utf-8')
        m = re.match(r'^Xray (\d+\.\d+\.\d+)', output)
        if m:
            return m.groups()[0]

    def get_x25519(self, private_key: str = None):
        cmd = [self.executable_path, "x25519"]
        if private_key:
            cmd.extend(['-i', private_key])
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode('utf-8')
        private_match = re.search(r'(?im)^\s*Private\s*[Kk]ey:\s*(\S+)', output)
        public_match = re.search(r'(?im)^\s*Public\s*[Kk]ey:\s*(\S+)', output)

        private = private_match.group(1).strip() if private_match else (private_key.strip() if private_key else "")
        public = public_match.group(1).strip() if public_match else ""

        if not public:
            key_lines = re.findall(r'(?im)^\s*(?:Private|Public)\s*[Kk]ey:\s*(\S+)', output)
            if len(key_lines) >= 2:
                if private_key:
                    public = key_lines[-1].strip()
                else:
                    private = key_lines[0].strip()
                    public = key_lines[1].strip()

        if public:
            return {
                "private_key": private,
                "public_key": public
            }

    def __capture_process_logs(self):
        def capture_and_debug_log():
            while self.process:
                output = self.process.stdout.readline()
                if output:
                    output = output.strip()
                    self._logs_buffer.append(output)
                    for buf in list(self._temp_log_buffers.values()):
                        buf.append(output)
                    logger.debug(output)

                elif not self.process or self.process.poll() is not None:
                    break

        def capture_only():
            while self.process:
                output = self.process.stdout.readline()
                if output:
                    output = output.strip()
                    self._logs_buffer.append(output)
                    for buf in list(self._temp_log_buffers.values()):
                        buf.append(output)

                elif not self.process or self.process.poll() is not None:
                    break

        if DEBUG:
            threading.Thread(target=capture_and_debug_log).start()
        else:
            threading.Thread(target=capture_only).start()

    @contextmanager
    def get_logs(self):
        buf = deque(self._logs_buffer, maxlen=100)
        buf_id = id(buf)
        try:
            self._temp_log_buffers[buf_id] = buf
            yield buf
        finally:
            del self._temp_log_buffers[buf_id]
            del buf

    @property
    def started(self):
        if not self.process:
            return False

        if self.process.poll() is None:
            return True

        return False

    def start(self, config: XRayConfig):
        if self.started is True:
            raise RuntimeError("Xray is started already")

        if config.get('log', {}).get('logLevel') in ('none', 'error'):
            config['log']['logLevel'] = 'warning'

        cmd = [
            self.executable_path,
            "run",
            '-config',
            'stdin:'
        ]
        self.process = subprocess.Popen(
            cmd,
            env=self._env,
            stdin=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdout=subprocess.PIPE,
            universal_newlines=True
        )
        config_json = config.to_json()
        self.process.stdin.write(config_json)
        self.process.stdin.flush()
        self.process.stdin.close()
        logger.warning(f"Xray core {self.version} started")

        # Check if Xray crashed immediately (wait 1s)
        time.sleep(1)
        if self.process.poll() is not None:
            exit_code = self.process.poll()
            remaining = self.process.stdout.read()
            logger.error(f"Xray core CRASHED immediately with exit code {exit_code}")
            if remaining:
                for line in remaining.strip().split('\n')[-30:]:
                    logger.error(f"  [xray] {line}")
            else:
                logger.error("  [xray] No output captured")
            self.process = None
            return

        self.__capture_process_logs()

        # execute on start functions
        for func in self._on_start_funcs:
            threading.Thread(target=func).start()

    def stop(self):
        if not self.started:
            return

        self.process.terminate()
        self.process = None
        logger.warning("Xray core stopped")

        # execute on stop functions
        for func in self._on_stop_funcs:
            threading.Thread(target=func).start()

    def restart(self, config: XRayConfig):
        if self.restarting is True:
            return

        # Prevent rapid restart loops
        current_time = time.time()
        time_since_last_restart = current_time - self._last_restart_time
        
        if time_since_last_restart < MIN_RESTART_INTERVAL:
            self._restart_count += 1
            if self._restart_count > 3:
                logger.error(
                    f"Xray core restart loop detected ({self._restart_count} restarts in {MIN_RESTART_INTERVAL}s). "
                    f"Waiting {MIN_RESTART_INTERVAL - time_since_last_restart:.0f}s before next restart. "
                    "Check your xray_config.json for errors."
                )
                return
        else:
            self._restart_count = 0

        try:
            self.restarting = True
            self._last_restart_time = current_time
            logger.warning("Restarting Xray core...")
            self.stop()
            self.start(config)
        finally:
            self.restarting = False

    def on_start(self, func: callable):
        self._on_start_funcs.append(func)
        return func

    def on_stop(self, func: callable):
        self._on_stop_funcs.append(func)
        return func
