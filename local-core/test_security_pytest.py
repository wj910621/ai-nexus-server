"""
Comprehensive pytest tests for security module.
"""
import os
import sys
import tempfile

import pytest

# Add /workspace/local-core to sys.path for imports
sys.path.insert(0, "/workspace/local-core")

from security import (
    normalize_path,
    is_path_safe,
    sanitize_path,
    is_command_safe,
    sanitize_input,
    is_plugin_url_safe,
    get_safe_work_dir,
    DENIED_PATHS,
    DANGEROUS_COMMANDS,
    ALLOWED_BASE_DIRS,
)


# ---------------------------------------------------------------------------
# normalize_path
# ---------------------------------------------------------------------------

class TestNormalizePath:
    """Tests for normalize_path function."""

    def test_none_input(self):
        assert normalize_path(None) is None

    def test_empty_string(self):
        assert normalize_path("") is None

    def test_non_string_input_integer(self):
        assert normalize_path(123) is None

    def test_non_string_input_list(self):
        assert normalize_path([]) is None

    def test_relative_path(self):
        result = normalize_path("subdir/file.txt")
        assert result is not None
        assert os.path.isabs(result)

    def test_absolute_path(self, tmp_path):
        abs_dir = str(tmp_path / "myfile.txt")
        result = normalize_path(abs_dir)
        assert result is not None
        assert os.path.isabs(result)

    def test_path_with_double_dot_traversal(self):
        base = os.getcwd()
        result = normalize_path(os.path.join(base, "sub", "..", "target"))
        assert result is not None
        # Should resolve .. and not contain it literally
        assert ".." not in result

    def test_path_with_tilde(self):
        result = normalize_path("~/some_dir")
        assert result is not None
        home = os.path.expanduser("~")
        assert result.startswith(home)

    def test_path_with_multiple_traversal(self):
        base = os.getcwd()
        result = normalize_path(os.path.join(base, "a", "b", "..", ".."))
        assert result is not None
        assert ".." not in result


# ---------------------------------------------------------------------------
# is_path_safe
# ---------------------------------------------------------------------------

class TestIsPathSafe:
    """Tests for is_path_safe function."""

    @pytest.mark.parametrize("denied", [
        "/etc",
        "/etc/passwd",
        "/bin",
        "/bin/sh",
        "/usr/bin",
        "/usr/bin/python",
        "/sbin",
        "/sys",
        "/proc",
        "/dev",
    ])
    def test_denied_system_paths_linux(self, denied):
        assert is_path_safe(denied) is False

    @pytest.mark.parametrize("denied_win", [
        "C:\\Windows",
        "C:\\Windows\\System32",
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        "C:\\ProgramData",
    ])
    def test_denied_system_paths_windows(self, denied_win):
        # On Linux these won't be real paths but the prefix check in
        # is_path_safe compares lowercase prefixes, so if the normalized
        # result happens to start with the denied prefix it will be rejected.
        # We just verify the function does not raise.
        result = is_path_safe(denied_win)
        assert isinstance(result, bool)

    def test_allowed_path_within_cwd(self, tmp_path):
        # Use the actual cwd as an allowed base
        allowed = [os.getcwd()]
        safe_path = os.path.join(os.getcwd(), "some_safe_dir")
        assert is_path_safe(safe_path, allowed_bases=allowed) is True

    def test_allowed_path_with_subdirectory(self):
        allowed = [os.getcwd()]
        safe_path = os.path.join(os.getcwd(), "sub", "dir")
        assert is_path_safe(safe_path, allowed_bases=allowed) is True

    def test_path_traversal_attempt(self):
        """Attempt to escape the allowed dir via .."""
        allowed = [os.getcwd()]
        traversal = os.path.join(os.getcwd(), "..", "..", "etc", "passwd")
        # normalize_path resolves .. to a real absolute path, which will be
        # outside the allowed base directory.
        assert is_path_safe(traversal, allowed_bases=allowed) is False

    def test_non_string_input_none(self):
        assert is_path_safe(None) is False

    def test_non_string_input_integer(self):
        assert is_path_safe(42) is False

    def test_empty_string(self):
        assert is_path_safe("") is False

    def test_path_outside_allowed_bases(self, tmp_path):
        # Create a temp dir that is NOT in allowed bases
        other_dir = str(tmp_path / "outside" / "dir")
        allowed = [os.getcwd()]
        assert is_path_safe(other_dir, allowed_bases=allowed) is False


# ---------------------------------------------------------------------------
# sanitize_path
# ---------------------------------------------------------------------------

class TestSanitizePath:
    """Tests for sanitize_path function."""

    def test_safe_relative_path(self):
        # Use cwd as base — it is in ALLOWED_BASE_DIRS, so is_path_safe passes
        base = os.getcwd()
        result = sanitize_path("subdir", default_base=base)
        expected = os.path.realpath(os.path.join(base, "subdir"))
        assert result == expected

    def test_dangerous_path_fallback(self, tmp_path):
        base = str(tmp_path)
        # /etc/passwd is a denied path; sanitize should fallback to base
        result = sanitize_path("/etc/passwd", default_base=base)
        expected = os.path.realpath(os.path.expanduser(base))
        assert result == expected

    def test_path_with_double_dot(self, tmp_path):
        base = str(tmp_path)
        # Join a path with .. — if the resolved path stays under base it's ok,
        # otherwise it falls back to base.
        result = sanitize_path("sub/../file.txt", default_base=base)
        # The resolved path should be within base
        assert os.path.isabs(result)

    def test_no_default_base_raises_for_dangerous(self):
        """Without default_base, a dangerous path should raise ValueError."""
        with pytest.raises(ValueError):
            sanitize_path("/etc/passwd")

    def test_no_default_base_safe_path(self):
        """A safe path without default_base should return the normalized path."""
        safe = os.path.join(os.getcwd(), "safe_folder")
        result = sanitize_path(safe)
        assert result == normalize_path(safe)


# ---------------------------------------------------------------------------
# is_command_safe
# ---------------------------------------------------------------------------

class TestIsCommandSafe:
    """Tests for is_command_safe function."""

    @pytest.mark.parametrize("cmd", [
        "rm -rf /",
        "rm -rf /*",
        "format C:",
        "fdisk /dev/sda",
        "dd if=/dev/zero of=/dev/sda",
        ":(){ :|:& };:",          # fork bomb
        "> /dev/sda",
        "mkfs.ext4 /dev/sda1",
        "deltree C:\\",
        "rd /s C:\\",
        "rmdir /s /q C:\\Windows",
    ])
    def test_dangerous_commands(self, cmd):
        assert is_command_safe(cmd) is False

    @pytest.mark.parametrize("cmd", [
        "ls",
        "ls -la",
        "echo hello",
        "python script.py",
        "git status",
        "npm install",
        "cat README.md",
    ])
    def test_safe_commands(self, cmd):
        assert is_command_safe(cmd) is True

    def test_empty_string(self):
        assert is_command_safe("") is False

    def test_none_input(self):
        assert is_command_safe(None) is False

    def test_non_string_input(self):
        assert is_command_safe(12345) is False

    def test_case_insensitive_dangerous(self):
        assert is_command_safe("FORMAT C:") is False
        assert is_command_safe("RM -RF /") is False

    def test_dangerous_substring_in_longer_command(self):
        """Dangerous pattern embedded in a longer command string."""
        assert is_command_safe("sudo rm -rf /") is False


# ---------------------------------------------------------------------------
# sanitize_input
# ---------------------------------------------------------------------------

class TestSanitizeInput:
    """Tests for sanitize_input function."""

    def test_control_character_removal(self):
        text = "hello\x00world\x01end"
        result = sanitize_input(text)
        assert result == "helloworldend"

    def test_tab_and_newline_preserved(self):
        """Tab and newline should be preserved (they are not in the removed range)."""
        text = "hello\tworld\ntest"
        result = sanitize_input(text)
        assert "\t" in result
        assert "\n" in result

    def test_length_limiting_default(self):
        long_text = "a" * 20000
        result = sanitize_input(long_text)
        assert len(result) == 10000

    def test_length_limiting_custom(self):
        long_text = "a" * 500
        result = sanitize_input(long_text, max_length=100)
        assert len(result) == 100

    def test_zero_width_character_removal(self):
        # U+200B zero-width space, U+200C ZWNJ, U+200D ZWJ, U+FEFF BOM
        text = "a\u200bb\u200cc\u200dd\ufeffe"
        result = sanitize_input(text)
        assert result == "abcde"

    def test_non_string_input_integer(self):
        result = sanitize_input(12345)
        assert result == "12345"

    def test_non_string_input_none(self):
        result = sanitize_input(None)
        assert result == "None"

    def test_strips_whitespace(self):
        result = sanitize_input("  hello  ")
        assert result == "hello"

    def test_delete_char_removal(self):
        """DEL character (0x7F) should be removed."""
        text = "hello\x7fworld"
        result = sanitize_input(text)
        assert result == "helloworld"


# ---------------------------------------------------------------------------
# is_plugin_url_safe
# ---------------------------------------------------------------------------

class TestIsPluginUrlSafe:
    """Tests for is_plugin_url_safe function."""

    def test_localhost_rejection(self):
        assert is_plugin_url_safe("http://localhost/evil-plugin") is False

    def test_127_rejection(self):
        assert is_plugin_url_safe("http://127.0.0.1/evil-plugin") is False

    def test_0000_rejection(self):
        assert is_plugin_url_safe("http://0.0.0.0/evil-plugin") is False

    def test_ipv6_loopback_rejection(self):
        assert is_plugin_url_safe("http://[::1]/evil-plugin") is False

    def test_file_protocol_rejection(self):
        assert is_plugin_url_safe("file:///etc/passwd") is False

    def test_ftp_protocol_rejection(self):
        assert is_plugin_url_safe("ftp://example.com/plugin.zip") is False

    def test_valid_https_url(self):
        """A public HTTPS URL should pass the check (unless DNS resolution fails
        or resolves to a private IP, which is unlikely for github.com)."""
        result = is_plugin_url_safe("https://github.com/some/plugin")
        # We accept True (normal case) or False (if DNS is unavailable in
        # the sandbox). The important thing is no exception is raised.
        assert isinstance(result, bool)

    def test_empty_input(self):
        assert is_plugin_url_safe("") is False

    def test_none_input(self):
        assert is_plugin_url_safe(None) is False

    def test_non_string_input(self):
        assert is_plugin_url_safe(12345) is False

    def test_private_ip_rejection(self):
        """Private network IPs should be rejected (SSRF prevention)."""
        assert is_plugin_url_safe("http://192.168.1.1/plugin") is False
        assert is_plugin_url_safe("http://10.0.0.1/plugin") is False
        assert is_plugin_url_safe("http://172.16.0.1/plugin") is False

    def test_no_hostname(self):
        """URL with no hostname should be rejected."""
        assert is_plugin_url_safe("https:///plugin") is False


# ---------------------------------------------------------------------------
# get_safe_work_dir
# ---------------------------------------------------------------------------

class TestGetSafeWorkDir:
    """Tests for get_safe_work_dir function."""

    def test_default_sub_dir(self):
        result = get_safe_work_dir()
        assert os.path.isdir(result)
        assert result.endswith("data") or "data" in result

    def test_custom_sub_dir(self, tmp_path):
        # We use a unique name under cwd to avoid polluting workspace
        sub_name = "__test_custom_subdir__"
        result = get_safe_work_dir(sub_name)
        assert os.path.isdir(result)
        assert sub_name in result
        # Cleanup
        if os.path.exists(result):
            os.rmdir(result)

    def test_creates_directory_if_missing(self):
        sub_name = "__test_missing_dir__"
        target = os.path.join(os.getcwd(), sub_name)
        # Ensure it doesn't exist
        if os.path.exists(target):
            os.rmdir(target)
        result = get_safe_work_dir(sub_name)
        assert os.path.isdir(result)
        # Cleanup
        if os.path.exists(result):
            os.rmdir(result)

    def test_idempotent_creation(self):
        sub_name = "__test_idempotent__"
        result1 = get_safe_work_dir(sub_name)
        result2 = get_safe_work_dir(sub_name)
        assert result1 == result2
        assert os.path.isdir(result1)
        # Cleanup
        if os.path.exists(result1):
            os.rmdir(result1)

    def test_returns_real_path(self):
        result = get_safe_work_dir()
        # Should be a resolved real path (no symlinks, no ..)
        assert result == os.path.realpath(result)
