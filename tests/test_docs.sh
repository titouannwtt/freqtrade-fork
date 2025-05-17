#!/bin/bash
# Test Documentation boxes -
# !!! <TYPE>: is not allowed!
# !!! <TYPE> "title" - Title needs to be quoted!
# Same for ???
grep -Er '^(!{3}|\?{3})\s\S+:|^(!{3}|\?{3})\s\S+\s[^"]' docs/*
format_issues=$?

failed=0

while read -r file; do
    awk -v fname="$file" '
    /^(!!!|\?\?\?)/ {
        current_line_number = NR
        current_line = $0
        if (getline nextLine <= 0 || nextLine !~ /^    /) {
            print "File:", fname
            print "Error in Line ", current_line_number, "Expected next line to start with 4 spaces"
            print ">>", current_line
            print "------"
            exit 1
        }
    }
    ' "$file"

    if [ $? -ne 0 ]; then
        failed=1
    fi
done < <(find . -type f -name "*.md")

if  [ $format_issues -eq 1 ] && [ $failed -eq 0 ]; then
    echo "Docs test success."
    exit 0
fi
echo "Docs test failed."
exit 1
