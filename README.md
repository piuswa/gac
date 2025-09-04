# SSH-based Access Control for Git using Git

This software was developed for a bachelors thesis at the University of Basel. The completed thesis can be found in [this repository](/SSH-based%20Access%20Control%20for%20Git%20using%20Git.pdf) and and the [Website of the Computer Networks](https://cn.dmi.unibas.ch/en/projects/) group of the University of Basel under "Completed Bachelor Projects"

## Introduction

Administrating a Git repository can present a certain workload. We present a way to manage
a repository using commits to control access. A user can express his trust to an other user.
This creates a trust graph which is the base for calculating who can access the repository
on which way. The owner of a repository can grant read and write access while users with
this access can grant read access to other users. This is done in a secure way by using self-
certification. Incoming commits are processed by a Git hook and saved in the trust graph.
It then translates this trust graph into access privileges. These privileges are enforced by
restricting the SSH access of users to certain actions.

## Deployment
This section describes how to use the code that was developed in this thesis to host a Git repository with access control. It will provide two different ways to run it. One  which allows a developer to easily make modifications on his development machine, which we call the _host machine_ and one in a Docker container to simplify deployments on remote servers.

### Deploying the Code on the Host Machine
Deploying the code on the host machine itself is the simplest way to use it. One needs to have a non bare initialized Git repository and just needs to copy the `gac.sh` file into the root folder of the repository. Then one needs to run it with the following command, replacing `<ed25519-pub-key>` with the ED25519 public key that one wants to be the owner of the repository:
```
./gac.sh \<ed25519-pub-key>
```
Make sure that this public key is also in the authorized keys file with full SSH access to the server. This can simply be done by adding the following line to your `authorized\_keys` file:
```
ssh-ed25519 <ed25519-pub-key> <optional-identifier>
```
The identifier is completely optional and can just be removed.

### Deploying the Code in Docker
Deploying the code in Docker is a clean and simple solution to host a repository but provides a a few challenges. Since the code is not being run on the host machine itself but in a container there still needs to be a way to access the host machine.

One can not expose port 22 of the container to the outside since this port is needed to access the host machine. It is also not possible for the host machine to tell which hostname was used to access it since there is no protocol extension like Server Name Identification (SNI) in HTTPS for SSH. Otherwise it would be possible to tell by the hostname that was used if a user wanted to access the container running the Git repository or if he wanted to use SSH to access the host machine. This is a problem because it would be the cleanest solution to access the repository. We can get around this by exposing a different port to the outside and then mapping this port to port 22 on the container. This setup keeps the host machine accessible and allows access to the Git repository inside the container. However, since the SSH port is non-standard, the port must be explicitly specified when accessing the repository.

If one wants to run the container Docker must be installed and one needs to edit the last line in the Dockerfile to use the ED25519 public key that should be the owner of the repository. Currently it contains an example key. It should look like this:
```
ENTRYPOINT ["/entrypoint.sh", "<your-key>"]
```
The example Dockerfile that is included maps port 22 of the container to port 2222 of the host machine. One can build the docker image by executing the following command in the directory that contains the `Dockerfile`, `docker-compose.yml`, `gac.sh` and `entrypoint.sh` files:
```
docker-compose build
```
One can then run the container in the background by executing the following command in the same directory:
```
docker-compose up -d
```
To stop the container one can execute the following command in the same directory:
```
docker-compose down
```
If one wants to run multiple containers one can do so by exposing a different port for each container. This would only require changing the port mapping in the `docker-compose.yml` file. In the example `docker-compose.yml` port 22 on the container is mapped to port 2222 on the the host machine. One can change this to any port that is not already in use. One will also need to change the names of the volumes in the `docker-compose.yml` file to something that is unique for each container. Otherwise the container will just contain the same data as the other container.

## Using the software

### Accessing the Repository
To access the repository one can use the following command, replacing the placeholders as needed:
```
git clone ssh://<user>@<host>:<port><path-to-repository>.git
```
If one is running the code in Docker with the example Dockerfile the command will look like this and one only needs to replace `<host>` with the hostname or IP address of the host machine:
```
git clone ssh://git@<host>:2222/home/git/repo/.git
```
This command will clone the repository to the machine it is being executed on. To start using the access control system one needs to set it up first. This can be done by executing a single command in the root directory of the repository right after cloning it. This command will setup the access control system on the local machine. One will need to provide the path to one's own ED25519 public key. This key must be the same that was used to create the repository on the host machine if one is the owner of the repository. Otherwise it can just be the ED25519 public key that one wants to use with this system. The command is as follows:
```
./gac.py create_repo <path-to-your-ed25519-public-key>
```
Depending on how the host machine is usually accessed one might need to setup the SSH config file to use the correct key. This can be done by adding the following lines to the `~/.ssh/config` file and replacing the placeholders with the correct values:
```
Host <hostname>
    HostName <hostname>
    Port <port>
    User <user-on-server>
    IdentityFile <path-to-your-ed25519-public-key>
    IdentitiesOnly yes
```
The hostname is the hostname or IP address of the host machine. If the software is running in Docker with the example Dockerfile the port is 2222. If one is running the software on the host machine the port is 22. The user is the user on the server which is hosting the repository. If one is hosting the repository on Docker it is `Git`. The path to ones ED25519 public key is the path to the public key that one wants to use with the access control software. This setup will allow one to access the repository without having to specify the key every t

### Adding and removing trust

Adding or removing trust in this software is encoded in Git commits. Each user has their own branch on which they make commits that either encode adding or removing trust. We will call these their _personal access control_ branches. Each branch's name follows the structure `<root-hash>_<base-32-encoded-pub-key-of-user>`.

The root hash is the Git hash of a signed Git commit that contains all software needed to run the access control software and we will refer to it as the _root commit_. This allows us to identify which version of the software is being used and if this branch even belongs to this access control software.

The base 32 encoded pubkey allows us to tell exactly to whom this branch belongs to. It is base 32 encoded to avoid any characters that could be be invalid or be interpreted by Git or the operating system as a path separator, such as a backslash. 

A user of the system can simply interact with the system by interacting with the `gac.py` script that will be on their personal access control branch as well as on the branch called `<root-hash>_gac` which is the branch that contains all software used for the access control. If a user wants to add trust for a person he can do so simply by executing the following command:
```
./gac.py add_trust <trustee-pub-key>
```
If a user wants to remove trust for a person he can do so by executing the following command:
```
./gac.py remove_trust <trustee-pub-key>
```
After such an operation the user needs to push his access control branch to the server to update the trust relationships.