# Setup searches only the stores the Harness reads

Setup counts a Borrowed skill as Present only when it sits in a store the
current Harness reads, because a skill in another Harness's store is one
this Harness never loads, and a search across every store would report that
install as healthy. Cursor searches no `.claude` or `.codex` store: the IDE
reads them only through an import the user can turn off, and Setup cannot
read that setting.

A Harness also reads stores the search does not cover, such as Claude
Code's enterprise store. So when the search misses a skill that the Session
can still run, Setup counts it as Present and says the search did not find
it.
