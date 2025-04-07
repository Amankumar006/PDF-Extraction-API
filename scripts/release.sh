#!/bin/bash

# Check if version argument is provided
if [ -z "$1" ]; then
    echo "Usage: ./release.sh <version>"
    echo "Example: ./release.sh 1.0.0"
    exit 1
fi

VERSION=$1
TAG="v$VERSION"

# Update VERSION file
echo $VERSION > VERSION

# Commit version update
git add VERSION
git commit -m "Bump version to $VERSION"

# Create and push tag
git tag -a $TAG -m "Release version $VERSION"
git push origin $TAG

# Create release notes template
cat > release_notes.md << EOF
## [$VERSION] - $(date +%Y-%m-%d)

### Added
- 

### Changed
- 

### Deprecated
- 

### Removed
- 

### Fixed
- 

### Security
- 
EOF

echo "Release $VERSION prepared!"
echo "1. Review and update release_notes.md"
echo "2. Create a new release on GitHub using the tag $TAG"
 