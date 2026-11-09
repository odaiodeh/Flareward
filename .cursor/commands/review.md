This command might include optional parameters
basic / deep - this is the type of review to invoke if no parameter is given for that option the default should be basic
files/folders - if file or folder specification is given only review them.

following my developing a new feature please follow these steps:
1. go over the code, and get all the changes.
2. (only if deep review) prepare a design you can use as a reference, in addition where the folder containing parts of the new feature includes an architecture.md file use it as reference as well.
3. review the code added in this branch and gather all your comments in a file named <branch_name>_<review_type>_review.md (where branch name is the actual branch name you checked).
pay close attention to the design and make sure it's not being broken in any way
the review file should be built like this:
1. list of issues found split by areas and severity (area first)
2. at the top a short overview of the review and the purpose of the feature as you understood it
3. if a design is available add it to the file (if you created the design by running deep review add it as is if the design is part of the added files to the branch just specify its location)
