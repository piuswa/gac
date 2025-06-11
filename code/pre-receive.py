#!/usr/bin/env python3

import base64
import binascii
import os
import sys
import subprocess
import yaml
import hashlib

# global for easy access
root_commit_reference = ""

def decode_pubkey_base32(encoded):
    padding = "=" * (8 - len(encoded) % 8)
    try:
        decoded_bytes = base64.b32decode(encoded + padding)
    except binascii.Error:
        log_message("Invalid base32 encoding. Exiting.")
        log_message("--------------------------------")
        exit(1)
    return decoded_bytes.decode()

def load_current_yaml():
    yaml_file = "./git_hook.yaml"
    try:
        with open(yaml_file, "r") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print("No yaml file found! Exiting...")
        exit(1)

def ssh_key_fingerprint(key_data):
    try:
        key_bytes = base64.b64decode(key_data)
        # compute SHA256 fingerprint
        fingerprint = hashlib.sha256(key_bytes).digest()
        fingerprint_b64 = base64.b64encode(fingerprint).decode()
    except binascii.Error:
        log_message("Invalid base64 encoding. Exiting.")
        log_message("--------------------------------")
        exit(1)

    return f"SHA256:{fingerprint_b64}".strip('=')

def save_allowed_signers(owner, push_pull):
    lines = []
    lines.append(f"* ssh-ed25519 {owner}\n")
    for user in push_pull:
        lines.append(f"* ssh-ed25519 {user}\n")
    allowed_signers_file = "./allowed_signers"
    with open(allowed_signers_file, "w") as file:
        file.writelines(lines)

def edit_auth_keys(push_pull, pull, wd):
    home_path = os.path.expanduser("~")
    auth_keys = home_path + "/.ssh/authorized_keys"
    with open(auth_keys, "r") as file:
        lines = file.readlines()
    # remove all lines of access control scripts
    lines = [line for line in lines if not line.startswith(f'command="{wd}/git-pull.sh"') and not line.startswith(f'command="{wd}/git-push-pull.sh"')]
    # add lines for push/pull and pull users
    for user in push_pull:
        lines.append(f'command="{wd}/git-push-pull.sh",no-agent-forwarding,no-port-forwarding,no-pty,no-user-rc,no-X11-forwarding ssh-ed25519 {user}\n')
    for user in pull:
        lines.append(f'command="{wd}/git-pull.sh",no-agent-forwarding,no-port-forwarding,no-pty,no-user-rc,no-X11-forwarding ssh-ed25519 {user}\n')
    # overwrite all lines in the file
    with open(auth_keys, "w") as file:
        file.writelines(lines)
        
def save_yaml(data):
    yaml_file = "./git_hook.yaml"
    with open(yaml_file, "w") as file:
        yaml.dump(data, file)
        
def parse_data_to_privileges(data):
    owner_pub_key = data.get("owner", "")
    trust_graph = data.get("trustgraph", [])
    if trust_graph is None or len(trust_graph) == 0:
        trust_graph = []
        trust_graph.append({"pub_key": owner_pub_key, "trust": []})
    owner_info = next((person for person in trust_graph if person['pub_key'] == owner_pub_key), None)
    push_pull = owner_info.get("trust", False)
    pull = []
    if push_pull is None:
        push_pull = []
    # add all people trusted by owner to push_pull
    for pub_key in push_pull:
        person_info = next((p for p in trust_graph if p['pub_key'] == pub_key), None)
        if person_info is None:
            continue
        person_trust = person_info.get("trust", None)
        if person_trust is None:
            person_trust = []
        # add all people trusted by this person to pull
        for pull_person in person_trust:
            if pull_person not in pull and pull_person != owner_pub_key and pull_person not in push_pull:
                pull.append(pull_person)
    return owner_pub_key, push_pull, pull

def add_trust(data, pub_key, trustee_pub_key):
    trust_graph = data.get("trustgraph", [])
    if trust_graph is None:
        trust_graph = []
    person = next((p for p in trust_graph if p['pub_key'] == pub_key), None)
    if person is None:
        person = {"pub_key": pub_key, "trust": []}
        trust_graph.append(person)
    if person["trust"] is None:
        person["trust"]=[]
    if trustee_pub_key not in person["trust"]:
        person["trust"].append(trustee_pub_key)
        trust_graph.append({"pub_key": trustee_pub_key, "trust": []})
    data["trustgraph"] = trust_graph

def remove_trust(data, pub_key, trustee_pub_key):
    trust_graph = data.get("trustgraph", [])
    person = next((p for p in trust_graph if p['pub_key'] == pub_key), None)
    if person is not None and trustee_pub_key in person["trust"]:
        person["trust"].remove(trustee_pub_key)
    data["trustgraph"] = trust_graph

def log_message(message):
    log_file = "./git_hook.log"
    with open(log_file, "a") as log:
        log.write(message + "\n")

def main():
    zero_commit = "0000000000000000000000000000000000000000"
    data = load_current_yaml()

    wd = subprocess.run(["pwd"], capture_output=True, text=True).stdout.strip()
    log_message("--------------------------------")
    log_message("Git hook pre-receive started.")
    log_message(f"Working directory: {wd}")
    log_message("--------------------------------")
    
    for line in sys.stdin:
        oldrev, newrev, refname = line.strip().split()
        log_message(f"Received push to branch: {refname}")
        log_message(f"The old revision is: {oldrev}")
        log_message(f"The new revision is: {newrev}")
        log_message("--------------------------------")
        # check if the branch has a self-describing root commit
        root_commit = subprocess.run(["git", "rev-list", "--max-parents=0", f"{newrev}"], capture_output=True, text=True).stdout.strip()
        if not root_commit == root_commit_reference:
            log_message("Self-describing root commit not found. Continuing...")
            log_message("--------------------------------")
            continue
        branch = refname[11:]
        if branch[:40] != root_commit_reference:
            log_message("Branch does not start with root commit. Continuing...")
            log_message("--------------------------------")
            continue
        if branch == f"{root_commit_reference}_gac":
            log_message("Branch is the access control branch to which you may not push. Exiting...")
            log_message("--------------------------------")
            exit(1)
        committer_pub_key = decode_pubkey_base32(branch[41:])
        # check if the branch is being deleted
        if newrev == zero_commit:
            log_message("Branch deletion for access control branch. Not allowed. Exiting.")
            log_message("--------------------------------")
            exit(1)
        # make sure the push is not a force push
        if oldrev != zero_commit:
            fast_forward = subprocess.run(["git", "merge-base", "--is-ancestor", oldrev, newrev], capture_output=True)
            if fast_forward.returncode != 0:
                log_message("Push is a force push. Exiting.")
                log_message("--------------------------------")
                exit(1)
        # check for merges
        merge_commits = subprocess.run(["git", "rev-list", "--min-parents=2", f"{newrev}"], capture_output=True, text=True).stdout.strip().split("\n")
        try:
            merge_commits.remove("")
        except ValueError:
            pass
        if len(merge_commits) > 0:
            log_message("Merge commit found. Exiting.")
            log_message("--------------------------------")
            exit(1)
        # get list of new commits
        commit_list = ""
        if oldrev == zero_commit:
            commit_list = subprocess.run(["git", "rev-list", f"{newrev}"], capture_output=True, text=True)
        else:
            commit_list = subprocess.run(["git", "rev-list", f"{oldrev}..{newrev}"], capture_output=True, text=True)
        commits = commit_list.stdout.strip().split("\n")
        # reverse the list to process commits in order
        commits.reverse()
        for commit in commits:
            if not commit:
                continue
            if commit == root_commit:
                log_message("Self-describing root commit found in processing. Continuing...")
                log_message("--------------------------------")
                continue
            log_message(f"Processing commit: {commit}")
            
            # get commit details
            committer_name = subprocess.run(["git", "show", "-s", "--format=%cn", commit], capture_output=True, text=True).stdout.strip()
            committer_email = subprocess.run(["git", "show", "-s", "--format=%ce", commit], capture_output=True, text=True).stdout.strip()
            commit_message = subprocess.run(["git", "show", "-s", "--format=%s", commit], capture_output=True, text=True).stdout.strip()
            commit_signed = subprocess.run(["git", "show", "-s", "--format=%G?", commit], capture_output=True, text=True).stdout.strip()
            commit_sign_key = ""
            # log commit details
            log_message(f"Committer: {committer_name} ")
            log_message(f"Signed: {commit_signed}")
            log_message(f"Branch: {branch}")
            log_message(f"Message: {commit_message}")
            # check signature
            if commit_signed == "G" or commit_signed == "U":
                commit_sign_key = subprocess.run(["git", "show", "-s", "--format=%GK", commit], capture_output=True, text=True).stdout.strip()
                log_message(f"Sign Key: {commit_sign_key}")
            else:
                log_message("--------------------------------")
                log_message("Commit not signed. Exiting")
                exit(1)
            log_message("--------------------------------")
            if ssh_key_fingerprint(committer_pub_key) != commit_sign_key or ssh_key_fingerprint(decode_pubkey_base32(committer_email)) != commit_sign_key:
                log_message("Committer public key does not match the signed key. Exiting")
                exit(1)
            # execute trust operation
            if commit_message == "add_trust":
                add_trust(data, committer_pub_key, committer_name)
            elif commit_message == "remove_trust":
                remove_trust(data, committer_pub_key, committer_name)

    owner, push_pull, pull = parse_data_to_privileges(data)
    save_yaml(data)
    save_allowed_signers(owner, push_pull)
    log_message(f"Owner: {owner}")
    log_message(f"Push/Pull: {push_pull}")
    log_message(f"Pull: {pull}")
    log_message("--------------------------------")
    edit_auth_keys(push_pull, pull, wd)
    log_message("Edited authorized_keys file.")
    log_message("--------------------------------")
    log_message("Git hook pre-receive finished.")
    sys.exit(0)

if __name__ == "__main__":
    main()
