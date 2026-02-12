"""Tests for mojomark machine fingerprint."""

from mojomark.machine import format_machine_summary, get_machine_info, machines_match


class TestGetMachineInfo:
    def test_returns_all_expected_keys(self):
        info = get_machine_info()
        assert "cpu" in info
        assert "cores" in info
        assert "ram_gb" in info
        assert "os" in info
        assert "arch" in info
        assert "hostname_hash" in info

    def test_cores_is_positive(self):
        info = get_machine_info()
        assert info["cores"] > 0

    def test_ram_is_positive(self):
        info = get_machine_info()
        assert info["ram_gb"] > 0

    def test_hostname_hash_is_stable(self):
        a = get_machine_info()
        b = get_machine_info()
        assert a["hostname_hash"] == b["hostname_hash"]

    def test_hostname_hash_is_short_hex(self):
        info = get_machine_info()
        assert len(info["hostname_hash"]) == 12
        int(info["hostname_hash"], 16)  # should not raise


class TestFormatMachineSummary:
    def test_contains_key_info(self):
        info = get_machine_info()
        summary = format_machine_summary(info)
        assert str(info["cores"]) in summary
        assert "RAM" in summary
        assert info["arch"] in summary


class TestMachinesMatch:
    def test_same_machine_matches(self):
        info = get_machine_info()
        assert machines_match(info, info) is True

    def test_different_hostname_hash(self):
        a = {"hostname_hash": "aaa", "cpu": "M2", "cores": 10}
        b = {"hostname_hash": "bbb", "cpu": "M2", "cores": 10}
        assert machines_match(a, b) is False

    def test_different_cpu(self):
        a = {"hostname_hash": "aaa", "cpu": "M2", "cores": 10}
        b = {"hostname_hash": "aaa", "cpu": "i9", "cores": 10}
        assert machines_match(a, b) is False

    def test_ram_difference_still_matches(self):
        a = {"hostname_hash": "aaa", "cpu": "M2", "cores": 10, "ram_gb": 16}
        b = {"hostname_hash": "aaa", "cpu": "M2", "cores": 10, "ram_gb": 32}
        assert machines_match(a, b) is True

    def test_missing_keys_handled(self):
        assert machines_match({}, {}) is True
