#!/usr/bin/env bash
# Run one arm of the article-drafts benchmark, once.
#
# Usage: run_arm.sh <a|c> <run-index>
#
# - Clean-checkouts the arm repo into a throwaway workspace
# - Drives claude-code:claude-opus-4-8 headless with the arm-appropriate prompt
#   (A = naive implement; C = FFFlow spec-first pipeline), very high max-turns
# - Overlays the hidden tests and scores via `manage.py test`
# - Emits a per-run result line (pass count, duration) and saves the diff
#
# Correctness is the metric; duration is an annotation.
set -uo pipefail

ARM="$1"; IDX="$2"; TASK="$3"; PROBE="$4"; TESTFILE="$5"
BENCH=/home/claude/working/ffflow-plugin/benchmark
SRC=/home/claude/working/aaia-summer-2026-$ARM
RESULTS=$BENCH/results/$TASK
WS=$HOME/bench-ws/$TASK-$ARM-$IDX
mkdir -p "$RESULTS"

MODEL="claude-code:claude-opus-4-8"
MAX_TURNS=400
ISSUE="$(cat "$BENCH/tasks/$TASK/issue.md")"

# --- clean checkout: tracked files only, no db/venv/pycache/build junk ---
rm -rf "$WS"; mkdir -p "$WS"
git -C "$SRC" archive HEAD | tar -x -C "$WS"
# each arm needs a working venv; reuse the source repo's (symlink to save time)
ln -s "$SRC/.venv" "$WS/.venv"

# Snapshot the BASE state in a throwaway git repo BEFORE the agent runs, so we
# can diff the agent's net change against it afterward (mirrors VulcanBench).
cd "$WS"
printf '.venv\n__pycache__/\n*.pyc\ndb.sqlite3\n.pytest_cache/\n' > .gitignore
git init -q
git -c user.email=b@b -c user.name=b add -A
git -c user.email=b@b -c user.name=b commit -q -m base

# --- arm-specific prompt ---
if [ "$ARM" = "a" ]; then
  PROMPT="We're going to add a feature to this project.

$ISSUE

Implement it. Leave the finished implementation in the working tree; do not open a PR."
else
  PROMPT="We're going to add a feature to this project. This project uses FFFlow.

$ISSUE

Use /fff:plan-chat and /fff:plan-breakdown to design the target state and decompose the work into an ordered set of small chess moves. Then /fff:work-issue each one in dependency order — updating specs, implementing, and self-reviewing per move — so each is a clean, disciplined step that passes the project's automated checks. Consult the specs in docs/specs/ and the per-module CLAUDE.md files to understand the existing contracts before writing code.

Work on a single branch. When finished, leave that branch checked out with all commits applied, so the completed feature is present in the working tree. Do not open a PR, and do not reset, stash, or return to the base branch."
fi

echo "[$ARM-$IDX] running agent (max_turns=$MAX_TURNS)..." >&2
START=$(cat /proc/uptime | cut -d' ' -f1)

cd "$WS"
# Hermetic project settings so C's .claude/ plugin declaration loads and A's does not.
timeout 5400 claude -p "$PROMPT" \
  --output-format stream-json --verbose \
  --model claude-opus-4-8 --max-turns $MAX_TURNS \
  --dangerously-skip-permissions --setting-sources project \
  > "$RESULTS/$ARM-$IDX.stream.jsonl" 2> "$RESULTS/$ARM-$IDX.stderr" &
AGENT_PID=$!
wait $AGENT_PID
AGENT_RC=$?

END=$(cat /proc/uptime | cut -d' ' -f1)
DUR=$(awk "BEGIN{printf \"%.0f\", $END - $START}")

# --- capture the net working-tree change vs the base commit ---
cd "$WS"
git -c user.email=b@b -c user.name=b add -A 2>/dev/null
git diff --cached HEAD > "$RESULTS/$ARM-$IDX.final.patch" 2>/dev/null

# --- score: overlay hidden tests, run manage.py test ---
mkdir -p "$WS/$PROBE"; touch "$WS/$PROBE/__init__.py"
cp "$BENCH/tasks/$TASK/tests/$TESTFILE" "$WS/$PROBE/tests.py"
# ensure migrations exist for any model change the agent made
DEBUG=true DATABASE_URL=':memory:' "$WS/.venv/bin/python" manage.py makemigrations 2>/dev/null | tail -2 >&2
TEST_OUT=$(DEBUG=true DATABASE_URL=':memory:' timeout 300 "$WS/.venv/bin/python" manage.py test $PROBE --verbosity=1 2>&1)
echo "$TEST_OUT" > "$RESULTS/$ARM-$IDX.testout"

# parse "Ran N tests" and failures/errors
RAN=$(echo "$TEST_OUT" | grep -oE 'Ran [0-9]+ test' | grep -oE '[0-9]+' | head -1)
FAILS=$(echo "$TEST_OUT" | grep -oE '(failures|errors)=[0-9]+' | grep -oE '[0-9]+' | awk '{s+=$1} END{print s+0}')
RAN=${RAN:-0}; FAILS=${FAILS:-$RAN}
PASS=$((RAN - FAILS))

echo "[$ARM-$IDX] pass=$PASS/$RAN dur=${DUR}s agent_rc=$AGENT_RC" | tee -a "$RESULTS/summary.txt"
echo "$TASK,$ARM,$IDX,$PASS,$RAN,$DUR,$AGENT_RC" >> "$RESULTS/summary.csv"

# --- regression gate: overlay C's behavior suite onto THIS arm's final tree ---
CSUITE=/home/claude/working/aaia-summer-2026-c
for app in accounts articles comments; do
  cp "$CSUITE/apps/$app/tests.py" "$WS/apps/$app/tests.py" 2>/dev/null
done
# ensure any model the agent added has migrations, then run the 107-test baseline
DEBUG=true DATABASE_URL=':memory:' "$WS/.venv/bin/python" manage.py makemigrations 2>/dev/null | tail -1 >&2
REG_OUT=$(DEBUG=true DATABASE_URL=':memory:' timeout 300 "$WS/.venv/bin/python" -m pytest   apps/accounts/tests.py apps/articles/tests.py apps/comments/tests.py -q   --deselect "apps/accounts/tests.py::UserIdentityPropertyTest::test_authentication_always_keyed_on_email_not_username"   2>&1)
echo "$REG_OUT" > "$RESULTS/$ARM-$IDX.regression"
REG_PASS=$(echo "$REG_OUT" | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+' | head -1); REG_PASS=${REG_PASS:-0}
REG_FAIL=$(echo "$REG_OUT" | grep -oE '[0-9]+ failed' | grep -oE '[0-9]+' | head -1); REG_FAIL=${REG_FAIL:-0}
echo "[$ARM-$IDX] regression: $REG_PASS passed / $REG_FAIL failed (baseline 107/0)" | tee -a "$RESULTS/summary.txt"
echo "$TASK,$ARM,$IDX,regression,$REG_PASS,$REG_FAIL" >> "$RESULTS/summary.csv"

