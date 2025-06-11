#!/usr/bin/env python3

import base64
import os
import subprocess
import sys
import yaml

root_commit_reference = ""

def encode_pubkey_base32(pubkey_str):
    pubkey_bytes = pubkey_str.encode()
    return base64.b32encode(pubkey_bytes).decode().rstrip("=")

def get_ssh_key(path):
    with open(path, "r") as file:
        return file.read().strip().split(" ")[1]

def save_yaml(data, path):
    with open(path, "w") as file:
        yaml.dump(data, file)

def write_allowed_signers(pub_key):
    allowed_signers_file = "./.git/allowed_signers"
    with open(allowed_signers_file, "w") as file:
        file.write("* ssh-ed25519 " + pub_key)

def load_info():
    yaml_file = "./.git/info.yaml"
    try:
        with open(yaml_file, "r") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print("No yaml file found! Exiting...")
        exit(1)

def get_parant(branch):
    try:
        with open(f"./.git/refs/heads/{branch}", "r") as file:
            return file.read().strip()
    except FileNotFoundError:
        print("No parent found! Exiting...")
        exit(1)

def write_new_commit(commit, branch):
    with open(f"./.git/refs/heads/{branch}", "w") as file:
        file.write(commit)

def trust_operation(trustee_pub_key, tg_operation):
    info = load_info()
    branch = f'{root_commit_reference}_{info["pub_key_encoded"]}'
    parent = get_parant(branch)
    env_trustee = dict(os.environ)
    env_trustee["GIT_COMMITTER_NAME"] = trustee_pub_key
    env_trustee["GIT_COMMITTER_EMAIL"] = info["pub_key_encoded"]
    commit_tree_command = ["git", "commit-tree", info["tree"][:5], "-m", tg_operation, "-p", parent, "-S"]
    result = subprocess.run(commit_tree_command, env=env_trustee, capture_output=True, text=True)
    new_commit = result.stdout.strip()
    write_new_commit(new_commit, branch)

def create_repo(pub_key_path):
    key = get_ssh_key(pub_key_path)
    key_encoded = encode_pubkey_base32(key)
    branch = f'{root_commit_reference}_{key_encoded}'
    subprocess.run(["git", "checkout", "-b", branch])
    write_new_commit(root_commit_reference, branch)
    empty_tree = subprocess.run(["git", "write-tree"], capture_output=True, text=True).stdout.strip()
    info = {"tree": empty_tree, "pub_key_path": pub_key_path, "pub_key_encoded": key_encoded}
    save_yaml(info, "./.git/info.yaml")
    subprocess.run(["git", "config", "commit.gpgsign", "true"])
    subprocess.run(["git", "config", "gpg.format", "ssh"])
    subprocess.run(["git", "config", "user.signingkey", pub_key_path])
    write_allowed_signers(key)
    wd = subprocess.run(["pwd"], capture_output=True, text=True).stdout.strip()
    subprocess.run(["git", "config", "gpg.ssh.allowedSignersFile", f"{wd}/.git/allowed_signers"])
    subprocess.run(["git", "add", "."])
    env = dict(os.environ)
    env["GIT_COMMITTER_EMAIL"] = key_encoded
    subprocess.run(["git", "commit", "-m", "created repo"], env=env)

def create_server(owner_pub_key):
    wd = subprocess.run(["pwd"], capture_output=True, text=True).stdout.strip()
    subprocess.run(["git", "config", "gpg.ssh.allowedSignersFile", f"{wd}/.git/allowed_signers"])
    write_allowed_signers(owner_pub_key)
    save_yaml({"owner": owner_pub_key, "trustgraph": []}, "./.git/git_hook.yaml")
    subprocess.run(["mv", "./pre-receive.py", "./.git/hooks/pre-receive"])
    with open("./git-pull.sh", "r") as file:
        git_pull = file.readlines()
    git_pull[2] = f'echo "$SSH_ORIGINAL_COMMAND" >> {wd}/.git/ssh.log\n'
    git_pull[4] = f"pullpatt=\"git-upload-pack '{wd}/.git'$\"\n"
    with open("./git-push-pull.sh", "r") as file:
        git_push_pull = file.readlines()
    git_push_pull[2] = f'echo "$SSH_ORIGINAL_COMMAND" >> {wd}/.git/ssh.log\n'
    git_push_pull[4] = f"pullpatt=\"git-upload-pack '{wd}/.git'$\"\n"
    git_push_pull[6] = f"pushpatt=\"git-receive-pack '{wd}/.git'$\"\n"
    with open("./git-pull.sh", "w") as file:
        file.writelines(git_pull)
    with open("./git-push-pull.sh", "w") as file:
        file.writelines(git_push_pull)
    subprocess.run(["mv", "./git-pull.sh", "./.git/git-pull.sh"])
    subprocess.run(["mv", "./git-push-pull.sh", "./.git/git-push-pull.sh"])
    subprocess.run(["touch", "./.git/ssh.log"])
    branch = f'{root_commit_reference}_gac'
    subprocess.run(["git", "checkout", "-b", branch])
    subprocess.run(["git", "add", "git-pull.sh"])
    subprocess.run(["git", "add", "git-push-pull.sh"])
    subprocess.run(["git", "add", "pre-receive.py"])
    subprocess.run(["git", "add", "gac.py"])
    write_new_commit(root_commit_reference, branch)
    subprocess.run(["git", "commit", "-m", "Git Access Control"])

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: gac.py <operation> [trustee|pub_key_path|owner_pub_key]")
        exit(1)
    operation = sys.argv[1]
    if operation not in ["add_trust", "remove_trust", "create_repo", "create_server"]:
        print("Invalid operation. Use 'add_trust', 'remove_trust', 'create_server' or 'create_repo'.")
        exit(1)
    in_repo = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True).stdout.strip()
    in_root = os.path.exists("./.git")
    if in_repo != "true" or not in_root:
        print("Not inside a git repository. Please run this script inside the root folder of a git repository.")
        exit(1)
    if operation == "add_trust":
        trustee = sys.argv[2]
        trust_operation(trustee, operation)
    elif operation == "remove_trust":
        trustee = sys.argv[2]
        trust_operation(trustee, operation)
    elif operation == "create_repo":
        key_path = sys.argv[2]
        create_repo(key_path)
    elif operation == "create_server":
        owner_pub_key = sys.argv[2]
        create_server(owner_pub_key)
