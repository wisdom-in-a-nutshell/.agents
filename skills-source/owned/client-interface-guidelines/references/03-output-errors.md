### Output

**Human-readable output is paramount.**
Humans come first, machines second.
The most simple and straightforward heuristic for whether a particular output stream (`stdout` or `stderr`) is being read by a human is _whether or not it’s a TTY_.
Whatever language you’re using, it will have a utility or library for doing this (e.g. Python, Node, Go).

_Further reading on what a TTY is._

**Have machine-readable output where it does not impact usability.**
Streams of text is the universal interface in UNIX.
Programs typically output lines of text, and programs typically expect lines of text as input,
therefore you can compose multiple programs together.
This is normally done to make it possible to write scripts,
but it can also help the usability for humans using programs.
For example, a user should be able to pipe output to `grep` and it should do what they expect.

> “Expect the output of every program to become the input to another, as yet unknown, program.”
— Doug McIlroy

**If human-readable output breaks machine-readable output, use `--plain` to display output in plain, tabular text format for integration with tools like `grep` or `awk`.**
In some cases, you might need to output information in a different way to make it human-readable.
For example, if you are displaying a line-based table, you might choose to split a cell into multiple lines, fitting in more information while keeping it within the width of the screen.
This breaks the expected behavior of there being one piece of data per line, so you should provide a `--plain` flag for scripts, which disables all such manipulation and outputs one record per line.

**Display output as formatted JSON if `--json` is passed.**
JSON allows for more structure than plain text, so it makes it much easier to output and handle complex data structures.
`jq` is a common tool for working with JSON on the command-line, and there is now a whole ecosystem of tools that output and manipulate JSON.

It is also widely used on the web, so by using JSON as the input and output of programs, you can pipe directly to and from web services using `curl`.

**Display output on success, but keep it brief.**
Traditionally, when nothing is wrong, UNIX commands display no output to the user.
This makes sense when they’re being used in scripts, but can make commands appear to be hanging or broken when used by humans.
For example, `cp` will not print anything, even if it takes a long time.

It’s rare that printing nothing at all is the best default behavior, but it’s usually best to err on the side of less.

For instances where you do want no output (for example, when used in shell scripts), to avoid clumsy redirection of `stderr` to `/dev/null`, you can provide a `-q` option to suppress all non-essential output.

**If you change state, tell the user.**
When a command changes the state of a system, it’s especially valuable to explain what has just happened, so the user can model the state of the system in their head—particularly if the result doesn’t directly map to what the user requested.

For example, `git push` tells you exactly what it is doing, and what the new state of the remote branch is:

```
$ git push
Enumerating objects: 18, done.
Counting objects: 100% (18/18), done.
Delta compression using up to 8 threads
Compressing objects: 100% (10/10), done.
Writing objects: 100% (10/10), 2.09 KiB | 2.09 MiB/s, done.
Total 10 (delta 8), reused 0 (delta 0), pack-reused 0
remote: Resolving deltas: 100% (8/8), completed with 8 local objects.
To github.com:replicate/replicate.git
 + 6c22c90...a2a5217 bfirsh/fix-delete -> bfirsh/fix-delete
```

**Make it easy to see the current state of the system.**
If your program does a lot of complex state changes and it is not immediately visible in the filesystem, make sure you make this easy to view.

For example, `git status` tells you as much information as possible about the current state of your Git repository, and some hints at how to modify the state:

```
$ git status
On branch bfirsh/fix-delete
Your branch is up to date with 'origin/bfirsh/fix-delete'.

Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   cli/pkg/cli/rm.go

no changes added to commit (use "git add" and/or "git commit -a")
```

**Suggest commands the user should run.**
When several commands form a workflow, suggesting to the user commands they can run next helps them learn how to use your program and discover new functionality.
For example, in the `git status` output above, it suggests commands you can run to modify the state you are viewing.

**Actions crossing the boundary of the program’s internal world should usually be explicit.**
This includes things like:

- Reading or writing files that the user didn’t explicitly pass as arguments (unless those files are storing internal program state, such as a cache).
- Talking to a remote server, e.g. to download a file.

**Increase information density—with ASCII art!**
For example, `ls` shows permissions in a scannable way.
When you first see it, you can ignore most of the information.
Then, as you learn how it works, you pick out more patterns over time.

```
-rw-r--r-- 1 root root     68 Aug 22 23:20 resolv.conf
lrwxrwxrwx 1 root root     13 Mar 14 20:24 rmt -> /usr/sbin/rmt
drwxr-xr-x 4 root root   4.0K Jul 20 14:51 security
drwxr-xr-x 2 root root   4.0K Jul 20 14:53 selinux
-rw-r----- 1 root shadow  501 Jul 20 14:44 shadow
-rw-r--r-- 1 root root    116 Jul 20 14:43 shells
drwxr-xr-x 2 root root   4.0K Jul 20 14:57 skel
-rw-r--r-- 1 root root      0 Jul 20 14:43 subgid
-rw-r--r-- 1 root root      0 Jul 20 14:43 subuid
```

**Use color with intention.**
For example, you might want to highlight some text so the user notices it, or use red to indicate an error.
Don’t overuse it—if everything is a different color, then the color means nothing and only makes it harder to read.

**Disable color if your program is not in a terminal or the user requested it.**
These things should disable colors:

- `stdout` or `stderr` is not an interactive terminal (a TTY).
  It’s best to individually check—if you’re piping `stdout` to another program, it’s still useful to get colors on `stderr`.
- The `NO_COLOR` environment variable is set and it is not empty (regardless of its value).
- The `TERM` environment variable has the value `dumb`.
- The user passes the option `--no-color`.
- You may also want to add a `MYAPP_NO_COLOR` environment variable in case users want to disable color specifically for your program.

**If `stdout` is not an interactive terminal, don’t display any animations.**
This will stop progress bars turning into Christmas trees in CI log output.

**Use symbols and emoji where it makes things clearer.**
Pictures can be better than words if you need to make several things distinct, catch the user’s attention, or just add a bit of character.
Be careful, though—it can be easy to overdo it and make your program look cluttered or feel like a toy.

For example, yubikey-agent uses emoji to add structure to the output so it isn’t just a wall of text, and a ❌ to draw your attention to an important piece of information:

```shell-session
$ yubikey-agent -setup
🔐 The PIN is up to 8 numbers, letters, or symbols. Not just numbers!
❌ The key will be lost if the PIN and PUK are locked after 3 incorrect tries.

Choose a new PIN/PUK:
Repeat the PIN/PUK:

🧪 Reticulating splines …

✅ Done! This YubiKey is secured and ready to go.
🤏 When the YubiKey blinks, touch it to authorize the login.

🔑 Here's your new shiny SSH public key:
ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBCEJ/
UwlHnUFXgENO3ifPZd8zoSKMxESxxot4tMgvfXjmRp5G3BGrAnonncE7Aj11pn3SSYgEcrrn2sMyLGpVS0=

💭 Remember: everything breaks, have a backup plan for when this YubiKey does.
```

**By default, don’t output information that’s only understandable by the creators of the software.**
If a piece of output serves only to help you (the developer) understand what your software is doing, it almost certainly shouldn’t be displayed to normal users by default—only in verbose mode.

Invite usability feedback from outsiders and people who are new to your project.
They’ll help you see important issues that you are too close to the code to notice.

**Don’t treat `stderr` like a log file, at least not by default.**
Don’t print log level labels (`ERR`, `WARN`, etc.) or extraneous contextual information, unless in verbose mode.

**Use a pager (e.g. `less`) if you are outputting a lot of text.**
For example, `git diff` does this by default.
Using a pager can be error-prone, so be careful with your implementation such that you don’t make the experience worse for the user.
Use a pager only if `stdin` or `stdout` is an interactive terminal.

A good sensible set of options to use for `less` is `less -FIRX`.
This does not page if the content fills one screen, ignores case when you search, enables color and formatting, and leaves the contents on the screen when `less` quits.

There might be libraries in your language that are more robust than piping to `less`.
For example, pypager in Python.

### Errors

One of the most common reasons to consult documentation is to fix errors.
If you can make errors into documentation, then this will save the user loads of time.

**Catch errors and rewrite them for humans.**
If you’re expecting an error to happen, catch it and rewrite the error message to be useful.
Think of it like a conversation, where the user has done something wrong and the program is guiding them in the right direction.
Example: “Can’t write to file.txt. You might need to make it writable by running ‘chmod +w file.txt’.”

**Signal-to-noise ratio is crucial.**
The more irrelevant output you produce, the longer it’s going to take the user to figure out what they did wrong.
If your program produces multiple errors of the same type, consider grouping them under a single explanatory header instead of printing many similar-looking lines.

**Consider where the user will look first.**
Put the most important information at the end of the output.
The eye will be drawn to red text, so use it intentionally and sparingly.

**If there is an unexpected or unexplainable error, provide debug and traceback information, and instructions on how to submit a bug.**
That said, don’t forget about the signal-to-noise ratio: you don’t want to overwhelm the user with information they don’t understand.
Consider writing the debug log to a file instead of printing it to the terminal.

**Make it effortless to submit bug reports.**
One nice thing you can do is provide a URL and have it pre-populate as much information as possible.

