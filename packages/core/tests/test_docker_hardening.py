"""
RUN-821 — Docker hardening tests.

These tests are RED-phase: they assert on security posture that does not yet exist.
Every test here is expected to FAIL until Green implements:

1. Dockerfile — runsight user (UID/GID 1000), git safe.directory, USER directive
2. docker-compose.yml — init-permissions service, cap_drop, no-new-privileges,
   mem_limit, cpus, init: true, depends_on
3. docker-entrypoint.sh — fail-fast when workspace is absent (no mkdir)
4. process-isolation.md — Layer 4 updated to reflect container hardening

Acceptance Criteria coverage:
- AC1: Process runs as UID 1000 (runsight), not root
- AC2: Memory limits via cgroup OOM (mem_limit / memswap_limit in compose)
- AC3: Zero Linux capabilities (cap_drop: ALL, no cap_add)
- AC4: no-new-privileges security_opt
- AC5: init-permissions service owns /workspace before main service
- AC6: git safe.directory configured at build time
- AC7: zombie reaping via tini (init: true in compose)
"""

import re
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml

# Resolve repo root: packages/core/tests/ is 3 levels deep from root.
REPO_ROOT = Path(__file__).resolve().parents[3]

DOCKERFILE = REPO_ROOT / "Dockerfile"
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
ENTRYPOINT = REPO_ROOT / "docker-entrypoint.sh"
PROCESS_ISOLATION_MD = (
    REPO_ROOT
    / "apps"
    / "site"
    / "src"
    / "content"
    / "docs"
    / "docs"
    / "execution"
    / "process-isolation.md"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_dockerfile() -> str:
    return DOCKERFILE.read_text()


def _load_compose() -> dict:
    return yaml.safe_load(COMPOSE_FILE.read_text())


def _read_entrypoint() -> str:
    return ENTRYPOINT.read_text()


def _read_process_isolation_md() -> str:
    return PROCESS_ISOLATION_MD.read_text()


def _runtime_stage_lines(dockerfile_text: str) -> list[str]:
    """Return lines that belong to the runtime stage (after 'AS runtime')."""
    lines = dockerfile_text.splitlines()
    in_runtime = False
    result = []
    for line in lines:
        if re.search(r"FROM\s+\S+\s+AS\s+runtime", line, re.IGNORECASE):
            in_runtime = True
            continue
        if in_runtime and re.match(r"FROM\s+", line, re.IGNORECASE):
            # Next FROM stage — stop collecting.
            break
        if in_runtime:
            result.append(line)
    return result


# ===========================================================================
# SECTION 1 — Dockerfile: non-root user, UID 1000, git safe.directory
# ===========================================================================


class TestDockerfileNonRootUser:
    """AC1 / AC6 — Dockerfile must create and switch to UID 1000 user."""

    def test_user_directive_exists_in_runtime_stage(self):
        """A USER directive must be present in the runtime stage."""
        runtime_lines = _runtime_stage_lines(_read_dockerfile())
        user_directives = [ln for ln in runtime_lines if re.match(r"^\s*USER\s+", ln)]
        assert user_directives, (
            "No USER directive found in the runtime stage. "
            "Green must add 'USER runsight' (or USER 1000) to the runtime stage."
        )

    def test_user_directive_names_runsight(self):
        """The USER directive must reference the runsight user (not root, not numeric root)."""
        runtime_lines = _runtime_stage_lines(_read_dockerfile())
        user_directives = [ln for ln in runtime_lines if re.match(r"^\s*USER\s+", ln)]
        assert user_directives, (
            "No USER directive found in the runtime stage — cannot verify it names 'runsight'. "
            "Green must add 'USER runsight' to the runtime stage."
        )
        for line in user_directives:
            m = re.match(r"^\s*USER\s+(\S+)", line)
            if m:
                user_value = m.group(1).lower()
                assert "runsight" in user_value or user_value == "1000", (
                    f"USER directive is '{m.group(1)}', expected 'runsight' or '1000'. "
                    "Green must use the named runsight user."
                )

    def test_groupadd_creates_gid_1000(self):
        """groupadd must create the runsight group with GID 1000."""
        dockerfile_text = _read_dockerfile()
        runtime_lines = _runtime_stage_lines(dockerfile_text)
        runtime_block = "\n".join(runtime_lines)
        assert re.search(r"groupadd\b.*--gid\s+1000", runtime_block) or re.search(
            r"groupadd\b.*-g\s+1000", runtime_block
        ), (
            "No groupadd with GID 1000 found in runtime stage. "
            "Green must add: groupadd --gid 1000 runsight"
        )

    def test_useradd_creates_uid_1000(self):
        """useradd must create the runsight user with UID 1000."""
        runtime_block = "\n".join(_runtime_stage_lines(_read_dockerfile()))
        assert re.search(r"useradd\b.*--uid\s+1000", runtime_block) or re.search(
            r"useradd\b.*-u\s+1000", runtime_block
        ), (
            "No useradd with UID 1000 found in runtime stage. "
            "Green must add: useradd --uid 1000 --gid 1000 runsight"
        )

    def test_useradd_references_runsight(self):
        """useradd must create a user named 'runsight'."""
        runtime_block = "\n".join(_runtime_stage_lines(_read_dockerfile()))
        assert re.search(r"useradd\b.*runsight", runtime_block), (
            "No 'useradd ... runsight' found in runtime stage. Green must name the user 'runsight'."
        )

    def test_git_safe_directory_configured(self):
        """git config safe.directory /workspace must be set at build time."""
        runtime_block = "\n".join(_runtime_stage_lines(_read_dockerfile()))
        assert re.search(
            r"git\s+config\s+--global\s+--add\s+safe\.directory\s+/workspace", runtime_block
        ), (
            "git safe.directory /workspace not configured in the Dockerfile runtime stage. "
            "Green must add: RUN git config --global --add safe.directory /workspace"
        )

    def test_workspace_dir_created_with_correct_ownership(self):
        """
        /workspace must be pre-created and chowned to the runsight user
        in the Dockerfile so the non-root user can write to it.
        """
        runtime_block = "\n".join(_runtime_stage_lines(_read_dockerfile()))
        # Accept either explicit mkdir+chown or combined form.
        has_mkdir = re.search(r"mkdir\s+-p\s+/workspace", runtime_block)
        has_chown = re.search(
            r"chown\s+.*runsight.*:.*runsight.*\s+/workspace", runtime_block
        ) or re.search(r"chown\s+1000:1000\s+/workspace", runtime_block)
        assert has_mkdir and has_chown, (
            "Dockerfile runtime stage must mkdir /workspace and chown it to runsight:runsight (1000:1000). "
            f"mkdir found: {bool(has_mkdir)}, chown found: {bool(has_chown)}"
        )


# ===========================================================================
# SECTION 2 — docker-compose.yml: security settings
# ===========================================================================


class TestDockerComposeInitPermissions:
    """AC5 — init-permissions service must set up /workspace before main service."""

    def test_init_permissions_service_exists(self):
        """An 'init-permissions' service must exist in docker-compose.yml."""
        compose = _load_compose()
        services = compose.get("services", {})
        assert "init-permissions" in services, (
            "No 'init-permissions' service found in docker-compose.yml. "
            "Green must add a service that chowns /workspace to UID 1000."
        )

    def test_init_permissions_uses_busybox(self):
        """init-permissions service must use a minimal image (busybox)."""
        compose = _load_compose()
        svc = compose.get("services", {}).get("init-permissions", {})
        image = svc.get("image", "")
        assert "busybox" in image.lower(), (
            f"init-permissions uses image '{image}', expected a busybox-based image. "
            "Green must use 'busybox' for the init-permissions service."
        )

    def test_init_permissions_runs_as_root(self):
        """init-permissions service must run as root (user: '0') to chown files."""
        compose = _load_compose()
        svc = compose.get("services", {}).get("init-permissions", {})
        user = str(svc.get("user", ""))
        assert user == "0", (
            f"init-permissions service user is '{user}', expected '0' (root). "
            "Green must set user: '0' so it can chown /workspace."
        )

    def test_init_permissions_has_cap_drop_all(self):
        """init-permissions service must drop all capabilities."""
        compose = _load_compose()
        svc = compose.get("services", {}).get("init-permissions", {})
        cap_drop = svc.get("cap_drop", [])
        assert "ALL" in cap_drop, (
            f"init-permissions cap_drop is {cap_drop}, expected ['ALL']. "
            "Green must add cap_drop: [ALL] to the init-permissions service."
        )

    def test_init_permissions_has_cap_add_chown_only(self):
        """init-permissions must add back only CAP_CHOWN."""
        compose = _load_compose()
        svc = compose.get("services", {}).get("init-permissions", {})
        cap_add = svc.get("cap_add", [])
        assert cap_add == ["CHOWN"], (
            f"init-permissions cap_add is {cap_add}, expected ['CHOWN']. "
            "Green must add cap_add: [CHOWN] only."
        )


class TestDockerComposeRunsightServiceSecurity:
    """AC2 / AC3 / AC4 / AC7 — runsight service must be locked down."""

    def test_runsight_has_cap_drop_all(self):
        """runsight service must drop ALL Linux capabilities."""
        compose = _load_compose()
        svc = compose.get("services", {}).get("runsight", {})
        cap_drop = svc.get("cap_drop", [])
        assert "ALL" in cap_drop, (
            f"runsight cap_drop is {cap_drop}, expected ['ALL']. "
            "Green must add cap_drop: [ALL] to the runsight service."
        )

    def test_runsight_has_no_cap_add(self):
        """
        runsight service must NOT have a cap_add directive.
        This test also verifies cap_drop: ALL is already present (otherwise
        'no cap_add' is trivially true for any unconfigured service).
        """
        compose = _load_compose()
        svc = compose.get("services", {}).get("runsight", {})
        # First check cap_drop is configured — makes this test load-bearing.
        cap_drop = svc.get("cap_drop", [])
        assert "ALL" in cap_drop, (
            f"runsight cap_drop is {cap_drop}. "
            "Green must add cap_drop: [ALL] before the no-cap_add assertion is meaningful."
        )
        cap_add = svc.get("cap_add")
        assert cap_add is None or cap_add == [], (
            f"runsight has cap_add: {cap_add}. "
            "Green must not add any capabilities back to the runsight service."
        )

    def test_runsight_has_no_new_privileges(self):
        """runsight service must set security_opt: no-new-privileges:true."""
        compose = _load_compose()
        svc = compose.get("services", {}).get("runsight", {})
        security_opt = svc.get("security_opt", [])
        assert "no-new-privileges:true" in security_opt, (
            f"runsight security_opt is {security_opt}, "
            "expected 'no-new-privileges:true'. "
            "Green must add security_opt: [no-new-privileges:true]."
        )

    def test_runsight_has_mem_limit(self):
        """runsight service must have a mem_limit set (4g or equivalent)."""
        compose = _load_compose()
        svc = compose.get("services", {}).get("runsight", {})
        mem_limit = svc.get("mem_limit")
        assert mem_limit is not None, (
            "runsight service has no mem_limit. Green must add mem_limit: 4g to cap memory usage."
        )
        assert str(mem_limit).lower() in ("4g", "4096m", "4294967296"), (
            f"runsight mem_limit is '{mem_limit}', expected '4g'. Green must set mem_limit: 4g."
        )

    def test_runsight_has_memswap_limit(self):
        """runsight service must have memswap_limit equal to mem_limit to prevent swap usage."""
        compose = _load_compose()
        svc = compose.get("services", {}).get("runsight", {})
        memswap = svc.get("memswap_limit")
        assert memswap is not None, (
            "runsight service has no memswap_limit. "
            "Green must add memswap_limit: 4g to prevent OOM evasion via swap."
        )
        assert str(memswap).lower() in ("4g", "4096m", "4294967296"), (
            f"runsight memswap_limit is '{memswap}', expected '4g'. "
            "Green must set memswap_limit: 4g."
        )

    def test_runsight_has_cpus_limit(self):
        """runsight service must have a cpus limit."""
        compose = _load_compose()
        svc = compose.get("services", {}).get("runsight", {})
        cpus = svc.get("cpus")
        assert cpus is not None, (
            "runsight service has no cpus limit. Green must add cpus: 2 to cap CPU usage."
        )
        assert float(cpus) == 2.0, f"runsight cpus is {cpus}, expected 2. Green must set cpus: 2."

    def test_runsight_has_init_true(self):
        """runsight service must use init: true so tini (PID 1) reaps zombie processes."""
        compose = _load_compose()
        svc = compose.get("services", {}).get("runsight", {})
        init_flag = svc.get("init")
        assert init_flag is True, (
            f"runsight 'init' flag is {init_flag!r}, expected True. "
            "Green must add init: true so Docker injects tini as PID 1."
        )

    def test_runsight_depends_on_init_permissions(self):
        """runsight service must depend on init-permissions completing successfully."""
        compose = _load_compose()
        svc = compose.get("services", {}).get("runsight", {})
        depends_on = svc.get("depends_on", {})

        # depends_on can be a list or dict form.
        if isinstance(depends_on, list):
            assert "init-permissions" in depends_on, (
                f"runsight depends_on is {depends_on}. "
                "Green must add init-permissions to depends_on."
            )
        elif isinstance(depends_on, dict):
            assert "init-permissions" in depends_on, (
                f"runsight depends_on keys are {list(depends_on.keys())}. "
                "Green must add init-permissions to depends_on."
            )
            condition = depends_on["init-permissions"].get("condition")
            assert condition == "service_completed_successfully", (
                f"init-permissions condition is '{condition}', "
                "expected 'service_completed_successfully'. "
                "Green must use condition: service_completed_successfully."
            )
        else:
            pytest.fail(
                f"runsight depends_on is missing or malformed: {depends_on!r}. "
                "Green must add depends_on: init-permissions with condition: service_completed_successfully."
            )


# ===========================================================================
# SECTION 3 — docker-entrypoint.sh: fail-fast, no mkdir
# ===========================================================================


class TestEntrypointBehavior:
    """AC1 / AC5 — Entrypoint must fail-fast when workspace absent; no mkdir."""

    def test_entrypoint_has_no_mkdir(self):
        """
        The updated entrypoint must NOT contain mkdir.
        Non-root containers cannot create root-owned directories at runtime.
        """
        entrypoint_text = _read_entrypoint()
        assert "mkdir" not in entrypoint_text, (
            "docker-entrypoint.sh still contains 'mkdir'. "
            "Green must remove all mkdir calls — init-permissions handles ownership, "
            "and the container runs as non-root."
        )

    def test_entrypoint_exits_nonzero_when_workspace_missing(self):
        """
        When RUNSIGHT_BASE_PATH does not exist the entrypoint must exit with
        a non-zero status code and a meaningful error message.
        """
        with tempfile.TemporaryDirectory() as tmp:
            missing_path = str(Path(tmp) / "nonexistent-workspace")
            result = subprocess.run(
                ["sh", str(ENTRYPOINT), "true"],
                env={
                    "PATH": "/app/.venv/bin:/usr/local/bin:/usr/bin:/bin",
                    "RUNSIGHT_BASE_PATH": missing_path,
                },
                capture_output=True,
                text=True,
            )
        assert result.returncode != 0, (
            f"Entrypoint exited with code {result.returncode} (expected non-zero) "
            f"when workspace '{missing_path}' does not exist. "
            "Green must add a fail-fast check: if workspace is absent, exit 1."
        )

    def test_entrypoint_succeeds_when_workspace_exists(self):
        """
        When RUNSIGHT_BASE_PATH exists the entrypoint must exit with code 0
        and pass through to exec.
        """
        with tempfile.TemporaryDirectory() as workspace:
            result = subprocess.run(
                ["sh", str(ENTRYPOINT), "true"],
                env={
                    "PATH": "/app/.venv/bin:/usr/local/bin:/usr/bin:/bin",
                    "RUNSIGHT_BASE_PATH": workspace,
                },
                capture_output=True,
                text=True,
            )
        assert result.returncode == 0, (
            f"Entrypoint exited with code {result.returncode} when workspace exists. "
            f"stdout: {result.stdout!r}, stderr: {result.stderr!r}"
        )

    def test_entrypoint_prints_scaffold_message_for_empty_workspace(self):
        """
        When the workspace exists but is empty the entrypoint should print a
        message indicating Runsight will scaffold a new project.
        """
        with tempfile.TemporaryDirectory() as workspace:
            result = subprocess.run(
                ["sh", str(ENTRYPOINT), "true"],
                env={
                    "PATH": "/app/.venv/bin:/usr/local/bin:/usr/bin:/bin",
                    "RUNSIGHT_BASE_PATH": workspace,
                },
                capture_output=True,
                text=True,
            )
        combined = result.stdout + result.stderr
        assert "scaffold" in combined.lower(), (
            "Entrypoint did not print a scaffolding message for an empty workspace. "
            f"Output was: {combined!r}"
        )


# ===========================================================================
# SECTION 4 — process-isolation.md: Container hardening is Layer 1, active
# ===========================================================================


class TestProcessIsolationDocsUpdated:
    """AC3 / AC2 — Documentation must reflect container hardening as Layer 1."""

    def test_container_hardening_is_layer_1(self):
        """Container hardening must be Layer 1 (outermost defense layer)."""
        md = _read_process_isolation_md()
        layer1_lines = [ln for ln in md.splitlines() if "Layer 1" in ln]
        assert layer1_lines, "No 'Layer 1' line found in process-isolation.md."
        layer1_text = " ".join(layer1_lines).lower()
        assert "container" in layer1_text or "hardening" in layer1_text, (
            f"Layer 1 does not mention container hardening: {layer1_lines}. "
            "Container hardening must be the outermost layer (Layer 1)."
        )

    def test_layer_1_does_not_say_future(self):
        """Container hardening layer must not contain 'future' — it is active."""
        md = _read_process_isolation_md()
        layer1_lines = [ln for ln in md.splitlines() if "Layer 1" in ln]
        assert layer1_lines, "No 'Layer 1' line found in process-isolation.md."
        layer1_text = " ".join(layer1_lines).lower()
        assert "future" not in layer1_text, (
            f"Layer 1 description still contains 'future': {layer1_lines}. "
            "Container hardening is active, not future."
        )

    def test_layer_1_mentions_unprivileged_user(self):
        """
        Container hardening layer must mention the unprivileged user,
        using human-readable language.
        """
        md = _read_process_isolation_md()
        layer1_lines = [ln for ln in md.splitlines() if "Layer 1" in ln]
        assert layer1_lines, "No 'Layer 1' line found in process-isolation.md."
        layer1_text = " ".join(layer1_lines).lower()
        assert "unprivileged" in layer1_text or "non-root" in layer1_text, (
            f"Layer 1 does not mention unprivileged/non-root user: {layer1_lines}. "
            "Container hardening layer must reference the unprivileged container user."
        )

    def test_cpu_memory_limits_row_not_unenforced(self):
        """
        The CPU / memory limits row in the Known Limitations table must no longer
        say 'Not enforced' — it should reflect container-level enforcement.
        """
        md = _read_process_isolation_md()
        lines = md.splitlines()
        cpu_mem_lines = [ln for ln in lines if "cpu" in ln.lower() and "memory" in ln.lower()]
        assert cpu_mem_lines, (
            "No CPU / memory row found in process-isolation.md Known Limitations table."
        )
        for line in cpu_mem_lines:
            assert "Not enforced" not in line, (
                f"CPU / memory limits row still says 'Not enforced': {line!r}. "
                "Green must update this to 'Container-level' enforcement."
            )

    def test_cpu_memory_limits_row_mentions_container_level(self):
        """CPU / memory row must mention 'Container-level' enforcement."""
        md = _read_process_isolation_md()
        lines = md.splitlines()
        cpu_mem_lines = [ln for ln in lines if "cpu" in ln.lower() and "memory" in ln.lower()]
        assert cpu_mem_lines, (
            "No CPU / memory row found in process-isolation.md Known Limitations table."
        )
        found = any("container" in ln.lower() for ln in cpu_mem_lines)
        assert found, (
            f"CPU / memory row does not mention 'Container-level': {cpu_mem_lines}. "
            "Green must update the row to reflect container-level enforcement."
        )
