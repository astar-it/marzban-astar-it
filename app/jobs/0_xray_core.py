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


@app.on_event("shutdown")
def app_shutdown():
    logger.info("Stopping main Xray core")
    xray.core.stop()

    logger.info("Stopping nodes Xray core")
    for node in list(xray.nodes.values()):
        try:
            node.disconnect()
        except Exception:
            pass
