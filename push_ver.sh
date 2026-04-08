#!/usr/bin/env bash
set -euo pipefail

# Usage: ./push_ver.sh 0.6.9.4
# Bumps version in pyproject.toml + __init__.py, commits, tags, and pushes.
# server.py reads version from __init__.py at runtime, so only these two files need updating.

if [ $# -ne 1 ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 0.6.9.4"
    exit 1
fi

VERSION="$1"
TAG="v${VERSION}"

# Validate version format (X.Y.Z or X.Y.Z.W)
if ! echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+(\.[0-9]+)?$'; then
    echo "Error: invalid version format '$VERSION' (expected e.g. 0.6.9.4)"
    exit 1
fi

# Check tag doesn't already exist
if git tag -l "$TAG" | grep -q .; then
    echo "Error: tag $TAG already exists"
    exit 1
fi

# Check clean working tree
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Error: working tree is not clean, commit or stash first"
    exit 1
fi

# Get current version
OLD_VERSION=$(grep '^version' pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/')

echo "Bumping version: $OLD_VERSION -> $VERSION"

# Replace version in pyproject.toml
sed -i '' "s/^version = \".*\"/version = \"$VERSION\"/" pyproject.toml

# Replace version in __init__.py (server.py reads this at runtime)
sed -i '' "s/^__version__ = \".*\"/__version__ = \"$VERSION\"/" src/agentmatrix/__init__.py

# Commit, tag, push
git add pyproject.toml src/agentmatrix/__init__.py
git commit -m "chore: bump version to $VERSION"
git tag "$TAG"
git push origin main
git push origin "$TAG"

echo "Done: $TAG pushed"
