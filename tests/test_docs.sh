#!/bin/bash
# Test Documentation boxes -
# !!! <TYPE>: is not allowed!
# !!! <TYPE> "title" - Title needs to be quoted!
# Same for ???
grep -Er '^(!{3}|\?{3})\s\S+:|^(!{3}|\?{3})\s\S+\s[^"]' docs/*

if  [ $? -ne 0 ]; then
    echo "Docs test success."
    exit 0
fi
echo "Docs test failed."
exit 1
