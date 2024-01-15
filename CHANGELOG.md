## 0.3.2 (2024-01-15)

### Fix

- read revision from bump job env

## 0.3.1 (2024-01-15)

### Fix

- pin python interpreter standalone in lift library to 3.11.7

## 0.3.0 (2024-01-15)

### Feat

- release action

## 0.2.0 (2024-01-15)

### Feat

- release action

### Fix

- release action
- release action

## 0.1.7 (2024-01-15)

### Fix

- integrate commitizen into build github actions

## 0.1.6 (2023-12-13)

### Fix

- add workflow permission to write releases

## 0.1.5 (2023-12-13)

### Fix

- github releases requires a tag
- fixing file path for release step
- show files in folder after installer build

## 0.1.4 (2023-12-13)

### Fix

- fix log path
- show logs from current user home directory
- show postinstall logs
- trigger build
- fixing download path
- tmp show catalog structure
- fixing paths
- job deps
- one workflow, two jobs
- upload binary as artifact to share it between workflows
- cache pikesquares binary between jobs, place it into binary folder and upload installer pkg as artifact
- checkout pikesquares mib from github repo
- update workflows, setup act
- two specific platform:arch mappings
- fix binary name in cdn post query
- science conflicts with all env vars prefixed with SCIENCE_
- absolute path to science
- another fix in science url
- different steps for different oses
- typo
- fixing science download url
- trying absoulte path
- download science in step when running it
- working build binary script steps
- rename copypasted job names
- use python versions 3.11 and 3.12 only, remove paid platform tags
- trigger workflow on push to master branch or pushing any tag
- add self-hosted runner (macos-latest-arm64) to workflows
- adding github workflows for build binary, macos pkg installer and publishing binary cdn
- create config dirs on app start (in case if app installed by pip or another non-installer method)
- show warning if user attempts to start/stop app or project even he doesn't create one
- update gitignore

## 0.1.1 (2023-12-07)

### Fix

- rm unneded settings from conf

## 0.1.0 (2023-12-06)

### Feat

- test versioning
