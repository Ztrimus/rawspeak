#!/usr/bin/env bash
# Seed research/issue-12/samples/ with synthetic WAVs via macOS `say`.
#
# These are *bootstrap* samples to wire the harness end-to-end. They cannot
# replace real recordings for noise / accent / silence experiments, but they
# are good enough to check the pipeline runs and to compare cleanup prompts on
# fixed transcripts.
#
# Usage:  bash research/issue-12/seed_samples.sh
set -euo pipefail

if ! command -v say >/dev/null 2>&1; then
    echo "macOS 'say' not found — this script is macOS-only." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SAMPLES_DIR="$SCRIPT_DIR/samples"
mkdir -p "$SAMPLES_DIR"

# id|text  (text used both for synthesis and as ground_truth in references.json)
declare -a SAMPLES=(
    "syn_clean_short|Set up a meeting with the team tomorrow at three p m to review the launch plan."
    "syn_fillers|Um so basically I think we should you know like ship the feature behind a flag and uh see what happens."
    "syn_list|First clone the repo. Second install the dependencies. Third run the tests. Fourth open a pull request."
    "syn_jargon|Use faster whisper with the distil large v three model and pass the hotwords list for proper nouns."
    "syn_long_pause|Open the report.       Now move to the cost section.       Highlight the deployment cost."
    "syn_false_starts|I was thinking we should we should actually move the the meeting to friday instead of thursday."
)

for entry in "${SAMPLES[@]}"; do
    id="${entry%%|*}"
    text="${entry#*|}"
    out="$SAMPLES_DIR/$id.wav"
    echo "  -> $out"
    say --voice=Samantha \
        --output-file="$out" \
        --file-format=WAVE \
        --data-format=LEI16@16000 \
        "$text"
done

echo
echo "Done. ${#SAMPLES[@]} synthetic samples written to $SAMPLES_DIR"
echo "Update references.json's 'ideal' fields if you want different cleaned forms."
