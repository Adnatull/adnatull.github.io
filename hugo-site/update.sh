#!/bin/bash
set -e

echo "Copying updated files into place (theme/git history untouched)..."
cp -r hugo-site/. .

echo "Committing and pushing..."
git add -A
git commit -m "Fix: images not rendering (remove <center>-wrapped markdown images)"
git push origin master

rm -rf hugo-site hugo-site.zip update.sh deploy.sh

echo "Done!"
