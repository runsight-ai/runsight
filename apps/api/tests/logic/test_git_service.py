from unittest.mock import Mock, patch
import subprocess
import pytest
from runsight_api.logic.services.git_service import GitService, GitError


@patch("runsight_api.logic.services.git_service.subprocess.run")
def test_get_status_clean_repo(mock_run):
    mock_run.side_effect = [
        Mock(stdout="", stderr="", returncode=0),
        Mock(stdout="main\n", stderr="", returncode=0),
    ]
    service = GitService(repo_path="/repo")
    result = service.get_status()
    assert result["branch"] == "main"
    assert result["files"] == []
    assert result["is_clean"] is True
    assert mock_run.call_count == 2
    assert mock_run.call_args_list[0][0][0] == ["git", "status", "--porcelain"]
    assert mock_run.call_args_list[1][0][0] == ["git", "branch", "--show-current"]


@patch("runsight_api.logic.services.git_service.subprocess.run")
def test_get_status_dirty_repo_with_files(mock_run):
    # Git porcelain: 2-char status + space + path (MM=modified both, ??=untracked)
    mock_run.side_effect = [
        Mock(stdout="MM foo.py\n?? bar.txt\n", stderr="", returncode=0),
        Mock(stdout="feature\n", stderr="", returncode=0),
    ]
    service = GitService(repo_path="/repo")
    result = service.get_status()
    assert result["branch"] == "feature"
    assert len(result["files"]) == 2
    assert result["files"][0] == {"path": "foo.py", "status": "MM"}
    assert result["files"][1] == {"path": "bar.txt", "status": "??"}
    assert result["is_clean"] is False


@patch("runsight_api.logic.services.git_service.subprocess.run")
def test_get_diff_returns_diff_string(mock_run):
    mock_run.return_value = Mock(
        stdout="diff --git a/foo.py b/foo.py\n--- a/foo.py\n+++ b/foo.py\n+new line\n",
        stderr="",
        returncode=0,
    )
    service = GitService(repo_path="/repo")
    result = service.get_diff()
    assert "diff --git" in result
    assert "+new line" in result
    mock_run.assert_called_once()
    assert mock_run.call_args[0][0] == ["git", "diff"]


@patch("runsight_api.logic.services.git_service.subprocess.run")
def test_get_log_normal_limit(mock_run):
    mock_run.return_value = Mock(
        stdout="abc123|Alice|2025-01-01 12:00:00 +0000|First commit\n"
        "def456|Bob|2025-01-02 12:00:00 +0000|Second commit\n",
        stderr="",
        returncode=0,
    )
    service = GitService(repo_path="/repo")
    result = service.get_log(limit=10)
    assert len(result) == 2
    assert result[0]["hash"] == "abc123"
    assert result[0]["author"] == "Alice"
    assert result[0]["date"] == "2025-01-01 12:00:00 +0000"
    assert result[0]["message"] == "First commit"
    assert result[1]["hash"] == "def456"
    assert result[1]["message"] == "Second commit"
    mock_run.assert_called_once()
    assert mock_run.call_args[0][0] == [
        "git",
        "log",
        "-n10",
        "--format=%H|%an|%ad|%s",
        "--date=iso",
    ]


@patch("runsight_api.logic.services.git_service.subprocess.run")
def test_get_log_empty_log(mock_run):
    mock_run.return_value = Mock(stdout="", stderr="", returncode=0)
    service = GitService(repo_path="/repo")
    result = service.get_log(limit=5)
    assert result == []
    assert mock_run.call_args[0][0] == ["git", "log", "-n5", "--format=%H|%an|%ad|%s", "--date=iso"]


@patch("runsight_api.logic.services.git_service.subprocess.run")
def test_commit_happy_path(mock_run):
    mock_run.side_effect = [
        Mock(stdout="", stderr="", returncode=0),
        Mock(stdout="", stderr="", returncode=0),
        Mock(stdout="abc123def|My commit message\n", stderr="", returncode=0),
    ]
    service = GitService(repo_path="/repo")
    result = service.commit("My commit message", files=["foo.py", "bar.py"])
    assert result["success"] is True
    assert result["hash"] == "abc123def"
    assert result["message"] == "My commit message"
    assert mock_run.call_count == 3
    assert mock_run.call_args_list[0][0][0] == ["git", "add", "foo.py", "bar.py"]
    assert mock_run.call_args_list[1][0][0] == ["git", "commit", "-m", "My commit message"]
    assert mock_run.call_args_list[2][0][0] == ["git", "log", "-1", "--format=%H|%s"]


@patch("runsight_api.logic.services.git_service.subprocess.run")
def test_commit_files_none_defaults_to_dot(mock_run):
    mock_run.side_effect = [
        Mock(stdout="", stderr="", returncode=0),
        Mock(stdout="", stderr="", returncode=0),
        Mock(stdout="abc|msg\n", stderr="", returncode=0),
    ]
    service = GitService(repo_path="/repo")
    service.commit("Message", files=None)
    assert mock_run.call_args_list[0][0][0] == ["git", "add", "."]


@patch("runsight_api.logic.services.git_service.subprocess.run")
def test_git_error_on_status(mock_run):
    mock_run.side_effect = subprocess.CalledProcessError(
        1, "git", stderr="fatal: not a git repository"
    )
    service = GitService(repo_path="/nonexistent")
    with pytest.raises(GitError) as exc_info:
        service.get_status()
    assert "fatal: not a git repository" in str(exc_info.value)


@patch("runsight_api.logic.services.git_service.subprocess.run")
def test_git_error_on_diff(mock_run):
    mock_run.side_effect = subprocess.CalledProcessError(128, "git", stderr="fatal: bad revision")
    service = GitService(repo_path="/repo")
    with pytest.raises(GitError) as exc_info:
        service.get_diff()
    assert "fatal: bad revision" in str(exc_info.value)


@patch("runsight_api.logic.services.git_service.subprocess.run")
def test_git_error_on_commit(mock_run):
    mock_run.side_effect = [
        Mock(stdout="", stderr="", returncode=0),
        subprocess.CalledProcessError(1, "git", stderr="nothing to commit"),
    ]
    service = GitService(repo_path="/repo")
    with pytest.raises(GitError) as exc_info:
        service.commit("Message")
    assert "nothing to commit" in str(exc_info.value)
