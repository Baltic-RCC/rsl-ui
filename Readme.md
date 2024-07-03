Docker image for QoCDC Standalone Validation Tool
===
![requirements-screenshot](https://i.pinimg.com/originals/f5/5e/80/f55e8059ea945abfd6804b887dd4a0af.gif
)


## 0.Quick Guide
1. Install Docker - [Get Docker](https://docs.docker.com/get-docker/)
2. Run Docker
3. Download SUV for docker and extract to place of your choosing - [Dockerized SUV](https://entsoe.sharefile.com/home/shared/fo60a51b-b147-4b51-8e62-a2b29f33e998)
4. Run install.bat for windows or install.sh for linux and mac
5. Place your files in input folder (replace the Svedala model, but keep the boundary files)
6. Run validate.bat for windows or validate.sh for linux nad mac

## 1.Introduction


This repository contains Dockerized environment for the QoCDC Standalone Valtion Tool.
We aim to  publish it to the private [Docker Hub](https://hub.docker.com/) via **automated build** mechanism.

### 2. Document Structure
Section 0: Quick Guide

Section 1: Introduces this document

Section 2: Explains the Requirements for host environment

Section 3: Describes the Configuration

Section 4: Details the usage

Section 5: How to run the project

Section 6: The VOLUMES directory tree

Section 7: how to Execute commands inside the container

Section 8: License

### 3.Requirements for host environment

3.1 Install [Docker](https://docs.docker.com).

3.2 Install [Docker-compose ](https://docs.docker.com/compose/install/). 

## 4.Configuration

This docker image contains the following software stack:

- Base image: Centos:8

- [JDK 14](https://download.java.net/java/GA/jdk14/076bab302c7b4508975440c56f6cc26a/36/GPL/openjdk-14_linux-x64_bin.tar.gz): Java Development Kit 14

## 5.Usage
5.1-Place the artifact

You need to place the desired version of the ``` standalone-validation-tool-${Version}.tar.gz```
 in the remote folder .

**The**  `repository`  is as follows:

```
.
└── Docker-repo
    └── remote
        ├── standalone-validation-tool-${Version}.tar.gz
    ├── dockerfile
    ├── docker-compose.yml
    ├── .env
```
5.2-Set the version

You will need to set the version of the standalone-validation-tool in :
    
* [.env file](./.env) - StandaloneValidationTool variable  

 ```    
  StandaloneValidationTool=standalone-validation-tool-${version}
  Example: StandaloneValidationTool=standalone-validation-tool-1.2.175
 ```
 
## 6.Run


Make sure that docker service is up and running:

6.1 Build the image

**When** you want to build the program :

```
$ docker-compose build
```

**Then** you can see the output as follows:

```
.
.
 => CACHED [19/19] RUN tar xvzf /home/tmp/standalone-validation-tool-1.2.  0.0s
 => exporting to image                                                     0.1s
 => => exporting layers                                                    0.0s
 => => writing image sha256:e1002496366653a0bcc8bf150cfc20cb3b917c9811fac  0.0s
 => => naming to docker.io/library/qocdc:v1.5                              0.0s
Successfully built e1002496366653a0bcc8bf150cfc20cb3b917c9811facd8a944d9a4e83df5f0a

```
6.2 Run the container

**When** you want to run the container :

```
$ docker-compose up -d
```

**Then** you can see the output as follows:

```
Recreating dockerizedtests_QoCDC_1 ... done
```
### 7.VOLUMES

**After running the container**  `directory `  is as follows:

```
.
└── Docker-repo
    ├── input
    ├── output
    ├── rule-set-library
    └── remote
        ├── standalone-validation-tool-${Version}.tar.gz
    ├── dockerfile
    ├── docker-compose.yml
    ├── .env
```
The folders **input** ,**output** & **rule-set-library** are mapped with the folders in the workspace of the standalone validation tool.
Therefore any uploaded file in these folders will be copied in the according directory of the container and versi-versa.

For more infos about docker-volumes check:
https://docs.docker.com/storage/volumes/

## 8.Execute commands
To run any command inside the container you should **either** :


8.1 Execute command through the cli 
```
docker exec -it <container_id_or_name> "COMMAND"
Example: docker exec -it dockerizedtests_QoCDC_1  sh validate.sh -vg file

```
In order to get the container name/id, you should type the following cammand
```
$ docker ps
CONTAINER ID   IMAGE        COMMAND            CREATED          STATUS          PORTS     NAMES
666d065d188b   qocdc:v1.5   "/usr/sbin/init"   17 minutes ago   Up 17 minutes             dockerizedtests_QoCDC_1
```
which will list all the running containers.

8.2 Run the container from the Docker-desktop 

Check the following links:

"https://docs.docker.com/engine"

"https://docs.docker.com/docker-for-windows/"

## 9.License

Author: QoCDC Team

