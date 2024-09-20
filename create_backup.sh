#!/bin/bash

# Create backup directory
mkdir -p backup

# Copy relevant files
cp main.py backup/
cp -r static backup/
cp -r templates backup/
cp forms.py backup/
cp config.py backup/
cp models.py backup/
cp db_check.py backup/
cp requirements.txt backup/

echo "Backup created successfully in the 'backup' directory."
