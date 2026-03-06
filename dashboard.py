#!/usr/bin/env python3
"""
Auto-GIT Pipeline Dashboard — Streamlit real-time monitoring
═══════════════════════════════════════════════════════════════

Displays live pipeline progress, per-node timings, token usage,
model health, and cost tracking.

Usage:
    streamlit run dashboard.py

Reads from:
    logs/pipeline_progress.txt  — live progress heartbeat
    logs/pipeline_trace_*.jsonl — per-node event trace
    logs/agent_status_*.md      — final run report
    logs/model_health_*.json    — model health snapshot
"""

import os
import json
import glob
import time
from datetime import datetime
from pathlib import Path

try:
    import streamlit as st
    import pandas as pd
except ImportError:
    print("❌ Streamlit not installed. Run: pip install streamlit pandas")
    print("   Then: streamlit run dashboard.py")
    raise SystemExit(1)


LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")


def get_latest_file(pattern: str) -> str | None:
    """Find the most recent file matching a glob pattern in logs/."""
    files = sorted(glob.glob(os.path.join(LOGS_DIR, pattern)))
    return files[-1] if files else None


def load_trace_events(trace_path: str) -> list[dict]:
    """Load JSONL trace file into a list of dicts."""
    events = []
    try:
        with open(trace_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    except Exception:
        pass
    return events


def load_health(health_path: str) -> dict:
    """Load model health JSON."""
    try:
        with open(health_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_progress_lines() -> list[str]:
    """Load live progress lines."""
    path = os.path.join(LOGS_DIR, "pipeline_progress.txt")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.readlines()[-50:]  # last 50 lines
    except Exception:
        return []


# ── Streamlit App ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Auto-GIT Dashboard",
    page_icon="🐉",
    layout="wide",
)

st.title("🐉 Auto-GIT Pipeline Dashboard")

# Auto-refresh
refresh_rate = st.sidebar.slider("Refresh interval (s)", 2, 30, 5)
auto_refresh = st.sidebar.checkbox("Auto-refresh", value=True)

if auto_refresh:
    time.sleep(0.1)  # Small delay to prevent busy loop
    st.rerun()  # type: ignore

# ── Sidebar: Run Selection ────────────────────────────────────────────────────
trace_files = sorted(glob.glob(os.path.join(LOGS_DIR, "pipeline_trace_*.jsonl")))
if not trace_files:
    st.warning("No pipeline traces found in logs/. Run a pipeline first!")
    st.stop()

trace_labels = [os.path.basename(f).replace("pipeline_trace_", "").replace(".jsonl", "") for f in trace_files]
selected_idx = st.sidebar.selectbox("Select run", range(len(trace_files)),
                                     format_func=lambda i: trace_labels[i],
                                     index=len(trace_files) - 1)
trace_path = trace_files[selected_idx]
events = load_trace_events(trace_path)

# ── Live Progress ─────────────────────────────────────────────────────────────
st.header("📡 Live Progress")
progress_lines = load_progress_lines()
if progress_lines:
    st.code("".join(progress_lines[-15:]), language="text")
else:
    st.info("No progress data yet.")

# ── Pipeline Stages ───────────────────────────────────────────────────────────
st.header("📊 Pipeline Node Timings")

node_events = [e for e in events if e.get("event") == "node_complete"]
if node_events:
    rows = []
    for e in node_events:
        rows.append({
            "Node": e.get("node", "?"),
            "Call #": e.get("call_num", 1),
            "Duration (s)": e.get("elapsed_s", 0),
            "Stage": e.get("current_stage", ""),
            "Errors": e.get("error_count", 0),
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)

    # Bar chart of durations
    timing_df = df.groupby("Node")["Duration (s)"].sum().sort_values(ascending=True)
    st.bar_chart(timing_df)
else:
    st.info("No node events yet.")

# ── Token Usage ───────────────────────────────────────────────────────────────
st.header("🧠 Token Usage & Cost")

end_events = [e for e in events if e.get("event") == "pipeline_end"]
if end_events:
    ts = end_events[-1].get("token_stats", {})
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Calls", ts.get("calls", 0))
    col2.metric("Total Tokens", f"{ts.get('total_tokens', 0):,}")
    col3.metric("Prompt Tokens", f"{ts.get('prompt_tokens', 0):,}")
    col4.metric("Completion Tokens", f"{ts.get('completion_tokens', 0):,}")

    # Cost
    cost = ts.get("estimated_cost_usd", 0.0)
    st.metric("Estimated Cost", f"${cost:.4f} USD")

    # By profile
    by_profile = ts.get("by_profile", {})
    if by_profile:
        st.subheader("By Profile")
        profile_df = pd.DataFrame(
            [{"Profile": k, "Tokens": v} for k, v in sorted(by_profile.items(), key=lambda x: -x[1])]
        )
        st.dataframe(profile_df, use_container_width=True)

    # By model
    by_model = ts.get("by_model", {})
    if by_model:
        st.subheader("By Model (top 15)")
        model_df = pd.DataFrame(
            [{"Model": k, "Tokens": v} for k, v in sorted(by_model.items(), key=lambda x: -x[1])[:15]]
        )
        st.dataframe(model_df, use_container_width=True)
else:
    st.info("Pipeline not yet finished — token stats appear after completion.")

# ── Model Health ──────────────────────────────────────────────────────────────
st.header("⚕️ Model Health")

health_path = get_latest_file("model_health_*.json")
if health_path:
    health = load_health(health_path)

    col1, col2, col3 = st.columns(3)

    # Active models
    resolved = health.get("resolved", {})
    with col1:
        st.subheader("✅ Active")
        if resolved:
            for profile, model in sorted(resolved.items()):
                st.write(f"**{profile}** → `{model}`")
        else:
            st.write("None")

    # Dead models
    dead = health.get("dead", [])
    with col2:
        st.subheader("🚫 Dead (404)")
        if dead:
            for m in dead:
                st.write(f"- `{m}`")
        else:
            st.write("None")

    # Timed out
    timed_out = health.get("timed_out", {})
    with col3:
        st.subheader("⏱️ Timed Out")
        if timed_out:
            for m, cnt in sorted(timed_out.items(), key=lambda x: -x[1]):
                st.write(f"- `{m}`: {cnt}x")
        else:
            st.write("None")
else:
    st.info("No health data yet.")

# ── Generated Files ───────────────────────────────────────────────────────────
st.header("📁 Generated Files")
if end_events:
    files = end_events[-1].get("files_generated", [])
    if files:
        for f in files:
            st.write(f"- `{f}`")
    else:
        st.info("No files generated.")

# ── Raw Event Log ─────────────────────────────────────────────────────────────
with st.expander("📋 Raw Event Log"):
    for e in events[-20:]:
        st.json(e)

st.sidebar.markdown("---")
st.sidebar.markdown("**Auto-GIT** — Pipeline Dashboard")
st.sidebar.markdown(f"Trace: `{os.path.basename(trace_path)}`")
st.sidebar.markdown(f"Events: {len(events)}")
