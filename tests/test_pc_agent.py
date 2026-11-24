import os, sys
sys.path.insert(0, r"C:\XiaoZhi-PC")
import pc_agent

def test_secret_redaction():
    os.environ["HA_TOKEN"] = "secret_token_999888777"
    masked = pc_agent._redact_secrets("Connecting with token secret_token_999888777 now")
    assert "secret_token_999888777" not in masked
    assert "[СКРЫТО]" in masked

def test_security_blocks_env():
    res = pc_agent.run_safe_powershell("Get-Content .env")
    assert ".env" in res and "LLM_API_KEY" not in res

def test_modes_switching():
    for m in ["combat", "companion", "entertainment"]:
        res = pc_agent.switch_assistant_mode(m)
        assert m in res.lower()
    pc_agent.switch_assistant_mode("companion")

def test_workspace_file_cycle():
    res_w = pc_agent.write_workspace_file("_pytest_tmp.txt", "hello johnny")
    assert "_pytest_tmp.txt" in res_w
    tmp_p = os.path.join(pc_agent.WORKSPACE_DIR, "_pytest_tmp.txt")
    assert os.path.exists(tmp_p)
    os.remove(tmp_p)