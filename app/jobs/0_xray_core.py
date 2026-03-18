import os
import time
import traceback

from app import app, logger, scheduler, xray
from app.db import GetDB, crud
from app.models.node import NodeStatus
from config import JOB_CORE_HEALTH_CHECK_INTERVAL
from xray_api import exc as xray_exc

# Track health check state
_consecutive_failures = 0
_MAX_CONSECUTIVE_FAILURES = 5

# TUIC/Juicity cores (set at startup)
_tuic_core = None
_juicity_core = None


def core_health_check():
    global _consecutive_failures
    config = None

    # main core
    if not xray.core.started:
        _consecutive_failures += 1
        
        if _consecutive_failures > _MAX_CONSECUTIVE_FAILURES:
            if _consecutive_failures == _MAX_CONSECUTIVE_FAILURES + 1:
                logger.error(
                    f"Xray core failed to start {_consecutive_failures} times consecutively. "
                    "Stopping restart attempts. Check your xray_config.json for errors."
                )
            # Don't attempt restart after too many failures
            return
        
        # Log last Xray output to help diagnose crash
        if xray.core._logs_buffer:
            last_logs = list(xray.core._logs_buffer)[-10:]
            logger.error(f"Xray core crashed. Last {len(last_logs)} log lines:")
            for line in last_logs:
                logger.error(f"  [xray] {line}")
        
        logger.warning(f"Xray core not running (attempt {_consecutive_failures}/{_MAX_CONSECUTIVE_FAILURES})")
        if not config:
            config = xray.config.include_db_users()
        xray.core.restart(config)
    else:
        # Reset counter on successful health check
        _consecutive_failures = 0

    # nodes' core
    for node_id, node in list(xray.nodes.items()):
        if node.connected:
            try:
                assert node.started
                node.api.get_sys_stats(timeout=2)
            except (ConnectionError, xray_exc.XrayError, AssertionError):
                if not config:
                    config = xray.config.include_db_users()
                xray.operations.restart_node(node_id, config)

        if not node.connected:
            if not config:
                config = xray.config.include_db_users()
            xray.operations.connect_node(node_id, config)


@app.on_event("startup")
def start_core():
    logger.info("Generating Xray core config")

    start_time = time.time()
    config = xray.config.include_db_users()
    logger.info(f"Xray core config generated in {(time.time() - start_time):.2f} seconds")

    # main core
    logger.info("Starting main Xray core")
    try:
        xray.core.start(config)
        # Wait briefly and check if core is still running
        time.sleep(1)
        if not xray.core.started:
            logger.error("Xray core exited immediately after start!")
            if xray.core._logs_buffer:
                last_logs = list(xray.core._logs_buffer)[-20:]
                logger.error(f"Xray core output ({len(last_logs)} lines):")
                for line in last_logs:
                    logger.error(f"  [xray] {line}")
    except Exception:
        traceback.print_exc()

    # Hysteria2 core
    from config import HYSTERIA2_ENABLED
    if HYSTERIA2_ENABLED:
        try:
            from app.hysteria.core import Hysteria2Core
            from app.hysteria.config import write_hysteria2_config
            from config import HYSTERIA2_EXECUTABLE_PATH
            import os

            hy2_config_path = "/var/lib/marzban/hysteria2.json"
            cert_path = "/var/lib/marzban/certs/fullchain.pem"
            key_path = "/var/lib/marzban/certs/privkey.pem"
            # Generate config if certs exist
            if os.path.isfile(cert_path) and os.path.isfile(key_path):
                write_hysteria2_config(hy2_config_path, cert_path, key_path)
            if os.path.isfile(hy2_config_path) and os.path.isfile(HYSTERIA2_EXECUTABLE_PATH):
                global _hysteria2_core
                _hysteria2_core = Hysteria2Core(HYSTERIA2_EXECUTABLE_PATH)
                version = _hysteria2_core.get_version()
                logger.info(f"Starting Hysteria2 core ({version})")
                _hysteria2_core.start(hy2_config_path)
            else:
                missing = []
                if not os.path.isfile(HYSTERIA2_EXECUTABLE_PATH):
                    missing.append(f"binary ({HYSTERIA2_EXECUTABLE_PATH})")
                if not os.path.isfile(hy2_config_path):
                    missing.append(f"config ({hy2_config_path})")
                if not os.path.isfile(cert_path):
                    missing.append(f"cert ({cert_path})")
                if not os.path.isfile(key_path):
                    missing.append(f"key ({key_path})")
                logger.warning(f"Hysteria2 enabled but missing: {', '.join(missing)}")
        except Exception:
            logger.warning("Failed to start Hysteria2 core")
            traceback.print_exc()

    # TUIC core
    from config import TUIC_ENABLED
    if TUIC_ENABLED:
        try:
            from app.tuic.core import TUICCore
            from app.tuic.config import write_tuic_config
            from config import TUIC_EXECUTABLE_PATH
            import os

            tuic_config_path = "/var/lib/marzban/tuic.json"
            cert_path = "/var/lib/marzban/certs/fullchain.pem"
            key_path = "/var/lib/marzban/certs/privkey.pem"
            if os.path.isfile(cert_path) and os.path.isfile(key_path):
                write_tuic_config(tuic_config_path, cert_path, key_path)
            if os.path.isfile(tuic_config_path) and os.path.isfile(TUIC_EXECUTABLE_PATH):
                global _tuic_core
                _tuic_core = TUICCore(TUIC_EXECUTABLE_PATH)
                version = _tuic_core.get_version()
                logger.info(f"Starting TUIC core ({version})")
                _tuic_core.start(tuic_config_path)
            else:
                logger.warning("TUIC enabled but binary or config not found, skipping")
        except Exception:
            logger.warning("Failed to start TUIC core")
            traceback.print_exc()

    # Juicity core
    from config import JUICITY_ENABLED
    if JUICITY_ENABLED:
        try:
            from app.juicity.core import JuicityCore
            from app.juicity.config import write_juicity_config
            from config import JUICITY_EXECUTABLE_PATH
            import os

            juicity_config_path = "/var/lib/marzban/juicity.json"
            cert_path = "/var/lib/marzban/certs/fullchain.pem"
            key_path = "/var/lib/marzban/certs/privkey.pem"
            if os.path.isfile(cert_path) and os.path.isfile(key_path):
                write_juicity_config(juicity_config_path, cert_path, key_path)
            if os.path.isfile(juicity_config_path) and os.path.isfile(JUICITY_EXECUTABLE_PATH):
                global _juicity_core
                _juicity_core = JuicityCore(JUICITY_EXECUTABLE_PATH)
                version = _juicity_core.get_version()
                logger.info(f"Starting Juicity core ({version})")
                _juicity_core.start(juicity_config_path)
            else:
                logger.warning("Juicity enabled but binary or config not found, skipping")
        except Exception:
            logger.warning("Failed to start Juicity core")
            traceback.print_exc()

    # nodes' core
    logger.info("Starting nodes Xray core")
    with GetDB() as db:
        dbnodes = crud.get_nodes(db=db, enabled=True)
        node_ids = [dbnode.id for dbnode in dbnodes]
        for dbnode in dbnodes:
            crud.update_node_status(db, dbnode, NodeStatus.connecting)

    for node_id in node_ids:
        xray.operations.connect_node(node_id, config)

    scheduler.add_job(core_health_check, 'interval',
                      seconds=JOB_CORE_HEALTH_CHECK_INTERVAL,
                      coalesce=True, max_instances=1)

    # TUIC/Juicity config sync - only restart when user list changes
    _last_tuic_users = {}
    _last_juicity_users = {}

    def sync_tuic_juicity():
        nonlocal _last_tuic_users, _last_juicity_users
        global _tuic_core, _juicity_core
        cert_path = "/var/lib/marzban/certs/fullchain.pem"
        key_path = "/var/lib/marzban/certs/privkey.pem"
        if not os.path.isfile(cert_path) or not os.path.isfile(key_path):
            return
        if TUIC_ENABLED:
            try:
                from app.tuic.config import get_tuic_users, write_tuic_config
                current = get_tuic_users()
                if current != _last_tuic_users:
                    _last_tuic_users = current
                    write_tuic_config("/var/lib/marzban/tuic.json", cert_path, key_path)
                    if _tuic_core and _tuic_core.started:
                        _tuic_core.restart()
                        logger.info("TUIC config updated, core restarted")
            except Exception as e:
                logger.debug(f"TUIC sync: {e}")
        if JUICITY_ENABLED:
            try:
                from app.juicity.config import get_juicity_users, write_juicity_config
                current = get_juicity_users()
                if current != _last_juicity_users:
                    _last_juicity_users = current
                    write_juicity_config("/var/lib/marzban/juicity.json", cert_path, key_path)
                    if _juicity_core and _juicity_core.started:
                        _juicity_core.restart()
                        logger.info("Juicity config updated, core restarted")
            except Exception as e:
                logger.debug(f"Juicity sync: {e}")

    scheduler.add_job(sync_tuic_juicity, 'interval', seconds=60, coalesce=True, max_instances=1)


@app.on_event("shutdown")
def app_shutdown():
    logger.info("Stopping main Xray core")
    xray.core.stop()

    if '_hysteria2_core' in globals() and _hysteria2_core:
        logger.info("Stopping Hysteria2 core")
        _hysteria2_core.stop()

    try:
        if _tuic_core and _tuic_core.started:
            logger.info("Stopping TUIC core")
            _tuic_core.stop()
    except NameError:
        pass

    try:
        if _juicity_core and _juicity_core.started:
            logger.info("Stopping Juicity core")
            _juicity_core.stop()
    except NameError:
        pass

    logger.info("Stopping nodes Xray core")
    for node in list(xray.nodes.values()):
        try:
            node.disconnect()
        except Exception:
            pass
