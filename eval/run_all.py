"""Evaluate agent.py on ARC-AGI-2 puzzles. Concurrent. Saves trajectories."""
import json
import subprocess
import sys
import os
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

data_path = sys.argv[1]
max_workers = int(sys.argv[2]) if len(sys.argv) > 2 else 8

with open(data_path) as f:
    tasks = [json.loads(line) for line in f]

total = len(tasks)
correct = 0
completed = 0
results = []


def eval_one(idx, task):
    try:
        proc = subprocess.run(
            ["python3", "agent.py"],
            input=json.dumps(task), capture_output=True, text=True, timeout=60,
        )
        predicted = None
        passed = False
        if proc.returncode == 0:
            try:
                predicted = json.loads(proc.stdout.strip())
                passed = predicted == task["expected_output"]
            except json.JSONDecodeError:
                pass

        return {
            "index": idx,
            "passed": passed,
            "predicted": predicted,
            "expected": task["expected_output"],
            "input_grid_size": f"{len(task['test_input'])}x{len(task['test_input'][0])}",
            "num_fewshots": len(task["fewshots"]),
            "agent_stdout": proc.stdout[:2000] if proc.returncode != 0 else None,
            "agent_stderr": proc.stderr[:500] if proc.stderr else None,
            "exit_code": proc.returncode,
        }
    except Exception as e:
        return {
            "index": idx,
            "passed": False,
            "predicted": None,
            "expected": task["expected_output"],
            "error": str(e),
        }


print(f"Evaluating {total} puzzles ({max_workers} concurrent)...", file=sys.stderr)

with ThreadPoolExecutor(max_workers=max_workers) as pool:
    futures = {pool.submit(eval_one, i, t): i for i, t in enumerate(tasks)}
    for future in as_completed(futures):
        completed += 1
        result = future.result()
        results.append(result)
        if result["passed"]:
            correct += 1
        print(f"  {completed}/{total} done, {correct} correct", file=sys.stderr, end="\r")

print(file=sys.stderr)

# Save trajectory
os.makedirs("eval_results", exist_ok=True)
timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
trajectory_path = f"eval_results/{timestamp}.jsonl"
results.sort(key=lambda r: r["index"])
with open(trajectory_path, "w") as f:
    for r in results:
        f.write(json.dumps(r) + "\n")
print(f"Trajectory saved to {trajectory_path}", file=sys.stderr)

print("---")
print(f"accuracy:         {correct / total:.6f}" if total > 0 else "accuracy:         0.000000")
print(f"correct:          {correct}")
print(f"total:            {total}")
