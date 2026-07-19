#!/bin/bash
set -e

echo "Removing old Hexo files..."
find . -mindepth 1 -maxdepth 1 ! -name 'hugo-site' ! -name '.git' -exec rm -rf {} +

echo "Copying new Hugo site into place..."
cp -r hugo-site/. .

echo "Adding PaperMod theme as submodule..."
git submodule add https://github.com/adityatelange/hugo-PaperMod.git themes/PaperMod || true

echo "Committing and pushing..."
git add -A
git commit -m "Migrate blog from Hexo to Hugo"
git push origin master

rm -rf hugo-site hugo-site.zip

echo ""
echo "Done! Now go to repo Settings -> Pages -> Source -> select 'GitHub Actions'."
