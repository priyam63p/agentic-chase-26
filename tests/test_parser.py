import pytest
from processing.parser import LogParser
from processing.templates import TemplateMiner

def test_parse_txt():
    txt_data = """
2026-11-07 10:00:00 [db-primary] [ERROR] Connection pool exhausted: 500 connections active
2026-11-07 10:00:05 [orders-api] [ERROR] Upstream db-primary timed out after 30s
"""
    entries = LogParser.parse_content(txt_data, file_type="txt")
    assert len(entries) == 2
    assert entries[0].line_id == "L-0001"
    assert entries[0].service == "db-primary"
    assert entries[0].level == "ERROR"
    assert entries[1].line_id == "L-0002"
    assert entries[1].service == "orders-api"

def test_parse_json():
    json_data = """[
      {"timestamp": "2026-11-07 10:00:00", "service": "worker-1", "level": "INFO", "message": "Starting batch"},
      {"timestamp": "2026-11-07 10:00:10", "service": "worker-1", "level": "ERROR", "message": "OOM killed"}
    ]"""
    entries = LogParser.parse_content(json_data, file_type="json")
    assert len(entries) == 2
    assert entries[0].line_id == "L-0001"
    assert entries[1].line_id == "L-0002"
    assert entries[1].level == "ERROR"

def test_parse_csv():
    csv_data = """timestamp,service,level,message
2026-11-07 10:00:00,checkout,INFO,User began checkout
2026-11-07 10:00:05,checkout,ERROR,Failed to charge card
"""
    entries = LogParser.parse_content(csv_data, file_type="csv")
    assert len(entries) == 2
    assert entries[0].line_id == "L-0001"
    assert entries[1].line_id == "L-0002"
    assert "charge card" in entries[1].message

def test_template_miner():
    txt_data = """
2026-11-07 10:00:00 [service-a] [ERROR] Connection to 10.0.0.5 failed after 30s
2026-11-07 10:00:02 [service-a] [ERROR] Connection to 10.0.0.9 failed after 45s
2026-11-07 10:00:04 [service-a] [ERROR] Connection to 192.168.1.1 failed after 10s
"""
    entries = LogParser.parse_content(txt_data, file_type="txt")
    templates = TemplateMiner.mine(entries)
    assert len(templates) >= 1
    # Check that IPs and numbers were masked into pattern
    top_pat = templates[0].pattern
    assert "<IP>" in top_pat
    assert templates[0].count == 3
