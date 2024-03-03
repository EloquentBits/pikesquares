#!/bin/bash
#
#
git tag --list |  xargs -I@ bash -c 'jq --arg T @ --arg C $(git rev-parse @^{commit}) -n "{(\$T): \$C}"' |  jq -s 'add' > ~/dev/eqb/scie-pikesquares/tools/src/scie_pikesquares/pikesquares_release_tags.json
