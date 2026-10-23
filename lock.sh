#!/bin/bash
# Serialise pipeline runs. Source this; do not execute it.
#
# Why: two different things now refresh this league. The launchd job (autorefresh.sh)
# fires at 8:05 and 23:05, and the Claude routine fires a few minutes later after its
# dispatch jitter. Both run update.sh and both publish the site, so without a shared
# lock they can be part-way through writing the same state/*.json files at the same
# time and leave a torn mix of two runs behind.
#
# The lock is a directory, because mkdir is atomic on macOS and flock isn't available.
#
# Callers that already hold it (autorefresh.sh takes it once, then calls update.sh and
# deploy_site.sh) export PIPELINE_LOCK_HELD so the nested calls don't deadlock waiting
# for a lock their own parent is holding.
#
# Contending callers WAIT rather than skip: when the routine has just written new injury
# overrides it needs a run that reflects them, so quietly skipping would hand it stale
# numbers — worse than being a few minutes late.

PIPELINE_LOCK="${PIPELINE_LOCK:-state/pipeline.lock}"
PIPELINE_LOCK_WAIT="${PIPELINE_LOCK_WAIT:-1200}"   # seconds to wait before giving up
PIPELINE_LOCK_STALE_MIN="${PIPELINE_LOCK_STALE_MIN:-60}"

acquire_pipeline_lock() {
    # Already held further up our own call stack — nothing to do.
    [ -n "${PIPELINE_LOCK_HELD:-}" ] && return 0

    mkdir -p state
    local waited=0

    until mkdir "$PIPELINE_LOCK" 2>/dev/null; do
        # A run killed mid-flight (crash, reboot, SIGKILL) leaves its lock behind. Without
        # this the pipeline would be wedged until someone noticed and deleted it by hand.
        if [ -n "$(find "$PIPELINE_LOCK" -maxdepth 0 -mmin "+$PIPELINE_LOCK_STALE_MIN" 2>/dev/null)" ]; then
            echo "lock.sh: $PIPELINE_LOCK is older than ${PIPELINE_LOCK_STALE_MIN}m; assuming a dead run and reclaiming it" >&2
            rmdir "$PIPELINE_LOCK" 2>/dev/null
            continue
        fi
        if [ "$waited" -ge "$PIPELINE_LOCK_WAIT" ]; then
            echo "lock.sh: another pipeline run held the lock for ${PIPELINE_LOCK_WAIT}s; giving up" >&2
            return 1
        fi
        [ "$waited" -eq 0 ] && echo "lock.sh: another pipeline run is in progress; waiting" >&2
        sleep 10
        waited=$((waited + 10))
    done

    # Exported, so anything we invoke knows the lock is held and skips acquiring it.
    PIPELINE_LOCK_HELD=1
    export PIPELINE_LOCK_HELD
    # NOT exported: only the shell that actually created the directory may remove it, so a
    # child process exiting can't release a lock its parent still depends on.
    PIPELINE_LOCK_OWNER=1
    return 0
}

release_pipeline_lock() {
    [ -n "${PIPELINE_LOCK_OWNER:-}" ] && rmdir "$PIPELINE_LOCK" 2>/dev/null
    return 0
}
