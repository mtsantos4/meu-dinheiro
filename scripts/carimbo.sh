#!/bin/sh
# Marca a versão do app (usado antes de cada commit)
V=$(date -u +%Y%m%d%H%M%S)
sed -i "s/const APP_BUILD = '[^']*';/const APP_BUILD = '$V';/" index.html
printf '%s\n' "$V" > version.txt
git add index.html version.txt
