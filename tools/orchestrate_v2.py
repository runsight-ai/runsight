import os
import sys
import time
import json
import subprocess
import re


def run_command(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def spawn_team(config_path):
    print(f"Spawning team with config {config_path}...")
    cmd = f"runsight --auto-approve create-team --config {config_path}"
    code, stdout, stderr = run_command(cmd)

    match = re.search(r"Team created: (team-[a-z0-9]+)", stdout)
    if not match:
        print("Failed to parse team ID from output.")
        print("STDOUT:", stdout)
        print("STDERR:", stderr)
        sys.exit(1)

    team_id = match.group(1)
    print(f"Successfully spawned {team_id}")
    return team_id


def wait_for_team(team_id):
    print(f"Waiting for {team_id} to finish...")
    while True:
        cmd = f"runsight team-status {team_id} --json"
        code, stdout, stderr = run_command(cmd)
        if code != 0:
            print(f"Error checking status for {team_id}. Retrying...")
            time.sleep(10)
            continue

        try:
            data = json.loads(stdout)
            status = data.get("team", {}).get("status", "unknown")
            print(f"[{time.strftime('%H:%M:%S')}] Status for {team_id}: {status}")
            if status in ["dead", "success", "failed"]:
                print(f"Team {team_id} finished with status {status}.")
                break
        except Exception as e:
            print(f"JSON parse error: {e}. Output: {stdout}")

        time.sleep(30)


def wait_for_pm_ux():
    print("Waiting for PM and UX teams to finish their initial files...")
    while True:
        roadmap_ready = os.path.exists(".agora/product_design_v2/product_roadmap.md")
        design_ready = os.path.exists(".agora/product_design_v2/design_system.md")

        if roadmap_ready and design_ready:
            print("Both product_roadmap.md and design_system.md are ready.")
            break
        print(f"[{time.strftime('%H:%M:%S')}] Still waiting for PM and UX baseline files...")
        time.sleep(30)


def main():
    print("--- Starting Orchestration Plan ---")

    # Step 1: Wait for baseline files
    wait_for_pm_ux()

    # Step 2: Mixed Team (Epic generation)
    mixed_team_id = spawn_team(".agora/epics/mixed_team.json")
    wait_for_team(mixed_team_id)

    # Step 3: Ensure mockups dir exists
    os.makedirs(".agora/epics/mockups", exist_ok=True)

    # Step 4: Mockup Team
    mockup_team_id = spawn_team(".agora/epics/mockup_team.json")
    wait_for_team(mockup_team_id)

    print("--- Orchestration Plan Completed ---")


if __name__ == "__main__":
    main()
