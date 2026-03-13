import subprocess
from typing import Dict, Any, List


class GitError(Exception):
    pass


class GitService:
    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path

    def _run_git(self, args: List[str]) -> str:
        try:
            result = subprocess.run(
                ["git"] + args, cwd=self.repo_path, capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise GitError(f"Git command failed: {e.stderr}")

    def get_status(self) -> Dict[str, Any]:
        output = self._run_git(["status", "--porcelain"])
        files = []
        for line in output.split("\n"):
            if line:
                status = line[:2]
                path = line[3:]
                files.append({"path": path, "status": status})

        branch = self._run_git(["branch", "--show-current"])
        return {"branch": branch, "files": files, "is_clean": len(files) == 0}

    def get_diff(self) -> str:
        return self._run_git(["diff"])

    def commit(self, message: str, files: List[str] = None) -> Dict[str, Any]:
        if not files:
            files = ["."]
        self._run_git(["add"] + files)
        self._run_git(["commit", "-m", message])

        log = self._run_git(["log", "-1", "--format=%H|%s"])
        parts = log.split("|", 1)
        return {
            "hash": parts[0] if len(parts) > 0 else "",
            "message": parts[1] if len(parts) > 1 else "",
            "success": True,
        }

    def get_log(self, limit: int = 10) -> List[Dict[str, Any]]:
        output = self._run_git(["log", f"-n{limit}", "--format=%H|%an|%ad|%s", "--date=iso"])
        logs = []
        for line in output.split("\n"):
            if line:
                parts = line.split("|", 3)
                if len(parts) == 4:
                    logs.append(
                        {
                            "hash": parts[0],
                            "author": parts[1],
                            "date": parts[2],
                            "message": parts[3],
                        }
                    )
        return logs
