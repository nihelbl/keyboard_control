import subprocess

SSH_TARGET = "sshtest@127.0.0.1"
SSH_PORT = "2222"
TASK_NAME = "AgentClavier"
AGENT_PATH = r"C:\keyboard_control\agent.py"

def run_remote(cmd):
    result = subprocess.run(
        ["ssh", "-p", SSH_PORT, SSH_TARGET, cmd],
        capture_output=True, text=True
    )
    return result.returncode, result.stdout, result.stderr

def ensure_agent_running():
    code, out, _ = run_remote(f"schtasks /query /tn {TASK_NAME}")
    if code != 0:
        create_cmd = (
            f'schtasks /create /tn {TASK_NAME} '
            f'/tr "pythonw.exe {AGENT_PATH}" '
            f'/sc onlogon /rl highest /it /f'
        )
        code, out, err = run_remote(create_cmd)
        if code != 0:
            print(f"[-] Échec création tâche : {err}")
            return False
        print("[+] Tâche planifiée créée sur la VM.")

    code, out, err = run_remote(f"schtasks /run /tn {TASK_NAME}")
    if code != 0:
        print(f"[-] Échec lancement agent : {err}")
        return False
    print("[+] Agent lancé sur la VM.")
    return True

if __name__ == "__main__":
    ensure_agent_running()