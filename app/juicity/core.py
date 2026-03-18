import atexit
import os
import subprocess
import threading
from collections import deque

from app import logger


class JuicityCore:
    def __init__(self, executable_path: str = "/usr/local/bin/juicity-server"):
        self.executable_path = executable_path
        self.process = None
        self._logs_buffer = deque(maxlen=100)
        self._config_path = None

        atexit.register(lambda: self.stop() if self.started else None)

    @property
    def started(self):
        if not self.process:
            return False
        return self.process.poll() is None

    def get_version(self):
        try:
            output = subprocess.check_output(
                [self.executable_path, "version"],
                stderr=subprocess.STDOUT,
            ).decode("utf-8")
            for line in output.strip().split("\n"):
                if "juicity" in line.lower() or line.startswith("v"):
                    return line.strip()
            return output.strip().split("\n")[0]
        except (FileNotFoundError, subprocess.CalledProcessError):
            return None

    def start(self, config_path: str):
        if self.started:
            raise RuntimeError("Juicity is already running")

        if not os.path.isfile(config_path):
            logger.error(f"Juicity config not found: {config_path}")
            return

        self._config_path = config_path
        cmd = [self.executable_path, "run", "-c", config_path]

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )

        logger.warning(f"Juicity core started (config: {config_path})")
        self._capture_logs()

    def stop(self):
        if not self.started:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
        self.process = None
        logger.warning("Juicity core stopped")

    def restart(self):
        self.stop()
        if self._config_path:
            self.start(self._config_path)

    def _capture_logs(self):
        def _read():
            while self.process:
                line = self.process.stdout.readline()
                if line:
                    line = line.strip()
                    self._logs_buffer.append(line)
                    logger.debug(f"[juicity] {line}")
                elif not self.process or self.process.poll() is not None:
                    break

        threading.Thread(target=_read, daemon=True).start()
