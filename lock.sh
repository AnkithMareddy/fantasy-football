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
# Long enough to outlast a full pipeline run. 1200s was not: a measured run on
# 2026-10-22 spent 8m25s in sensitivity.py alone and over 20 minutes in total, so a
# deploy queued behind it hit the timeout and silently published nothing.
PIPELINE_LOCK_WAIT="${PIPELINE_LOCK_WAIT:-3600}"   # seconds to wait before giving up
PIPELINE_LOCK_STALE_MIN="${PIPELINE_LOCK_STALE_MIN:-60}"

acquire_pipeline_lock() {
    # Already held further up our own call stack — nothing to do.
    [ -n "${PIPELINE_LOCK_HELD:-}" ] && return 0

    mkdir -p state
    local waited=0

    until mkdir "$PIPELINE_LOCK" 2>/dev/null; do
        # Whoever holds it records their pid. If that process is gone the lock is an
        # orphan and can be taken at once.
        #
        # This matters more than the age check below, which was the only reclaim at
        # first: on 2026-10-22 a run died without releasing, and both the launchd job and
        # a manual deploy sat waiting behind a lock with no owner. Nothing would have
        # moved for an HOUR, which would have swallowed the next scheduled run too.
        local holder
        holder="$(cat "$PIPELINE_LOCK/pid" 2>/dev/null || true)"
        if [ -n "$holder" ] && ! kill -0 "$holder" 2>/dev/null; then
            echo "lock.sh: lock holder pid $holder is gone; reclaiming the orphaned lock" >&2
            rm -rf "$PIPELINE_LOCK" 2>/dev/null
            continue
        fi
        # Belt and braces: a lock with no readable pid (written by an older version, or
        # the holder died between mkdir and writing it) still ages out.
        if [ -n "$(find "$PIPELINE_LOCK" -maxdepth 0 -mmin "+$PIPELINE_LOCK_STALE_MIN" 2>/dev/null)" ]; then
            echo "lock.sh: $PIPELINE_LOCK is older than ${PIPELINE_LOCK_STALE_MIN}m; assuming a dead run and reclaiming it" >&2
            rm -rf "$PIPELINE_LOCK" 2>/dev/null
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

    # Record the owner so a contender can tell "in progress" from "died holding it".
    echo "$$" > "$PIPELINE_LOCK/pid" 2>/dev/null || true

    # Exported, so anything we invoke knows the lock is held and skips acquiring it.
    PIPELINE_LOCK_HELD=1
    export PIPELINE_LOCK_HELD
    # NOT exported: only the shell that actually created the directory may remove it, so a
    # child process exiting can't release a lock its parent still depends on.
    PIPELINE_LOCK_OWNER=1
    return 0
}

release_pipeline_lock() {
    # rm -rf, not rmdir: the lock directory now holds a pid file.
    [ -n "${PIPELINE_LOCK_OWNER:-}" ] && rm -rf "$PIPELINE_LOCK" 2>/dev/null
    return 0
}
